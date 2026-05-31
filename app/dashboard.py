"""
dashboard.py — Dashboard principal Streamlit
Real-Time Delta One Risk Dashboard

Interface professionnelle simulant un outil de suivi du risque
utilisé sur un desk Delta One.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
from datetime import datetime

# ─── Path setup ─────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils import load_config, now_london, market_is_open, fmt_currency, fmt_pct
from src.market_data import fetch_historical_prices, fetch_daily_returns
from src.portfolio import (
    load_positions,
    enrich_with_live_prices,
    compute_gross_exposure,
    compute_net_exposure,
    compute_exposure_by_geography,
    compute_exposure_by_asset_class,
    get_portfolio_summary,
    get_top_movers,
)
from src.pnl import build_pnl_history, compute_pnl_attribution
from src.risk import (
    compute_correlation_matrix,
    compute_full_risk_report,
    generate_risk_alerts,
    compute_drawdown_series,
)
from src.stress import (
    SCENARIOS,
    run_all_scenarios,
    build_custom_scenario,
)

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Delta One Risk Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

config = load_config()

# ─── CSS personnalisé (style desk trading) ──────────────────────────────────
st.markdown("""
<style>
    /* Fond sombre type terminal */
    .stApp { background-color: #0e1117; }
    .main .block-container { padding-top: 1rem; padding-bottom: 1rem; }

    /* KPI cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a1f2e 0%, #1e2435 100%);
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 12px 16px;
    }

    /* Titres de section */
    .section-title {
        font-size: 14px;
        font-weight: 600;
        color: #a0aec0;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        border-bottom: 1px solid #2d3748;
        padding-bottom: 6px;
        margin-bottom: 12px;
    }

    /* Alert boxes */
    .alert-error {
        background: rgba(229, 62, 62, 0.15);
        border-left: 3px solid #e53e3e;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 4px 0;
        color: #fc8181;
    }
    .alert-warning {
        background: rgba(237, 137, 54, 0.15);
        border-left: 3px solid #ed8936;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 4px 0;
        color: #f6ad55;
    }
    .alert-ok {
        background: rgba(72, 187, 120, 0.15);
        border-left: 3px solid #48bb78;
        padding: 8px 12px;
        border-radius: 4px;
        margin: 4px 0;
        color: #68d391;
    }

    /* Live badge */
    .live-badge {
        display: inline-block;
        background: #48bb78;
        color: #0e1117;
        font-size: 10px;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 3px;
        margin-left: 8px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Controls")

    refresh = st.selectbox(
        "Refresh interval",
        ["Manual", "30s", "60s", "5min"],
        index=1,
    )

    st.markdown("---")
    st.markdown("**Data settings**")
    hist_period = st.selectbox(
        "Historical period",
        ["1mo", "3mo", "6mo", "1y"],
        index=1,
    )
    benchmark = st.selectbox(
        "Benchmark",
        ["SPY", "^GSPC", "QQQ"],
        index=0,
    )

    st.markdown("---")
    st.markdown("**View**")
    show_raw_data = st.checkbox("Show raw data tables", value=False)

    st.markdown("---")

    # Status marché
    is_open = market_is_open()
    market_status = "🟢 MARKET OPEN" if is_open else "🔴 MARKET CLOSED"
    st.markdown(f"**{market_status}**")
    st.markdown(f"London: `{now_london().strftime('%H:%M:%S')}`")
    st.markdown(f"Updated: `{datetime.utcnow().strftime('%H:%M:%S')} UTC`")

    if st.button("🔄 Refresh Now", use_container_width=True):
        st.cache_data.clear()


# ─── Data loading (avec cache) ───────────────────────────────────────────────
@st.cache_data(ttl=55)
def load_all_data(period: str, bench: str):
    """Charge toutes les données avec cache de 55 secondes."""
    positions_raw = load_positions()
    positions = enrich_with_live_prices(positions_raw)

    tickers = positions["ticker"].tolist()
    if bench not in tickers:
        all_tickers = tickers + [bench]
    else:
        all_tickers = tickers

    returns = fetch_daily_returns(all_tickers, period=period)
    pnl_hist = build_pnl_history(positions, period=period)
    summary = get_portfolio_summary(positions)

    risk_metrics = compute_full_risk_report(
        positions, pnl_hist, returns, benchmark_ticker=bench
    )
    alerts = generate_risk_alerts(summary, risk_metrics, positions)
    geo_exp = compute_exposure_by_geography(positions)
    ac_exp = compute_exposure_by_asset_class(positions)
    corr_matrix = compute_correlation_matrix(tickers, returns)
    pnl_attr = compute_pnl_attribution(positions)
    top_movers = get_top_movers(positions)

    # ── Courbe NAV normalisée vs benchmark ──────────────────────────────────
    # Normalise les deux séries à 100 au début de la période
    # pour comparer les performances sur la même base
    nav_vs_bench = pd.DataFrame()
    if not pnl_hist.empty and "portfolio_pnl" in pnl_hist.columns:
        date_col = "Date" if "Date" in pnl_hist.columns else pnl_hist.columns[0]
        initial_nav = (positions["entry_price"] * positions["quantity"].abs()).sum()
        portfolio_values = pnl_hist.set_index(date_col)["portfolio_pnl"] + initial_nav
        nav_norm = portfolio_values / portfolio_values.iloc[0] * 100

        if bench in returns.columns:
            bench_prices = (1 + returns[bench]).cumprod() * 100
            bench_prices.index = returns.index
            combined = pd.DataFrame({
                "Portfolio": nav_norm,
                bench: bench_prices,
            }).dropna()
            nav_vs_bench = combined.reset_index()

    return {
        "positions": positions,
        "returns": returns,
        "pnl_hist": pnl_hist,
        "summary": summary,
        "risk_metrics": risk_metrics,
        "alerts": alerts,
        "geo_exp": geo_exp,
        "ac_exp": ac_exp,
        "corr_matrix": corr_matrix,
        "pnl_attr": pnl_attr,
        "top_movers": top_movers,
        "nav_vs_bench": nav_vs_bench,
    }


# ─── Chargement ─────────────────────────────────────────────────────────────
with st.spinner("Fetching market data..."):
    data = load_all_data(hist_period, benchmark)

pos = data["positions"]
summary = data["summary"]
risk = data["risk_metrics"]
pnl_hist = data["pnl_hist"]

# ─── Header ─────────────────────────────────────────────────────────────────
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown(
        f"# 📊 Delta One Risk Dashboard"
        f'<span class="live-badge">{"LIVE" if market_is_open() else "EOD"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(f"*Simulated Delta One desk portfolio — {datetime.utcnow().strftime('%A %d %B %Y')}*")

with col_status:
    st.markdown("")
    total_pnl = summary["total_pnl"]
    pnl_color = "🟢" if total_pnl >= 0 else "🔴"
    st.metric(
        "Total PnL",
        fmt_currency(total_pnl),
        delta=fmt_currency(summary["intraday_pnl"]) + " today",
    )

st.markdown("---")

# ─── Section 1 : KPI Row ────────────────────────────────────────────────────
st.markdown('<p class="section-title">📈 Portfolio Summary</p>', unsafe_allow_html=True)

kpi_cols = st.columns(8)

kpis = [
    ("NAV", fmt_currency(summary["nav"]), None),
    ("Total PnL", fmt_currency(summary["total_pnl"]), fmt_currency(summary["intraday_pnl"])),
    ("Intraday PnL", fmt_currency(summary["intraday_pnl"]), None),
    ("Gross Exp.", fmt_currency(summary["gross_exposure"]), None),
    ("Net Exp.", fmt_currency(summary["net_exposure"]), None),
    ("Leverage", f"{summary['leverage']:.2f}×", None),
    ("Positions", str(summary["n_positions"]), f"{summary['n_long']}L / {summary['n_short']}S"),
    ("Portfolio β", f"{risk.get('portfolio_beta', 0):.2f}", None),
]

for col, (label, value, delta) in zip(kpi_cols, kpis):
    with col:
        if delta:
            st.metric(label, value, delta=delta)
        else:
            st.metric(label, value)

# ─── Section 2 : Risk KPIs ──────────────────────────────────────────────────
st.markdown("")
risk_cols = st.columns(6)

sharpe  = risk.get("sharpe_ratio", 0)
sortino = risk.get("sortino_ratio", 0)

risk_kpis = [
    ("VaR 95% (hist.)", fmt_currency(risk.get("var_95_historical", 0)),
     f"{risk.get('var_pct_of_nav', 0):.2f}% of NAV"),
    ("Max Drawdown", f"{risk.get('max_drawdown_pct', 0):.2f}%", None),
    ("Ann. Volatility", f"{risk.get('portfolio_volatility_pct', 0):.2f}%", None),
    ("Tracking Error", f"{risk.get('tracking_error_pct', 0):.2f}%", f"vs {benchmark}"),
    ("Sharpe Ratio",  f"{sharpe:.2f}",
     "✅ Good" if sharpe > 1 else ("⚠️ Low" if sharpe > 0 else "🔴 Negative")),
    ("Sortino Ratio", f"{sortino:.2f}",
     "✅ Good" if sortino > 1 else ("⚠️ Low" if sortino > 0 else "🔴 Negative")),
]

for col, (label, value, delta) in zip(risk_cols, risk_kpis):
    with col:
        if delta:
            st.metric(label, value, delta=delta)
        else:
            st.metric(label, value)

st.markdown("---")

# ─── Section 3 : PnL Chart + Alerts ────────────────────────────────────────
left_col, right_col = st.columns([3, 1])

with left_col:
    st.markdown('<p class="section-title">📉 PnL History</p>', unsafe_allow_html=True)

    if not pnl_hist.empty:
        date_col = "Date" if "Date" in pnl_hist.columns else pnl_hist.columns[0]
        fig_pnl = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.7, 0.3],
            vertical_spacing=0.03,
        )

        # Courbe PnL cumulatif
        colors = ["#48bb78" if v >= 0 else "#fc8181" for v in pnl_hist["portfolio_pnl"]]
        fig_pnl.add_trace(
            go.Scatter(
                x=pnl_hist[date_col],
                y=pnl_hist["portfolio_pnl"],
                mode="lines",
                name="Cumulative PnL",
                line=dict(color="#4299e1", width=2),
                fill="tozeroy",
                fillcolor="rgba(66, 153, 225, 0.1)",
            ),
            row=1, col=1,
        )

        # Barres PnL journalier
        fig_pnl.add_trace(
            go.Bar(
                x=pnl_hist[date_col],
                y=pnl_hist["daily_pnl"],
                name="Daily PnL",
                marker_color=[
                    "#48bb78" if v >= 0 else "#fc8181"
                    for v in pnl_hist["daily_pnl"].fillna(0)
                ],
                opacity=0.8,
            ),
            row=2, col=1,
        )

        fig_pnl.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            height=350,
            showlegend=True,
            legend=dict(orientation="h", y=1.05),
            margin=dict(l=0, r=0, t=20, b=0),
        )
        fig_pnl.update_yaxes(gridcolor="#1a1f2e", zeroline=True, zerolinecolor="#2d3748")
        fig_pnl.update_xaxes(gridcolor="#1a1f2e")
        st.plotly_chart(fig_pnl, use_container_width=True)
    else:
        st.info("No PnL history available. Data will populate as the app runs.")

with right_col:
    st.markdown('<p class="section-title">🚨 Risk Alerts</p>', unsafe_allow_html=True)
    for alert in data["alerts"]:
        level = alert["level"]
        msg = alert["message"]
        st.markdown(f'<div class="alert-{level}">{msg}</div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown('<p class="section-title">🏃 Top Movers</p>', unsafe_allow_html=True)
    top_m = data["top_movers"]
    if not top_m.empty:
        for _, row in top_m.iterrows():
            sign = "▲" if row["intraday_pct"] >= 0 else "▼"
            color = "#48bb78" if row["intraday_pct"] >= 0 else "#fc8181"
            st.markdown(
                f'<span style="color:{color}">{sign} <b>{row["ticker"]}</b>: '
                f'{row["intraday_pct"]:+.2f}%</span>',
                unsafe_allow_html=True,
            )

st.markdown("---")

# ─── Section 3b : NAV normalisée vs Benchmark ───────────────────────────────
st.markdown('<p class="section-title">📈 Portfolio vs Benchmark (Base 100)</p>', unsafe_allow_html=True)

nav_vs_bench = data.get("nav_vs_bench", pd.DataFrame())

if not nav_vs_bench.empty:
    date_col_nb = nav_vs_bench.columns[0]
    portfolio_final  = nav_vs_bench["Portfolio"].iloc[-1]
    bench_final      = nav_vs_bench[benchmark].iloc[-1]
    port_perf        = portfolio_final - 100
    bench_perf       = bench_final - 100
    outperf          = port_perf - bench_perf

    # KPIs de performance relative
    kp1, kp2, kp3 = st.columns(3)
    kp1.metric("Portfolio Return", f"{port_perf:+.2f}%",
               delta=f"Base 100 → {portfolio_final:.1f}")
    kp2.metric(f"{benchmark} Return", f"{bench_perf:+.2f}%",
               delta=f"Base 100 → {bench_final:.1f}")
    kp3.metric("Alpha (vs Benchmark)", f"{outperf:+.2f}%",
               delta="outperforming" if outperf >= 0 else "underperforming")

    # Graphique
    fig_nav = go.Figure()
    fig_nav.add_trace(go.Scatter(
        x=nav_vs_bench[date_col_nb],
        y=nav_vs_bench["Portfolio"],
        name="Portfolio",
        line=dict(color="#4299e1", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(66,153,225,0.05)",
    ))
    fig_nav.add_trace(go.Scatter(
        x=nav_vs_bench[date_col_nb],
        y=nav_vs_bench[benchmark],
        name=benchmark,
        line=dict(color="#ed8936", width=2, dash="dot"),
    ))
    fig_nav.add_hline(
        y=100, line_dash="dash",
        line_color="#4a5568", line_width=1,
        annotation_text="Inception (Base 100)",
        annotation_position="bottom right",
        annotation_font_color="#718096",
    )
    fig_nav.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        height=300,
        showlegend=True,
        legend=dict(orientation="h", y=1.05),
        margin=dict(l=0, r=0, t=20, b=0),
        yaxis=dict(gridcolor="#1a1f2e", ticksuffix=""),
        xaxis=dict(gridcolor="#1a1f2e"),
        hovermode="x unified",
    )
    st.plotly_chart(fig_nav, use_container_width=True)
else:
    st.info("NAV chart requires PnL history data.")

st.markdown("---")

# ─── Section 4 : Positions Table ────────────────────────────────────────────
st.markdown('<p class="section-title">📋 Position Book</p>', unsafe_allow_html=True)

display_cols = [
    "ticker", "name", "side", "quantity", "entry_price",
    "current_price", "market_value", "pnl", "pnl_pct", "weight_pct",
]
pos_display = pos[display_cols].copy()
pos_display.columns = [
    "Ticker", "Name", "Side", "Qty", "Entry Price",
    "Current Price", "Market Value ($)", "PnL ($)", "PnL (%)", "Weight (%)",
]

# Colorisation conditionnelle
def color_pnl(val):
    try:
        color = "#48bb78" if float(val) >= 0 else "#fc8181"
        return f"color: {color}"
    except Exception:
        return ""

styled = pos_display.style\
    .applymap(color_pnl, subset=["PnL ($)", "PnL (%)"])\
    .format({
        "Qty": "{:,.0f}",
        "Entry Price": "{:.2f}",
        "Current Price": "{:.2f}",
        "Market Value ($)": "${:,.0f}",
        "PnL ($)": "${:,.0f}",
        "PnL (%)": "{:+.2f}%",
        "Weight (%)": "{:.1f}%",
    })

st.dataframe(styled, use_container_width=True, height=200)

st.markdown("---")

# ─── Section 5 : Expositions + Corrélation ───────────────────────────────────
exp_col1, exp_col2, exp_col3 = st.columns(3)

with exp_col1:
    st.markdown('<p class="section-title">🌍 Geographic Exposure</p>', unsafe_allow_html=True)
    geo = data["geo_exp"]
    if not geo.empty:
        fig_geo = px.bar(
            geo,
            x="geography",
            y="net_exposure",
            color="net_exposure",
            color_continuous_scale=["#fc8181", "#a0aec0", "#48bb78"],
            text_auto=".2s",
            template="plotly_dark",
        )
        fig_geo.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            height=220,
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_geo, use_container_width=True)

with exp_col2:
    st.markdown('<p class="section-title">🏦 Asset Class Exposure</p>', unsafe_allow_html=True)
    ac = data["ac_exp"]
    if not ac.empty:
        fig_ac = px.pie(
            ac,
            values="gross_exposure",
            names="asset_class",
            color_discrete_sequence=px.colors.sequential.Blues_r,
            template="plotly_dark",
            hole=0.4,
        )
        fig_ac.update_layout(
            paper_bgcolor="#0e1117",
            height=220,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(font=dict(size=10)),
        )
        st.plotly_chart(fig_ac, use_container_width=True)

with exp_col3:
    st.markdown('<p class="section-title">📊 PnL Attribution</p>', unsafe_allow_html=True)
    attr = data["pnl_attr"]
    if not attr.empty:
        fig_attr = px.bar(
            attr.sort_values("pnl"),
            x="pnl",
            y="ticker",
            orientation="h",
            color="pnl",
            color_continuous_scale=["#fc8181", "#a0aec0", "#48bb78"],
            template="plotly_dark",
            text_auto=".2s",
        )
        fig_attr.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            height=220,
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_attr, use_container_width=True)

st.markdown("---")

# ─── Section 6 : Heatmap corrélation + Drawdown ─────────────────────────────
hm_col, dd_col = st.columns(2)

with hm_col:
    st.markdown('<p class="section-title">🔗 Correlation Matrix</p>', unsafe_allow_html=True)
    corr = data["corr_matrix"]
    if not corr.empty:
        fig_corr = px.imshow(
            corr,
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1,
            text_auto=".2f",
            template="plotly_dark",
            aspect="auto",
        )
        fig_corr.update_layout(
            paper_bgcolor="#0e1117",
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        fig_corr.update_traces(textfont=dict(size=11))
        st.plotly_chart(fig_corr, use_container_width=True)

with dd_col:
    st.markdown('<p class="section-title">📉 Drawdown</p>', unsafe_allow_html=True)
    if not pnl_hist.empty and "portfolio_pnl" in pnl_hist.columns:
        # Utilise la valeur du portefeuille (NAV initiale + PnL cumulatif)
        # pour éviter la division par ~0 qui exploserait le ratio
        initial_nav = (pos["entry_price"] * pos["quantity"].abs()).sum()
        date_col_dd = "Date" if "Date" in pnl_hist.columns else pnl_hist.columns[0]
        portfolio_value = pnl_hist.set_index(date_col_dd)["portfolio_pnl"] + initial_nav
        dd_series = compute_drawdown_series(portfolio_value)
        dd_df = dd_series.reset_index()
        dd_df.columns = ["Date", "Drawdown (%)"]

        fig_dd = go.Figure(
            go.Scatter(
                x=dd_df["Date"],
                y=dd_df["Drawdown (%)"],
                fill="tozeroy",
                mode="lines",
                line=dict(color="#fc8181", width=1.5),
                fillcolor="rgba(252, 129, 129, 0.2)",
                name="Drawdown",
            )
        )
        fig_dd.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            height=320,
            showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
        )
        fig_dd.update_yaxes(gridcolor="#1a1f2e", ticksuffix="%")
        fig_dd.update_xaxes(gridcolor="#1a1f2e")
        st.plotly_chart(fig_dd, use_container_width=True)
    else:
        st.info("Drawdown chart requires PnL history.")

st.markdown("---")

# ─── Section 7 : Stress Testing ─────────────────────────────────────────────
st.markdown('<p class="section-title">⚡ Stress Testing & Scenario Analysis</p>', unsafe_allow_html=True)
st.markdown(
    "<small style='color:#a0aec0'>Simule l'impact de chocs de marché sur le portefeuille. "
    "Méthode : choc appliqué sur les prix actuels + VaR stressée (σ × vol multiplier).</small>",
    unsafe_allow_html=True,
)

# Calcule tous les scénarios
scenario_results = run_all_scenarios(pos, data["returns"])
nav = summary["nav"]

# ── Tableau récapitulatif des scénarios ──────────────────────────────────────
current_total_pnl = summary["total_pnl"]

scenario_rows = []
for r in scenario_results:
    scenario_rows.append({
        "Scenario":           r["scenario"],
        "PnL Impact ($)":     r["pnl_impact"],
        "PnL Impact (% NAV)": r["pnl_impact_pct"],
        "PnL After Shock ($)": current_total_pnl + r["pnl_impact"],   # ← corrigé
        "Stressed VaR ($)":   r["stressed_var"],
        "Worst Position":     f"{r['worst_position']} (${r['worst_pnl_impact']:,.0f})",
        "Vol Multiplier":     f"{r['vol_multiplier']}×",
    })
scenario_df = pd.DataFrame(scenario_rows)

def color_impact(val):
    try:
        color = "#48bb78" if float(val) >= 0 else "#fc8181"
        return f"color: {color}; font-weight: bold"
    except Exception:
        return ""

styled_scenarios = scenario_df.style\
    .applymap(color_impact, subset=["PnL Impact ($)", "PnL Impact (% NAV)", "PnL After Shock ($)"])\
    .format({
        "PnL Impact ($)":      "${:,.0f}",
        "PnL Impact (% NAV)":  "{:+.2f}%",
        "PnL After Shock ($)": "${:,.0f}",
        "Stressed VaR ($)":    "${:,.0f}",
    })

st.dataframe(styled_scenarios, use_container_width=True, height=185)

# ── Graphique waterfall PnL impact par scénario ──────────────────────────────
fig_stress = go.Figure(go.Bar(
    x=[r["scenario"] for r in scenario_results],
    y=[r["pnl_impact"] for r in scenario_results],
    marker_color=["#fc8181" if r["pnl_impact"] < 0 else "#48bb78" for r in scenario_results],
    text=[f"${r['pnl_impact']:,.0f}" for r in scenario_results],
    textposition="outside",
))
fig_stress.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0e1117",
    plot_bgcolor="#0e1117",
    height=280,
    showlegend=False,
    title=dict(text="PnL Impact by Scenario ($)", font=dict(size=12, color="#a0aec0"), x=0),
    margin=dict(l=0, r=0, t=40, b=0),
    yaxis=dict(gridcolor="#1a1f2e", zeroline=True, zerolinecolor="#4a5568"),
    xaxis=dict(gridcolor="#1a1f2e"),
)
st.plotly_chart(fig_stress, use_container_width=True)

# ── Détail par scénario (expandable) ─────────────────────────────────────────
st.markdown("**Détail par scénario**")
cols_detail = st.columns(len(scenario_results))
for col, r in zip(cols_detail, scenario_results):
    with col:
        color = "#fc8181" if r["pnl_impact"] < 0 else "#48bb78"
        st.markdown(
            f"<div style='background:#1a1f2e; border:1px solid #2d3748; border-radius:8px; padding:10px;'>"
            f"<div style='font-size:11px; color:#a0aec0; margin-bottom:4px'>{r['scenario']}</div>"
            f"<div style='font-size:16px; font-weight:bold; color:{color}'>${r['pnl_impact']:,.0f}</div>"
            f"<div style='font-size:10px; color:#718096'>{r['pnl_impact_pct']:+.2f}% of NAV</div>"
            f"<div style='font-size:10px; color:#718096; margin-top:4px'>sVaR: ${r['stressed_var']:,.0f}</div>"
            f"<div style='font-size:10px; color:#fc8181; margin-top:2px'>↓ {r['worst_position']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

st.markdown("")

# ── Scénario personnalisé ─────────────────────────────────────────────────────
with st.expander("⚙️ Custom Scenario — définir tes propres chocs"):
    st.markdown("<small style='color:#a0aec0'>Ajuste le choc % sur chaque ticker et observe l'impact en temps réel.</small>", unsafe_allow_html=True)

    tickers_pos = pos["ticker"].tolist()
    custom_shocks = {}
    shock_cols = st.columns(len(tickers_pos))
    for col, ticker in zip(shock_cols, tickers_pos):
        with col:
            shock = col.slider(
                f"{ticker} (%)",
                min_value=-30, max_value=30, value=0, step=1,
                key=f"shock_{ticker}",
            )
            custom_shocks[ticker] = shock / 100.0

    vol_mult = st.slider("Vol Multiplier", min_value=0.5, max_value=4.0, value=1.0, step=0.1)

    custom_result = build_custom_scenario(pos, data["returns"], custom_shocks, vol_mult)
    pnl_color = "#48bb78" if custom_result["pnl_impact"] >= 0 else "#fc8181"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PnL Impact", f"${custom_result['pnl_impact']:,.0f}",
              delta=f"{custom_result['pnl_impact_pct']:+.2f}% of NAV")
    c2.metric("Stressed PnL", f"${custom_result['total_stressed_pnl']:,.0f}")
    c3.metric("Stressed VaR", f"${custom_result['stressed_var']:,.0f}")
    c4.metric("Stressed Net Exp.", f"${custom_result['stressed_net']:,.0f}")

    # Détail par position du scénario custom
    stress_detail = custom_result["stressed_positions"][[
        "ticker", "current_price", "stressed_price", "shock_pct",
        "pnl", "stressed_pnl", "pnl_impact"
    ]].copy()
    stress_detail.columns = [
        "Ticker", "Current Price", "Stressed Price", "Shock (%)",
        "Current PnL ($)", "Stressed PnL ($)", "PnL Impact ($)"
    ]
    st.dataframe(
        stress_detail.style
        .applymap(color_impact, subset=["PnL Impact ($)"])
        .format({
            "Current Price": "{:.2f}", "Stressed Price": "{:.2f}",
            "Shock (%)": "{:+.1%}",
            "Current PnL ($)": "${:,.0f}",
            "Stressed PnL ($)": "${:,.0f}",
            "PnL Impact ($)": "${:,.0f}",
        }),
        use_container_width=True,
        height=180,
    )

st.markdown("---")

# ─── Section 9 : Raw data (optionnel) ───────────────────────────────────────
if show_raw_data:
    st.markdown('<p class="section-title">🔍 Raw Data</p>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["Positions", "PnL History", "Returns"])
    with tab1:
        st.dataframe(pos, use_container_width=True)
    with tab2:
        st.dataframe(pnl_hist, use_container_width=True)
    with tab3:
        st.dataframe(data["returns"].tail(20), use_container_width=True)

# ─── Footer ─────────────────────────────────────────────────────────────────
st.markdown(
    '<p style="text-align:center; color:#4a5568; font-size:12px;">'
    "Delta One Risk Dashboard · Portfolio project · Data: Yahoo Finance (yfinance) · "
    "For demonstration purposes only — not financial advice."
    "</p>",
    unsafe_allow_html=True,
)
