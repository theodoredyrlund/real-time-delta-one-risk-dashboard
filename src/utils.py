"""
utils.py — Utilitaires partagés
Real-Time Delta One Risk Dashboard
"""

import logging
import os
import yaml
from pathlib import Path
from datetime import datetime
import pytz


# ─── Chemins ────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"


# ─── Config ─────────────────────────────────────────────────────────────────

def load_config(path: Path = CONFIG_PATH) -> dict:
    """Charge la configuration depuis config.yaml."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ─── Logging ────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Retourne un logger configuré."""
    LOGS_DIR.mkdir(exist_ok=True)
    cfg = load_config()
    level = getattr(logging, cfg.get("logging", {}).get("level", "INFO"))

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        fmt = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        # File handler
        log_file = LOGS_DIR / "dashboard.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ─── Dates ──────────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    """Retourne l'heure actuelle en UTC."""
    return datetime.now(tz=pytz.UTC)


def now_london() -> datetime:
    """Retourne l'heure actuelle à Londres (timezone desk)."""
    return datetime.now(tz=pytz.timezone("Europe/London"))


def market_is_open() -> bool:
    """Vérifie approximativement si le marché US est ouvert (9h30-16h ET)."""
    et = pytz.timezone("America/New_York")
    now = datetime.now(tz=et)
    if now.weekday() >= 5:  # samedi ou dimanche
        return False
    return 9 * 60 + 30 <= now.hour * 60 + now.minute <= 16 * 60


# ─── Formatage ──────────────────────────────────────────────────────────────

def fmt_currency(value: float, decimals: int = 0) -> str:
    """Formate un nombre en USD."""
    if value >= 0:
        return f"${value:,.{decimals}f}"
    return f"-${abs(value):,.{decimals}f}"


def fmt_pct(value: float, decimals: int = 2) -> str:
    """Formate un nombre en pourcentage."""
    return f"{value:+.{decimals}f}%"


def fmt_delta_color(value: float) -> str:
    """Retourne 'normal', 'inverse' pour Streamlit metric delta."""
    return "normal" if value >= 0 else "inverse"


# ─── Sécurité ────────────────────────────────────────────────────────────────

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division sécurisée qui retourne default si dénominateur est 0."""
    if denominator == 0 or denominator is None:
        return default
    return numerator / denominator
