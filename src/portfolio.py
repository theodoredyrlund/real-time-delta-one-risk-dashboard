"""
portfolio.py — Gestion du portefeuille fictif Delta One
Real-Time Delta One Risk Dashboard

Charge les positions depuis config.yaml, enrichit avec les prix live,
calcule les valeurs de marché et les expositions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from src.utils import get_logger, load_config, safe_divide
from src.market_data import fetch_realtime_prices, fetch_open_prices

logger = get_logger(__name__)
config = load_config()


# ─── Chargement des positions ────────────────────────────────────────────────

def load_positions() -> pd.DataFrame:
    """
    Charge les positions depuis config.yaml.

    Returns:
        DataFrame avec les positions de base (sans prix live)
    """
    raw = config["portfolio"]["positions"]
    df = pd.DataFrame(raw)
    # Sépare les vraies positions des indicateurs
    df = df[df["side"] != "indicator"].copy()
    df["quantity"] = df["quantity"].astype(float)
    df["entry_price"] = df["entry_price"].astype(float)
    logger.info(f"Loaded {len(df)} positions from config")
    return df


def enrich_with_live_prices(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les prix actuels et calcule les métriques de base.

    Args:
        positions: DataFrame issu de load_positions()

    Returns:
        DataFrame enrichi avec current_price, market_value, pnl, weight
    """
    tickers = positions["ticker"].tolist()
    live_prices = fetch_realtime_prices(tickers)
    open_prices = fetch_open_prices(tickers)

    df = positions.copy()
    df["current_price"] = df["ticker"].map(live_prices)
    df["open_price"] = df["ticker"].map(open_prices)

    # Fallback : si prix live indisponible, utiliser prix d'entrée
    df["current_price"] = df["current_price"].fillna(df["entry_price"])
    df["open_price"] = df["open_price"].fillna(df["current_price"])

    # Valeur de marché (positive pour long, négative pour short)
    df["market_value"] = df["quantity"] * df["current_price"]

    # PnL par position
    df["pnl"] = (df["current_price"] - df["entry_price"]) * df["quantity"]
    df["pnl_pct"] = (df["current_price"] - df["entry_price"]) / df["entry_price"] * 100

    # PnL intraday (par rapport à l'open)
    df["intraday_pnl"] = (df["current_price"] - df["open_price"]) * df["quantity"]

    # Notionnel (valeur absolue)
    df["notional"] = df["market_value"].abs()

    # Poids dans le portefeuille (basé sur valeur absolue)
    total_notional = df["notional"].sum()
    df["weight_pct"] = df["notional"] / total_notional * 100 if total_notional > 0 else 0

    logger.info(f"Enriched {len(df)} positions with live prices")
    return df


# ─── Expositions ────────────────────────────────────────────────────────────

def compute_gross_exposure(positions: pd.DataFrame) -> float:
    """
    Gross exposure = somme des valeurs absolues de marché.
    Mesure le levier total du portefeuille.
    """
    return positions["market_value"].abs().sum()


def compute_net_exposure(positions: pd.DataFrame) -> float:
    """
    Net exposure = somme algébrique des valeurs de marché.
    Mesure le biais directionnel (positif = net long).
    """
    return positions["market_value"].sum()


def compute_exposure_by_geography(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Répartition de l'exposition par zone géographique.

    Returns:
        DataFrame avec colonnes [geography, net_exposure, gross_exposure, weight_pct]
    """
    geo = positions.groupby("geography").agg(
        net_exposure=("market_value", "sum"),
        gross_exposure=("notional", "sum"),
    ).reset_index()
    total = geo["gross_exposure"].sum()
    geo["weight_pct"] = geo["gross_exposure"] / total * 100 if total > 0 else 0
    return geo.sort_values("gross_exposure", ascending=False)


def compute_exposure_by_asset_class(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Répartition de l'exposition par asset class.
    """
    ac = positions.groupby("asset_class").agg(
        net_exposure=("market_value", "sum"),
        gross_exposure=("notional", "sum"),
    ).reset_index()
    total = ac["gross_exposure"].sum()
    ac["weight_pct"] = ac["gross_exposure"] / total * 100 if total > 0 else 0
    return ac.sort_values("gross_exposure", ascending=False)


# ─── Métriques agrégées ─────────────────────────────────────────────────────

def get_portfolio_summary(positions: pd.DataFrame) -> Dict:
    """
    Retourne un dictionnaire de métriques synthétiques du portefeuille.
    """
    nav = positions["market_value"].sum()
    gross = compute_gross_exposure(positions)
    net = compute_net_exposure(positions)
    total_pnl = positions["pnl"].sum()
    intraday_pnl = positions["intraday_pnl"].sum()

    # Levier = gross / |NAV|
    leverage = safe_divide(gross, abs(nav))

    # Top contributor au PnL
    top_winner = positions.loc[positions["pnl"].idxmax()]
    top_loser = positions.loc[positions["pnl"].idxmin()]

    return {
        "nav": nav,
        "gross_exposure": gross,
        "net_exposure": net,
        "leverage": leverage,
        "total_pnl": total_pnl,
        "intraday_pnl": intraday_pnl,
        "n_positions": len(positions),
        "n_long": len(positions[positions["quantity"] > 0]),
        "n_short": len(positions[positions["quantity"] < 0]),
        "top_winner": top_winner["ticker"],
        "top_winner_pnl": top_winner["pnl"],
        "top_loser": top_loser["ticker"],
        "top_loser_pnl": top_loser["pnl"],
    }


def get_top_movers(positions: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """
    Retourne les N positions avec le plus grand mouvement intraday en %.
    """
    df = positions.copy()
    df["intraday_pct"] = (
        (df["current_price"] - df["open_price"])
        / df["open_price"].replace(0, float("nan"))
        * 100
    )
    return df[["ticker", "name", "intraday_pct", "intraday_pnl"]].reindex(
        df["intraday_pct"].abs().nlargest(n).index
    )
