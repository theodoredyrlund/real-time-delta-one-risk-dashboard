"""
market_data.py — Ingestion des données de marché
Real-Time Delta One Risk Dashboard

Récupère les prix via yfinance (Yahoo Finance).
Pour un déploiement prod, remplacer par un vrai fournisseur (Bloomberg, Refinitiv).
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger, load_config

logger = get_logger(__name__)
config = load_config()


# ─── Fetch historique ────────────────────────────────────────────────────────

def fetch_historical_prices(
    tickers: List[str],
    period: str = "1y",
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Télécharge les prix de clôture historiques pour une liste de tickers.

    Args:
        tickers: liste de symboles Yahoo Finance
        period:  '1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y'
        interval: '1m', '5m', '15m', '30m', '60m', '1d', '1wk', '1mo'

    Returns:
        DataFrame (dates en index, tickers en colonnes) — prix de clôture ajustés
    """
    logger.info(f"Fetching historical prices: {tickers}, period={period}, interval={interval}")
    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

        # Extrait la colonne 'Close'
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Close"]
        else:
            prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

        prices = prices.dropna(how="all")
        logger.info(f"Fetched {len(prices)} rows for {len(prices.columns)} tickers")
        return prices

    except Exception as e:
        logger.error(f"Error fetching historical prices: {e}")
        return pd.DataFrame()


def fetch_realtime_prices(tickers: List[str]) -> Dict[str, float]:
    """
    Récupère le dernier prix disponible pour chaque ticker.

    Returns:
        dict {ticker: last_price}
    """
    logger.info(f"Fetching realtime prices for: {tickers}")
    prices = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            # fast_info.last_price est le plus fiable hors-heures
            price = info.last_price if info.last_price else info.previous_close
            prices[ticker] = round(float(price), 4)
        except Exception as e:
            logger.warning(f"Could not fetch price for {ticker}: {e}")
            prices[ticker] = None
    return prices


def fetch_daily_returns(
    tickers: List[str],
    period: str = "1y",
) -> pd.DataFrame:
    """
    Calcule les rendements journaliers logarithmiques.

    Returns:
        DataFrame de rendements (log returns)
    """
    prices = fetch_historical_prices(tickers, period=period, interval="1d")
    if prices.empty:
        return pd.DataFrame()
    returns = np.log(prices / prices.shift(1)).dropna()
    return returns


def fetch_open_prices(tickers: List[str]) -> Dict[str, float]:
    """
    Récupère les prix d'ouverture du jour (pour le PnL intraday).

    Returns:
        dict {ticker: open_price}
    """
    opens = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            today = t.history(period="1d", interval="1m")
            if not today.empty:
                opens[ticker] = round(float(today["Open"].iloc[0]), 4)
        except Exception as e:
            logger.warning(f"Could not fetch open for {ticker}: {e}")
            opens[ticker] = None
    return opens


def get_ticker_info(ticker: str) -> Dict:
    """Retourne les métadonnées d'un ticker (nom, secteur, beta)."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "name": info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "beta": info.get("beta", None),
            "currency": info.get("currency", "USD"),
        }
    except Exception as e:
        logger.warning(f"Could not fetch info for {ticker}: {e}")
        return {"name": ticker, "sector": "N/A", "beta": None, "currency": "USD"}


# ─── Simulation (fallback si pas de réseau) ──────────────────────────────────

def simulate_price_feed(
    tickers: List[str],
    base_prices: Dict[str, float],
    n_days: int = 252,
    volatility: float = 0.015,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Simule un historique de prix via un mouvement brownien géométrique.
    Utilisé comme fallback en l'absence de données réelles.

    Args:
        tickers:     liste de tickers
        base_prices: dict {ticker: prix_initial}
        n_days:      nombre de jours à simuler
        volatility:  volatilité journalière (défaut 1.5%)

    Returns:
        DataFrame de prix simulés
    """
    np.random.seed(seed)
    dates = pd.bdate_range(end=datetime.today(), periods=n_days)
    data = {}

    for ticker in tickers:
        base = base_prices.get(ticker, 100.0)
        drift = 0.0002  # drift journalier légèrement positif
        shocks = np.random.normal(drift, volatility, n_days)
        prices = base * np.cumprod(1 + shocks)
        data[ticker] = prices

    return pd.DataFrame(data, index=dates)
