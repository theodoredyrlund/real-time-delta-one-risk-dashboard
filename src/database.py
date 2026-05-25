"""
database.py — Persistence des données (SQLite / PostgreSQL)
Real-Time Delta One Risk Dashboard

Stocke les snapshots de marché, l'historique PnL, et les métriques de risque.
"""

import pandas as pd
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, text, Column, Float, String, DateTime, Integer
from sqlalchemy.orm import declarative_base, Session

from src.utils import get_logger, load_config, ROOT_DIR

logger = get_logger(__name__)
config = load_config()

Base = declarative_base()


# ─── Connexion ───────────────────────────────────────────────────────────────

def get_engine():
    """
    Crée et retourne le moteur SQLAlchemy selon la config.
    MVP : SQLite | Cloud : PostgreSQL
    """
    db_cfg = config.get("database", {})
    db_type = db_cfg.get("type", "sqlite")

    if db_type == "sqlite":
        db_path = ROOT_DIR / db_cfg.get("sqlite_path", "data/dashboard.db")
        db_path.parent.mkdir(exist_ok=True)
        url = f"sqlite:///{db_path}"
    else:
        host = db_cfg.get("host", "localhost")
        port = db_cfg.get("port", 5432)
        name = db_cfg.get("name", "delta_one_db")
        user = db_cfg.get("user", "admin")
        pwd = db_cfg.get("password", "")
        url = f"postgresql://{user}:{pwd}@{host}:{port}/{name}"

    engine = create_engine(url, echo=False)
    logger.info(f"Database engine created: {db_type}")
    return engine


def init_db(engine=None):
    """Crée les tables si elles n'existent pas."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables initialized")
    return engine


# ─── Sauvegarde / chargement ─────────────────────────────────────────────────

def save_price_snapshot(prices: dict, engine=None):
    """
    Sauvegarde un snapshot des prix dans la table price_snapshots.

    Args:
        prices: dict {ticker: price}
    """
    if engine is None:
        engine = get_engine()
    rows = [
        {"ticker": k, "price": v, "timestamp": datetime.utcnow()}
        for k, v in prices.items()
        if v is not None
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_sql("price_snapshots", engine, if_exists="append", index=False)
        logger.info(f"Saved {len(df)} price snapshots")


def save_pnl_snapshot(pnl_data: dict, engine=None):
    """
    Sauvegarde un snapshot du PnL total.

    Args:
        pnl_data: dict avec total_pnl, intraday_pnl, etc.
    """
    if engine is None:
        engine = get_engine()
    row = {**pnl_data, "timestamp": datetime.utcnow()}
    df = pd.DataFrame([row])
    df.to_sql("pnl_snapshots", engine, if_exists="append", index=False)
    logger.info("Saved PnL snapshot")


def save_risk_metrics(metrics: dict, engine=None):
    """Sauvegarde un snapshot des métriques de risque."""
    if engine is None:
        engine = get_engine()
    row = {**metrics, "timestamp": datetime.utcnow()}
    df = pd.DataFrame([row])
    df.to_sql("risk_metrics", engine, if_exists="append", index=False)
    logger.info("Saved risk metrics snapshot")


def load_pnl_history(days: int = 90, engine=None) -> pd.DataFrame:
    """
    Charge l'historique PnL depuis la base.

    Args:
        days: nombre de jours d'historique à charger

    Returns:
        DataFrame avec colonnes [timestamp, total_pnl, intraday_pnl]
    """
    if engine is None:
        engine = get_engine()
    try:
        query = f"""
            SELECT timestamp, total_pnl, intraday_pnl
            FROM pnl_snapshots
            WHERE timestamp >= datetime('now', '-{days} days')
            ORDER BY timestamp ASC
        """
        df = pd.read_sql(query, engine, parse_dates=["timestamp"])
        return df
    except Exception as e:
        logger.warning(f"Could not load PnL history: {e}")
        return pd.DataFrame()


def load_price_history(ticker: str, days: int = 30, engine=None) -> pd.DataFrame:
    """Charge l'historique des prix d'un ticker depuis la base."""
    if engine is None:
        engine = get_engine()
    try:
        query = f"""
            SELECT timestamp, price
            FROM price_snapshots
            WHERE ticker = '{ticker}'
            AND timestamp >= datetime('now', '-{days} days')
            ORDER BY timestamp ASC
        """
        return pd.read_sql(query, engine, parse_dates=["timestamp"])
    except Exception as e:
        logger.warning(f"Could not load price history for {ticker}: {e}")
        return pd.DataFrame()
