"""
risk.py — Calcul des métriques de risque
Real-Time Delta One Risk Dashboard

Beta, volatilité, VaR, drawdown, corrélations, tracking error.
Toutes les formules sont documentées inline.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Optional, Tuple

from src.utils import get_logger, load_config, safe_divide
from src.market_data import fetch_historical_prices, fetch_daily_returns

logger = get_logger(__name__)
config = load_config()
risk_cfg = config.get("risk", {})


# ─── Beta ────────────────────────────────────────────────────────────────────

def compute_asset_beta(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    Beta d'un actif par rapport au benchmark via régression OLS.

    Formule: β = Cov(R_asset, R_benchmark) / Var(R_benchmark)

    Args:
        asset_returns:     série de rendements journaliers de l'actif
        benchmark_returns: série de rendements journaliers du benchmark (SPY)

    Returns:
        float: beta de l'actif
    """
    aligned = pd.concat([asset_returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 10:
        return 1.0  # défaut si pas assez de données

    cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].var()
    return safe_divide(cov, var, default=1.0)


def compute_portfolio_beta(
    positions: pd.DataFrame,
    returns: pd.DataFrame,
    benchmark_ticker: str = "SPY",
) -> float:
    """
    Beta du portefeuille = Σ (w_i × β_i)

    Args:
        positions: DataFrame des positions avec weights
        returns:   DataFrame des rendements historiques
        benchmark_ticker: ticker du benchmark

    Returns:
        float: beta du portefeuille pondéré
    """
    if benchmark_ticker not in returns.columns:
        logger.warning(f"Benchmark {benchmark_ticker} not in returns, defaulting beta to 1.0")
        return 1.0

    bench_ret = returns[benchmark_ticker]
    portfolio_beta = 0.0

    for _, pos in positions.iterrows():
        ticker = pos["ticker"]
        if ticker not in returns.columns:
            continue
        asset_ret = returns[ticker]
        beta_i = compute_asset_beta(asset_ret, bench_ret)
        weight_i = pos["weight_pct"] / 100.0
        # Signe: short inverse le beta
        sign = 1 if pos["quantity"] > 0 else -1
        portfolio_beta += weight_i * beta_i * sign

    return round(portfolio_beta, 3)


# ─── Volatilité ─────────────────────────────────────────────────────────────

def compute_rolling_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> pd.Series:
    """
    Volatilité glissante annualisée.

    Formule: σ_rolling = std(R, window) × √252

    Args:
        returns:   série de rendements journaliers
        window:    fenêtre glissante en jours (défaut 20 = ~1 mois)
        annualize: multiplier par √252 pour annualiser

    Returns:
        pd.Series: volatilité glissante
    """
    vol = returns.rolling(window).std()
    if annualize:
        vol = vol * np.sqrt(252)
    return vol


def compute_portfolio_volatility(
    positions: pd.DataFrame,
    returns: pd.DataFrame,
) -> float:
    """
    Volatilité annualisée du portefeuille (sur les 20 derniers jours).

    Returns:
        float: volatilité annualisée en %
    """
    # Calcule le rendement journalier du portefeuille pondéré
    weights = {}
    for _, pos in positions.iterrows():
        ticker = pos["ticker"]
        w = pos["weight_pct"] / 100.0 * (1 if pos["quantity"] > 0 else -1)
        weights[ticker] = w

    available = {t: w for t, w in weights.items() if t in returns.columns}
    if not available:
        return 0.0

    w_series = pd.Series(available)
    port_ret = (returns[list(available.keys())] * w_series).sum(axis=1)
    vol = port_ret.std() * np.sqrt(252)
    return round(float(vol) * 100, 2)  # en %


# ─── Value at Risk ────────────────────────────────────────────────────────────

def compute_var_historical(
    pnl_series: pd.Series,
    confidence: float = 0.95,
) -> float:
    """
    VaR historique (non-paramétrique).

    Formule: VaR_α = -Percentile(PnL, 1-α)
    Interprétation: perdu plus que VaR seulement (1-α)% du temps.

    Args:
        pnl_series:  série de PnL journaliers ($)
        confidence:  niveau de confiance (0.95 = 95%)

    Returns:
        float: VaR en $ (valeur positive = perte potentielle)
    """
    if pnl_series.empty:
        return 0.0
    var = float(np.percentile(pnl_series.dropna(), (1 - confidence) * 100))
    return -var  # convention: VaR positive = perte


def compute_var_parametric(
    pnl_series: pd.Series,
    confidence: float = 0.95,
) -> float:
    """
    VaR paramétrique (méthode variance-covariance, hypothèse gaussienne).

    Formule: VaR = μ + z_α × σ
    où z_α est le quantile de la loi normale au niveau α.

    Args:
        pnl_series: série de PnL journaliers ($)
        confidence: niveau de confiance

    Returns:
        float: VaR en $ (valeur positive = perte potentielle)
    """
    if pnl_series.empty:
        return 0.0
    mu = pnl_series.mean()
    sigma = pnl_series.std()
    z = stats.norm.ppf(1 - confidence)
    var = -(mu + z * sigma)
    return float(var)


def compute_var_as_pct_of_nav(var: float, nav: float) -> float:
    """Exprime la VaR en % du NAV."""
    return safe_divide(var, abs(nav)) * 100


# ─── Drawdown ────────────────────────────────────────────────────────────────

def compute_drawdown_series(cumulative_pnl: pd.Series) -> pd.Series:
    """
    Série de drawdowns journaliers.

    Formule: DD_t = (P_t - max(P_0..P_t)) / |max(P_0..P_t)|

    Returns:
        pd.Series: drawdowns en % (valeurs négatives)
    """
    rolling_max = cumulative_pnl.cummax()
    drawdown = (cumulative_pnl - rolling_max) / rolling_max.abs().replace(0, np.nan)
    return drawdown * 100  # en %


def compute_max_drawdown(cumulative_pnl: pd.Series) -> float:
    """
    Maximum drawdown sur la période.

    Returns:
        float: max drawdown en % (valeur négative)
    """
    dd = compute_drawdown_series(cumulative_pnl)
    return float(dd.min())


# ─── Corrélations ────────────────────────────────────────────────────────────

def compute_correlation_matrix(
    tickers: List[str],
    returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Matrice de corrélation entre les actifs du portefeuille.

    Returns:
        DataFrame: matrice de corrélation (valeurs entre -1 et +1)
    """
    available = [t for t in tickers if t in returns.columns]
    if not available:
        return pd.DataFrame()
    corr = returns[available].corr()
    return corr.round(3)


# ─── Tracking Error ─────────────────────────────────────────────────────────

def compute_tracking_error(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    Tracking Error annualisée.

    Formule: TE = std(R_portfolio - R_benchmark) × √252

    Mesure à quel point le portefeuille diverge de son benchmark.

    Returns:
        float: tracking error en % annualisée
    """
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1).dropna()
    if aligned.empty:
        return 0.0
    excess_returns = aligned.iloc[:, 0] - aligned.iloc[:, 1]
    te = excess_returns.std() * np.sqrt(252)
    return round(float(te) * 100, 2)


# ─── Sharpe & Sortino ────────────────────────────────────────────────────────

def compute_sharpe_ratio(
    portfolio_returns: pd.Series,
    risk_free_rate: float = 0.045,
) -> float:
    """
    Sharpe Ratio annualisé.

    Formule : Sharpe = (R_portfolio - R_rf) / sigma_portfolio × √252

    Mesure le rendement excédentaire par unité de risque total.
    Un Sharpe > 1 est considéré bon, > 2 excellent.

    Args:
        portfolio_returns: série de rendements journaliers
        risk_free_rate:    taux sans risque annualisé (défaut 4.5% = T-bill US 2026)

    Returns:
        float: Sharpe Ratio annualisé
    """
    if portfolio_returns.empty or portfolio_returns.std() == 0:
        return 0.0
    rf_daily = risk_free_rate / 252
    excess   = portfolio_returns - rf_daily
    sharpe   = excess.mean() / excess.std() * np.sqrt(252)
    return round(float(sharpe), 2)


def compute_sortino_ratio(
    portfolio_returns: pd.Series,
    risk_free_rate: float = 0.045,
) -> float:
    """
    Sortino Ratio annualisé.

    Formule : Sortino = (R_portfolio - R_rf) / sigma_downside × √252

    Différence vs Sharpe : utilise uniquement la volatilité des rendements
    négatifs (downside deviation) — ne pénalise pas la volatilité à la hausse.
    Plus pertinent pour les desks qui ont des rendements asymétriques.

    Args:
        portfolio_returns: série de rendements journaliers
        risk_free_rate:    taux sans risque annualisé

    Returns:
        float: Sortino Ratio annualisé
    """
    if portfolio_returns.empty:
        return 0.0
    rf_daily      = risk_free_rate / 252
    excess        = portfolio_returns - rf_daily
    downside      = excess[excess < 0]
    downside_std  = downside.std() * np.sqrt(252)
    if downside_std == 0:
        return 0.0
    sortino = excess.mean() * np.sqrt(252) / downside_std
    return round(float(sortino), 2)


# ─── Risk Report complet ─────────────────────────────────────────────────────

def compute_full_risk_report(
    positions: pd.DataFrame,
    pnl_history: pd.DataFrame,
    returns: pd.DataFrame,
    benchmark_ticker: str = "SPY",
) -> Dict:
    """
    Calcule toutes les métriques de risque en une seule passe.

    Returns:
        dict avec toutes les métriques
    """
    nav = positions["market_value"].sum()
    cfg = config.get("risk", {})

    # VaR
    if not pnl_history.empty and "daily_pnl" in pnl_history.columns:
        pnl_series = pnl_history["daily_pnl"].dropna()
        confidence = cfg.get("var_confidence", 0.95)
        var_hist = compute_var_historical(pnl_series, confidence)
        var_param = compute_var_parametric(pnl_series, confidence)
        var_pct = compute_var_as_pct_of_nav(var_hist, nav)
    else:
        var_hist = var_param = var_pct = 0.0

    # Drawdown — calculé sur la valeur du portefeuille (NAV initiale + PnL cumulatif)
    # pour éviter la division par ~0 quand le PnL démarre près de zéro
    if not pnl_history.empty and "portfolio_pnl" in pnl_history.columns:
        initial_nav = (positions["entry_price"] * positions["quantity"].abs()).sum()
        cum_pnl_col = pnl_history.set_index("Date")["portfolio_pnl"] if "Date" in pnl_history.columns else pnl_history["portfolio_pnl"]
        portfolio_value = cum_pnl_col + initial_nav
        max_dd = compute_max_drawdown(portfolio_value)
    else:
        max_dd = 0.0

    # Volatilité et beta
    portfolio_vol = compute_portfolio_volatility(positions, returns)
    portfolio_beta = compute_portfolio_beta(positions, returns, benchmark_ticker)

    # Tracking error + Sharpe + Sortino
    port_ret = pd.Series(dtype=float)
    if benchmark_ticker in returns.columns and not returns.empty:
        weights = {}
        for _, pos in positions.iterrows():
            t = pos["ticker"]
            w = pos["weight_pct"] / 100.0 * (1 if pos["quantity"] > 0 else -1)
            weights[t] = w
        available = {t: w for t, w in weights.items() if t in returns.columns}
        if available:
            w_s = pd.Series(available)
            port_ret = (returns[list(available.keys())] * w_s).sum(axis=1)
            te = compute_tracking_error(port_ret, returns[benchmark_ticker])
        else:
            te = 0.0
    else:
        te = 0.0

    rf = config.get("risk", {}).get("risk_free_rate", 0.045)
    sharpe  = compute_sharpe_ratio(port_ret, rf)  if not port_ret.empty else 0.0
    sortino = compute_sortino_ratio(port_ret, rf) if not port_ret.empty else 0.0

    return {
        "var_95_historical": var_hist,
        "var_95_parametric": var_param,
        "var_pct_of_nav": var_pct,
        "max_drawdown_pct": max_dd,
        "portfolio_volatility_pct": portfolio_vol,
        "portfolio_beta": portfolio_beta,
        "tracking_error_pct": te,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
    }


# ─── Alertes de risque ───────────────────────────────────────────────────────

def generate_risk_alerts(
    summary: Dict,
    risk_metrics: Dict,
    positions: pd.DataFrame,
) -> List[Dict]:
    """
    Génère des alertes si des seuils de risque sont dépassés.

    Returns:
        liste de dicts {level: 'warning'|'error', message: str}
    """
    alerts_cfg = config.get("alerts", {})
    alerts = []

    # VaR vs NAV
    if risk_metrics.get("var_pct_of_nav", 0) > alerts_cfg.get("var_threshold_pct", 2.0):
        alerts.append({
            "level": "error",
            "message": f"⚠️ VaR ({risk_metrics['var_pct_of_nav']:.1f}%) dépasse le seuil de {alerts_cfg['var_threshold_pct']}%",
        })

    # Drawdown
    dd = abs(risk_metrics.get("max_drawdown_pct", 0))
    if dd > alerts_cfg.get("drawdown_threshold_pct", 5.0):
        alerts.append({
            "level": "warning",
            "message": f"⚠️ Max Drawdown ({dd:.1f}%) dépasse le seuil de {alerts_cfg['drawdown_threshold_pct']}%",
        })

    # Levier
    if summary.get("leverage", 0) > alerts_cfg.get("gross_exposure_max", 2.0):
        alerts.append({
            "level": "warning",
            "message": f"⚠️ Levier ({summary['leverage']:.2f}x) dépasse le maximum autorisé de {alerts_cfg['gross_exposure_max']}x",
        })

    # Concentration
    max_pos_pct = alerts_cfg.get("single_position_max_pct", 40.0)
    for _, pos in positions.iterrows():
        if pos["weight_pct"] > max_pos_pct:
            alerts.append({
                "level": "warning",
                "message": f"⚠️ Position {pos['ticker']} représente {pos['weight_pct']:.1f}% du portefeuille (max: {max_pos_pct}%)",
            })

    if not alerts:
        alerts.append({
            "level": "ok",
            "message": "✅ Toutes les métriques de risque sont dans les limites",
        })

    return alerts
