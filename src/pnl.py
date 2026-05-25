"""
pnl.py — Calcul du PnL (Profit & Loss)
Real-Time Delta One Risk Dashboard

Calcule le PnL par position, total, intraday, et construit l'historique.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from src.utils import get_logger, load_config
from src.market_data import fetch_historical_prices

logger = get_logger(__name__)
config = load_config()


# ─── PnL par position ────────────────────────────────────────────────────────

def compute_position_pnl(
    current_price: float,
    entry_price: float,
    quantity: float,
) -> Dict[str, float]:
    """
    PnL d'une position individuelle.

    Formule: PnL = (P_current - P_entry) × Qty

    Args:
        current_price: prix de marché actuel
        entry_price:   prix d'entrée en position
        quantity:      nombre de titres (négatif si short)

    Returns:
        dict avec pnl absolu et pnl en %
    """
    pnl = (current_price - entry_price) * quantity
    pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price != 0 else 0
    return {"pnl": pnl, "pnl_pct": pnl_pct}


def compute_total_pnl(positions: pd.DataFrame) -> float:
    """PnL total du portefeuille (somme de toutes les positions)."""
    return float(positions["pnl"].sum())


def compute_intraday_pnl(positions: pd.DataFrame) -> float:
    """PnL intraday du portefeuille (par rapport au prix d'ouverture)."""
    return float(positions["intraday_pnl"].sum())


# ─── Historique du PnL ───────────────────────────────────────────────────────

def build_pnl_history(
    positions: pd.DataFrame,
    period: str = "3mo",
) -> pd.DataFrame:
    """
    Reconstitue l'historique du PnL du portefeuille à partir des prix historiques.

    Pour chaque jour, calcule le PnL comme si le portefeuille avait été
    constitué à la date d'entrée avec les mêmes prix.

    Args:
        positions: DataFrame des positions courantes
        period:    historique à charger

    Returns:
        DataFrame avec colonnes [date, portfolio_pnl, cumulative_pnl, daily_return]
    """
    tickers = positions["ticker"].tolist()
    hist = fetch_historical_prices(tickers, period=period, interval="1d")

    if hist.empty:
        logger.warning("No historical data available for PnL history")
        return pd.DataFrame()

    # Pour chaque ticker, PnL journalier = variation de prix × quantité
    pnl_df = pd.DataFrame(index=hist.index)
    for _, row in positions.iterrows():
        ticker = row["ticker"]
        qty = row["quantity"]
        if ticker in hist.columns:
            price_series = hist[ticker].dropna()
            # PnL cumulatif : (prix_t - prix_entry) × qty
            entry = row["entry_price"]
            pnl_df[ticker] = (price_series - entry) * qty

    pnl_df["portfolio_pnl"] = pnl_df.sum(axis=1)

    # PnL journalier (différence)
    pnl_df["daily_pnl"] = pnl_df["portfolio_pnl"].diff()
    pnl_df.loc[pnl_df.index[0], "daily_pnl"] = pnl_df["portfolio_pnl"].iloc[0]

    # Rendement journalier en % (par rapport au NAV initial)
    initial_nav = (positions["entry_price"] * positions["quantity"].abs()).sum()
    pnl_df["daily_return_pct"] = pnl_df["daily_pnl"] / initial_nav * 100

    return pnl_df[["portfolio_pnl", "daily_pnl", "daily_return_pct"]].reset_index()


def compute_pnl_attribution(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Attribution du PnL par position (contribution absolue et relative).

    Returns:
        DataFrame trié par contribution décroissante
    """
    df = positions[["ticker", "name", "side", "pnl", "pnl_pct", "intraday_pnl"]].copy()
    total_abs = df["pnl"].abs().sum()
    df["pnl_contribution_pct"] = df["pnl"].abs() / total_abs * 100 if total_abs > 0 else 0
    df["direction"] = df["pnl"].apply(lambda x: "Winner" if x >= 0 else "Loser")
    return df.sort_values("pnl", ascending=False)


def compute_rolling_pnl(
    pnl_history: pd.DataFrame,
    window: int = 5,
) -> pd.DataFrame:
    """
    Calcule le PnL glissant sur N jours.

    Args:
        pnl_history: résultat de build_pnl_history()
        window:      fenêtre en jours

    Returns:
        DataFrame avec colonne rolling_pnl ajoutée
    """
    df = pnl_history.copy()
    df[f"rolling_pnl_{window}d"] = df["daily_pnl"].rolling(window).sum()
    return df
