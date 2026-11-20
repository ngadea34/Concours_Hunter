"""Semaines françaises (lundi → dimanche) dans le fuseau de l'utilisateur. Les dates en base sont en UTC naïf."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Europe/Paris"


def zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def now_local(tz: ZoneInfo, now_utc: datetime | None = None) -> datetime:
    n = now_utc or datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    return n.astimezone(tz)


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_days(start: date) -> list[date]:
    return [start + timedelta(days=i) for i in range(7)]


def end_of_day_utc(d: date, tz: ZoneInfo) -> datetime:
    """23:59:59 heure locale du jour d, exprimé en UTC naïf (gère l'heure d'été)."""
    loc = datetime.combine(d, time(23, 59, 59), tzinfo=tz)
    return loc.astimezone(timezone.utc).replace(tzinfo=None)


def local_to_utc(dt_local: datetime) -> datetime:
    return dt_local.astimezone(timezone.utc).replace(tzinfo=None)


def hours_until_close(end: date, tz: ZoneInfo, now_utc: datetime | None = None) -> float:
    # soustraction en UTC : entre deux datetimes du même fuseau, Python ignore le changement d'heure
    n = now_local(tz, now_utc).astimezone(timezone.utc)
    close = datetime.combine(end, time(23, 59, 59), tzinfo=tz).astimezone(timezone.utc)
    return (close - n).total_seconds() / 3600


def iso_week_label(start: date) -> str:
    y, w, _ = start.isocalendar()
    return f"{y}-S{w:02d}"
