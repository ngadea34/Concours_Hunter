"""Point d'entrée : API + interface + planificateur dans un seul processus local."""
from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import router
from .api.weekly_routes import router as weekly_router
from .config import get_settings
from .db.migrations import migrate
from .db.session import session_scope
from .logging_setup import setup_logging
from .security.crypto import get_api_token

log = logging.getLogger("concours_hunter")
STATIC = Path(__file__).parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    setup_logging()
    migrate()
    s = get_settings()
    if s.seed_sources:
        from .seed import seed

        with session_scope() as db:
            seed(db)
    get_api_token()
    from .scheduler.runner import runner

    if s.scheduler_enabled:
        runner.start()
    log.info("Concours Hunter %s prêt sur http://%s:%s", __version__, s.host, s.port)
    yield
    runner.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Concours Hunter", version=__version__, lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")

    @app.middleware("http")
    async def security(request: Request, call_next):  # noqa: ANN001, ANN202
        s = get_settings()
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].lower()
        client = request.client.host if request.client else ""
        token = request.headers.get("x-ch-token") or request.cookies.get("ch_token") or ""
        request.state.token_ok = bool(token) and hmac.compare_digest(token, get_api_token())
        is_local = client in ("127.0.0.1", "::1", "testclient") and host in LOCAL_HOSTS | {"testserver"}
        request.state.trusted = s.localhost_trusted and is_local
        if request.url.path.startswith("/api") and request.url.path not in ("/api/health", "/api/auth/check"):
            # Anti-DNS-rebinding : en mode non LAN, on n'accepte que des Host locaux
            if not request.state.token_ok and not request.state.trusted:
                return JSONResponse({"detail": "Jeton requis (X-CH-Token)"}, status_code=401)
            # Anti-CSRF : une page web tierce ne peut pas déclencher d'action
            origin = request.headers.get("origin")
            if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
                same = origin.split("://", 1)[-1].rsplit(":", 1)[0].lower() in LOCAL_HOSTS | {host}
                ext = origin.startswith(("chrome-extension://", "moz-extension://", "extension://"))
                if not (same or ext):
                    return JSONResponse({"detail": "Origine refusée"}, status_code=403)
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        return resp

    app.include_router(router)
    app.include_router(weekly_router)

    if (STATIC / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):  # noqa: ANN202
        if path.startswith("api/"):
            return JSONResponse({"detail": "Introuvable"}, status_code=404)
        f = (STATIC / path).resolve()
        if path and f.is_file() and STATIC.resolve() in f.parents:
            return FileResponse(f)
        idx = STATIC / "index.html"
        if idx.exists():
            return FileResponse(idx)
        return JSONResponse({"detail": "Interface non compilée : lancez scripts/build-frontend"}, status_code=503)

    return app


app = create_app()


def run() -> None:
    import uvicorn

    s = get_settings()
    host = s.host
    try:  # mode LAN (smartphone) : activé dans Réglages, pris en compte au redémarrage
        from .admin.settings_service import get_settings_dict
        from .db.migrations import migrate

        migrate()
        with session_scope() as db:
            if get_settings_dict(db)["lan_mode"] and host == "127.0.0.1":
                host = "0.0.0.0"
    except Exception:  # noqa: BLE001
        pass
    if host != "127.0.0.1":
        log.warning("Mode LAN : accès réseau local protégé par jeton (python -m app.cli token)")
    uvicorn.run("app.main:app", host=host, port=s.port, log_level=s.log_level.lower())


if __name__ == "__main__":
    run()
