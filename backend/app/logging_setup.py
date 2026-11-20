import logging
from logging.handlers import RotatingFileHandler

from .config import get_settings


def setup_logging() -> None:
    s = get_settings()
    root = logging.getLogger()
    if any(getattr(h, "_ch", False) for h in root.handlers):
        return
    root.setLevel(s.log_level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(s.data_dir / "concours-hunter.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    fh._ch = True  # type: ignore[attr-defined]
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh._ch = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    root.addHandler(sh)
