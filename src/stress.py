"""
stress.py — Stress Testing & Scenario Analysis
Real-Time Delta One Risk Dashboard

Simule l'impact de chocs de marché sur le portefeuille.
Pour chaque scénario, calcule le PnL stressé, la nouvelle VaR,
les nouvelles expositions et le P&L par position.

Approche : on applique un choc % sur le prix actuel de chaque ticker,
puis on recalcule toutes les métriques comme si ces prix étaient réels.
C'est la méthode "Historical Simulation Shift" utilisée sur les desks.
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from scipy import stats

from src.utils import get_logger, load_config

logger = get_logger(__name__)
config = load_config()


# ─── Scénarios prédéfinis ────────────────────────────────────────────────────

SCENARIOS = {
    "🔴 Equity Crash": {
        "description": "Krach actions : correction brutale type Mars 2020 ou Oct 2008",
        "shocks": {
            "SPY": -0.10,
            "TLT": +0.08,   # flight to safety : les obligations montent en cas de krach
            "EWQ": -0.09,
            "IWM": -0.15,
        },
        "vol_multiplier": 2.5,
    },
    "🟠 VIX Spike": {
        "description": "Pic de volatilité : VIX > 40, toutes les corrélations montent",
        "shocks": {
            "SPY": -0.06,
            "TLT": +0.05,   # flight to quality
            "EWQ": -0.05,
            "IWM": -0.09,
        },
        "vol_multiplier": 2.0,
    },
    "🟡 EUR/USD Shock": {
        "description": "Choc de change EUR/USD -5% : impact sur l'exposition Europe",
        "shocks": {
            "SPY":  0.00,
            "TLT": -0.02,   # légère hausse des taux = TLT baisse légèrement
            "EWQ": -0.05,   # exposition Europe impactée par le FX
            "IWM":  0.00,
        },
        "vol_multiplier": 1.3,
    },
    "🟢 Rally (Reverse Stress)": {
        "description": "Rally actions : momentum haussier type 2023 Q4",
        "shocks": {
            "SPY": +0.08,
            "TLT": -0.04,   # rally actions = taux remontent = TLT baisse (good for short)
            "EWQ": +0.06,
            "IWM": +0.07,
        },
        "vol_multiplier": 0.8,
    },
}


# ─── Calculs ─────────────────────────────────────────────────────────────────

def apply_scenario(
    positions: pd.DataFrame,
    shocks: Dict[str, float],
) -> pd.DataFrame:
    """
    Applique un choc de marché sur les prix actuels et recalcule les métriques.

    Formule pour chaque position :
        stressed_price = current_price × (1 + shock_pct)
        stressed_pnl   = (stressed_price - entry_price) × quantity
        pnl_impact     = stressed_pnl - current_pnl   (variation due au choc)

    Args:
        positions: DataFrame des positions courantes (avec current_price)
        shocks:    dict {ticker: shock_pct}  ex: {"SPY": -0.10}

    Returns:
        DataFrame avec colonnes stressed_price, stressed_pnl, pnl_impact, pnl_impact_pct
    """
    df = positions.copy()

    df["shock_pct"] = df["ticker"].map(shocks).fillna(0.0)
    df["stressed_price"] = df["current_price"] * (1 + df["shock_pct"])
    df["stressed_market_value"] = df["quantity"] * df["stressed_price"]
    df["stressed_pnl"] = (df["stressed_price"] - df["entry_price"]) * df["quantity"]
    df["pnl_impact"] = df["stressed_pnl"] - df["pnl"]
    df["pnl_impact_pct"] = df["shock_pct"] * 100  # choc appliqué en %

    return df


def compute_scenario_summary(stressed_positions: pd.DataFrame) -> Dict:
    """
    Calcule les métriques agrégées du portefeuille stressé.

    Returns:
        dict avec total_stressed_pnl, pnl_impact, stressed_gross, stressed_net,
        worst_position, best_position
    """
    total_stressed_pnl = stressed_positions["stressed_pnl"].sum()
    pnl_impact = stressed_positions["pnl_impact"].sum()
    stressed_gross = stressed_positions["stressed_market_value"].abs().sum()
    stressed_net = stressed_positions["stressed_market_value"].sum()

    worst = stressed_positions.loc[stressed_positions["pnl_impact"].idxmin()]
    best  = stressed_positions.loc[stressed_positions["pnl_impact"].idxmax()]

    return {
        "total_stressed_pnl": total_stressed_pnl,
        "pnl_impact": pnl_impact,
        "stressed_gross_exposure": stressed_gross,
        "stressed_net_exposure": stressed_net,
        "worst_position": worst["ticker"],
        "worst_pnl_impact": worst["pnl_impact"],
        "best_position": best["ticker"],
        "best_pnl_impact": best["pnl_impact"],
    }


def compute_stressed_var(
    daily_returns: pd.DataFrame,
    positions: pd.DataFrame,
    vol_multiplier: float = 1.0,
    confidence: float = 0.95,
) -> float:
    """
    VaR stressée : on multiplie la volatilité historique par un facteur de stress.

    Méthode : VaR paramétrique avec sigma × vol_multiplier
    C'est l'approche Stressed VaR (sVaR) introduite par Bâle II.5.

    Args:
        daily_returns:  DataFrame de rendements historiques
        positions:      DataFrame des positions avec weights
        vol_multiplier: facteur d'amplification de la volatilité (ex: 2.0 = stress x2)
        confidence:     niveau de confiance (0.95)

    Returns:
        float: VaR stressée en $ (positive = perte potentielle)
    """
    weights = {}
    for _, pos in positions.iterrows():
        t = pos["ticker"]
        w = pos["weight_pct"] / 100.0 * (1 if pos["quantity"] > 0 else -1)
        weights[t] = w

    available = {t: w for t, w in weights.items() if t in daily_returns.columns}
    if not available:
        return 0.0

    w_series = pd.Series(available)
    port_ret = (daily_returns[list(available.keys())] * w_series).sum(axis=1)

    mu    = port_ret.mean()
    sigma = port_ret.std() * vol_multiplier   # ← amplification stress

    nav = (positions["market_value"].abs()).sum()
    z   = stats.norm.ppf(1 - confidence)
    var_pct = -(mu + z * sigma)

    return float(var_pct * nav)


def run_all_scenarios(
    positions: pd.DataFrame,
    daily_returns: pd.DataFrame,
) -> List[Dict]:
    """
    Lance tous les scénarios prédéfinis et retourne une liste de résultats.

    Returns:
        liste de dicts prêts à être affichés dans le dashboard
    """
    results = []
    nav = positions["market_value"].sum()

    for scenario_name, scenario_cfg in SCENARIOS.items():
        stressed = apply_scenario(positions, scenario_cfg["shocks"])
        summary  = compute_scenario_summary(stressed)
        s_var    = compute_stressed_var(
            daily_returns, positions,
            vol_multiplier=scenario_cfg["vol_multiplier"],
        )

        pnl_impact    = summary["pnl_impact"]
        pnl_impact_pct = (pnl_impact / abs(nav) * 100) if nav != 0 else 0

        results.append({
            "scenario":          scenario_name,
            "description":       scenario_cfg["description"],
            "pnl_impact":        pnl_impact,
            "pnl_impact_pct":    pnl_impact_pct,
            "total_stressed_pnl": summary["total_stressed_pnl"],
            "stressed_gross":    summary["stressed_gross_exposure"],
            "stressed_net":      summary["stressed_net_exposure"],
            "stressed_var":      s_var,
            "worst_position":    summary["worst_position"],
            "worst_pnl_impact":  summary["worst_pnl_impact"],
            "best_position":     summary["best_position"],
            "best_pnl_impact":   summary["best_pnl_impact"],
            "stressed_positions": stressed,
            "vol_multiplier":    scenario_cfg["vol_multiplier"],
        })

    return results


def build_custom_scenario(
    positions: pd.DataFrame,
    daily_returns: pd.DataFrame,
    shocks: Dict[str, float],
    vol_multiplier: float = 1.0,
    confidence: float = 0.95,
) -> Dict:
    """
    Scénario personnalisé avec des chocs définis manuellement (sliders dashboard).

    Args:
        shocks:         dict {ticker: shock_pct}  ex: {"SPY": -0.05}
        vol_multiplier: amplification de la vol

    Returns:
        dict avec les métriques du scénario custom
    """
    nav = positions["market_value"].sum()
    stressed = apply_scenario(positions, shocks)
    summary  = compute_scenario_summary(stressed)
    s_var    = compute_stressed_var(daily_returns, positions, vol_multiplier, confidence)

    pnl_impact = summary["pnl_impact"]
    pnl_impact_pct = (pnl_impact / abs(nav) * 100) if nav != 0 else 0

    return {
        "scenario":           "⚙️ Custom Scenario",
        "description":        "Scénario personnalisé via sliders",
        "pnl_impact":         pnl_impact,
        "pnl_impact_pct":     pnl_impact_pct,
        "total_stressed_pnl": summary["total_stressed_pnl"],
        "stressed_gross":     summary["stressed_gross_exposure"],
        "stressed_net":       summary["stressed_net_exposure"],
        "stressed_var":       s_var,
        "worst_position":     summary["worst_position"],
        "worst_pnl_impact":   summary["worst_pnl_impact"],
        "best_position":      summary["best_position"],
        "best_pnl_impact":    summary["best_pnl_impact"],
        "stressed_positions": stressed,
        "vol_multiplier":     vol_multiplier,
    }
