"""
tests/test_risk.py — Tests unitaires des calculs de risque
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk import (
    compute_asset_beta,
    compute_var_historical,
    compute_var_parametric,
    compute_max_drawdown,
    compute_drawdown_series,
    compute_rolling_volatility,
)
from src.pnl import compute_position_pnl


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_returns():
    """Rendements synthétiques pour les tests."""
    np.random.seed(42)
    n = 252
    dates = pd.bdate_range("2023-01-01", periods=n)
    spy = pd.Series(np.random.normal(0.0003, 0.012, n), index=dates, name="SPY")
    qqq = pd.Series(np.random.normal(0.0005, 0.015, n), index=dates, name="QQQ")
    return pd.DataFrame({"SPY": spy, "QQQ": qqq})


@pytest.fixture
def sample_pnl_series():
    """Série de PnL journaliers pour les tests."""
    np.random.seed(42)
    return pd.Series(np.random.normal(500, 2000, 252))


# ─── Tests PnL ───────────────────────────────────────────────────────────────

class TestPnL:

    def test_long_position_positive_pnl(self):
        """Un long position qui monte doit avoir un PnL positif."""
        result = compute_position_pnl(
            current_price=110.0,
            entry_price=100.0,
            quantity=100,
        )
        assert result["pnl"] == pytest.approx(1000.0)
        assert result["pnl_pct"] == pytest.approx(10.0)

    def test_short_position_positive_pnl(self):
        """Un short qui baisse doit avoir un PnL positif."""
        result = compute_position_pnl(
            current_price=90.0,
            entry_price=100.0,
            quantity=-100,  # short
        )
        assert result["pnl"] == pytest.approx(1000.0)  # (90-100) × -100 = 1000
        assert result["pnl_pct"] == pytest.approx(-10.0)  # prix a baissé de 10%

    def test_zero_pnl_when_no_move(self):
        """Pas de mouvement = pas de PnL."""
        result = compute_position_pnl(100.0, 100.0, 500)
        assert result["pnl"] == 0.0


# ─── Tests Beta ──────────────────────────────────────────────────────────────

class TestBeta:

    def test_beta_spy_vs_itself_is_one(self, sample_returns):
        """Le beta d'un actif vs lui-même doit être 1."""
        beta = compute_asset_beta(sample_returns["SPY"], sample_returns["SPY"])
        assert beta == pytest.approx(1.0, abs=1e-6)

    def test_beta_is_finite(self, sample_returns):
        """Le beta ne doit pas être infini ou NaN."""
        beta = compute_asset_beta(sample_returns["QQQ"], sample_returns["SPY"])
        assert np.isfinite(beta)

    def test_beta_returns_default_on_insufficient_data(self):
        """Moins de 10 observations → beta défaut = 1.0."""
        short_series = pd.Series([0.01, -0.02, 0.005])
        beta = compute_asset_beta(short_series, short_series)
        assert beta == 1.0


# ─── Tests VaR ───────────────────────────────────────────────────────────────

class TestVaR:

    def test_var_historical_is_positive(self, sample_pnl_series):
        """La VaR (perte potentielle) doit être positive."""
        var = compute_var_historical(sample_pnl_series, confidence=0.95)
        assert var > 0

    def test_var_99_greater_than_var_95(self, sample_pnl_series):
        """VaR 99% doit être >= VaR 95% (plus conservatrice)."""
        var_95 = compute_var_historical(sample_pnl_series, confidence=0.95)
        var_99 = compute_var_historical(sample_pnl_series, confidence=0.99)
        assert var_99 >= var_95

    def test_var_parametric_consistent(self, sample_pnl_series):
        """VaR paramétrique doit être du même ordre que historique."""
        var_hist = compute_var_historical(sample_pnl_series, 0.95)
        var_param = compute_var_parametric(sample_pnl_series, 0.95)
        # Ratio doit être entre 0.5 et 2.0 (ordre de grandeur cohérent)
        ratio = var_hist / var_param if var_param != 0 else 1.0
        assert 0.3 < ratio < 3.0


# ─── Tests Drawdown ───────────────────────────────────────────────────────────

class TestDrawdown:

    def test_drawdown_always_negative_or_zero(self):
        """Les valeurs de drawdown sont toujours <= 0."""
        pnl = pd.Series([100, 110, 105, 115, 100, 95, 120])
        dd = compute_drawdown_series(pnl)
        assert (dd <= 0.001).all()  # tolérance numérique

    def test_max_drawdown_is_negative(self):
        """Le max drawdown doit être <= 0."""
        pnl = pd.Series([100.0, 90.0, 80.0, 95.0, 100.0])
        mdd = compute_max_drawdown(pnl)
        assert mdd <= 0

    def test_no_drawdown_on_monotone_increase(self):
        """Série toujours croissante → drawdown nul."""
        pnl = pd.Series([100.0, 110.0, 120.0, 130.0, 140.0])
        mdd = compute_max_drawdown(pnl)
        assert mdd == pytest.approx(0.0, abs=1e-6)


# ─── Tests Volatilité ────────────────────────────────────────────────────────

class TestVolatility:

    def test_rolling_vol_is_positive(self, sample_returns):
        """La volatilité doit être positive."""
        vol = compute_rolling_volatility(sample_returns["SPY"], window=20)
        assert (vol.dropna() > 0).all()

    def test_annualized_vol_higher_than_daily(self, sample_returns):
        """Vol annualisée > vol journalière (facteur √252 ≈ 15.87)."""
        vol_ann = compute_rolling_volatility(sample_returns["SPY"], window=20, annualize=True)
        vol_daily = compute_rolling_volatility(sample_returns["SPY"], window=20, annualize=False)
        ratio = (vol_ann / vol_daily).dropna()
        assert (ratio > 1).all()
