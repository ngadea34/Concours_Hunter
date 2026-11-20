"""M10 : planificateur (APScheduler), quotas, reprise, arrêt d'urgence."""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select, update

from ..admin.backup import create_backup
from ..admin.settings_service import get_settings_dict
from ..audit import audit
from ..db.models import Contest, Participation, ScanJob, Source, utcnow
from ..db.session import session_scope
from ..discovery.fetcher import Fetcher
from ..discovery.pipeline import run_scan
from ..notifications.service import notify
from ..rewards.service import check_deadlines

log = logging.getLogger(__name__)


class Runner:
    def __init__(self) -> None:
        self.sched: BackgroundScheduler | None = None
        self.paused = False
        self.fetcher: Fetcher | None = None
        self.last: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ jobs
    def _wrap(self, job_id: str, fn) -> None:  # noqa: ANN001
        if self.paused:
            return
        if not self._lock.acquire(blocking=False):
            self.last[job_id] = {"at": utcnow().isoformat(), "status": "skipped (autre tâche en cours)"}
            return
        try:
            fn()
            self.last[job_id] = {"at": utcnow().isoformat(), "status": "ok"}
        except Exception as e:  # noqa: BLE001
            log.exception("Job %s", job_id)
            self.last[job_id] = {"at": utcnow().isoformat(), "status": f"error: {e}"[:200]}
        finally:
            self._lock.release()

    def job_scan(self) -> None:
        with session_scope() as db:
            settings = get_settings_dict(db)
            due_before = utcnow() - timedelta(minutes=settings["scan_interval_minutes"])
            sources = db.scalars(select(Source).where(Source.enabled.is_(True))).all()
            self.fetcher = Fetcher(max_per_hour=settings["max_requests_per_domain_per_hour"])
            try:
                for s in sources:
                    if self.paused or self.fetcher.stopped.is_set():
                        break
                    if s.last_scan_at and s.last_scan_at > due_before:
                        continue
                    run_scan(db, s, self.fetcher)
            finally:
                self.fetcher.close()
                self.fetcher = None

    def job_daily(self) -> None:
        with session_scope() as db:
            today = date.today()
            for c in db.scalars(select(Contest).where(Contest.end_date < today, Contest.status.in_(("new", "qualified", "to_verify")))):
                c.status = "expired"
            soon = today + timedelta(days=3)
            for c in db.scalars(select(Contest).where(Contest.status == "qualified", Contest.end_date >= today, Contest.end_date <= soon)):
                notify(db, "closing_soon", f"Clôture le {c.end_date:%d/%m} : {c.title[:150]}", c.prize_summary, c.id, dedup_key=f"soon:{c.id}")
            check_deadlines(db)

    def job_auto(self) -> None:
        from ..participation.browser_runner import run_auto

        with session_scope() as db:
            for p in db.scalars(select(Participation).where(Participation.status == "prepared", Participation.mode == "auto").limit(5)):
                if self.paused:
                    break
                run_auto(db, p)

    def job_backup(self) -> None:
        create_backup(label="auto")

    JOBS = {"scan": ("job_scan", 15), "daily": ("job_daily", 360), "auto": ("job_auto", 30), "backup": ("job_backup", 1440)}

    # ------------------------------------------------------------------ cycle de vie
    def start(self) -> None:
        with session_scope() as db:
            n = db.execute(update(ScanJob).where(ScanJob.status == "running").values(status="interrupted", finished_at=utcnow())).rowcount
            if n:
                audit(db, "system", "recover_interrupted_jobs", count=n)
        self.sched = BackgroundScheduler(job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600})
        for jid, (meth, minutes) in self.JOBS.items():
            self.sched.add_job(lambda m=meth, j=jid: self._wrap(j, getattr(self, m)), "interval", minutes=minutes, id=jid,
                               next_run_time=datetime.now() + timedelta(seconds=30 if jid != "backup" else 300))
        self.sched.start()

    def shutdown(self) -> None:
        if self.fetcher:
            self.fetcher.stopped.set()
        if self.sched:
            self.sched.shutdown(wait=False)
            self.sched = None

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def stop_all(self) -> None:
        """Arrêt d'urgence : pause + interruption des requêtes en cours."""
        self.paused = True
        if self.fetcher:
            self.fetcher.stopped.set()
        with session_scope() as db:
            audit(db, "user", "emergency_stop")

    def run_now(self, job_id: str) -> None:
        if job_id not in self.JOBS:
            raise KeyError(job_id)
        threading.Thread(target=self._wrap, args=(job_id, getattr(self, self.JOBS[job_id][0])), daemon=True).start()

    def status(self) -> dict:
        jobs = []
        for jid in self.JOBS:
            j = self.sched.get_job(jid) if self.sched else None
            jobs.append({"id": jid, "next_run": j.next_run_time.isoformat() if j and j.next_run_time else None,
                         "last_run": self.last.get(jid, {}).get("at"), "last_status": self.last.get(jid, {}).get("status")})
        return {"running": self.sched is not None and self.sched.running, "paused": self.paused, "jobs": jobs}


runner = Runner()
