"""Ligne de commande : python -m app.cli <commande>."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="concours-hunter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="démarre l'application")
    sub.add_parser("migrate", help="applique les migrations")
    sub.add_parser("backup", help="crée une sauvegarde")
    r = sub.add_parser("restore", help="restaure une sauvegarde")
    r.add_argument("name")
    sub.add_parser("backups", help="liste les sauvegardes")
    sub.add_parser("token", help="affiche le jeton d'accès (smartphone / extension)")
    sub.add_parser("doctor", help="diagnostic")
    sub.add_parser("demo-data", help="ajoute des concours de DÉMONSTRATION (fictifs, marqués [DÉMO])")
    en = sub.add_parser("enrich", help="cherche les règlements manquants (N concours max)")
    en.add_argument("limit", type=int, nargs="?", default=20)
    sc = sub.add_parser("scan", help="scanne une source par id")
    sc.add_argument("source_id", type=int)
    a = ap.parse_args(argv)

    from .db.migrations import migrate
    from .logging_setup import setup_logging

    setup_logging()
    if a.cmd == "serve":
        from .main import run

        run()
        return 0
    migrate()
    from .admin import backup as bk
    from .db.session import session_scope

    if a.cmd == "migrate":
        print("OK")
    elif a.cmd == "backup":
        print(json.dumps(bk.create_backup(label="cli")))
    elif a.cmd == "restore":
        bk.restore_backup(a.name)
        print("Restauré")
    elif a.cmd == "backups":
        print(json.dumps(bk.list_backups(), indent=2))
    elif a.cmd == "token":
        from .security.crypto import get_api_token

        print(get_api_token())
    elif a.cmd == "doctor":
        from .doctor import report

        print(json.dumps(report(), indent=2, ensure_ascii=False))
    elif a.cmd == "demo-data":
        from .demo import load_demo

        with session_scope() as db:
            print(f"{load_demo(db)} concours de démonstration ajoutés")
    elif a.cmd == "enrich":
        from .discovery.fetcher import Fetcher
        from .discovery.pipeline import enrich_backlog

        f = Fetcher()
        try:
            with session_scope() as db:
                print(json.dumps({"enriched": enrich_backlog(db, f, limit=a.limit)}))
        finally:
            f.close()
    elif a.cmd == "scan":
        from .db.models import Source
        from .discovery.pipeline import run_scan
        from .seed import seed

        with session_scope() as db:
            seed(db)
            s = db.get(Source, a.source_id)
            if not s:
                print("Source introuvable", file=sys.stderr)
                return 1
            j = run_scan(db, s)
            print(json.dumps({"status": j.status, "found": j.found, "new": j.new, "error": j.error}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
