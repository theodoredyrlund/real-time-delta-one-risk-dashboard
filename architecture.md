# Architecture — Real-Time Delta One Risk Dashboard

## Vue d'ensemble

Ce projet simule l'infrastructure d'un outil de suivi du risque utilisé sur un desk Delta One.
Il couvre l'ingestion de données de marché, le calcul de métriques de risque, et la visualisation
en temps quasi-réel via un dashboard interactif.

---

## Schéma d'architecture MVP

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                   │
│                                                                     │
│  Yahoo Finance API  ──►  market_data.py  ──►  SQLite / PostgreSQL  │
│  (yfinance)               (ingestion)           (stockage)         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      COMPUTATION LAYER                              │
│                                                                     │
│   portfolio.py  ──►  pnl.py  ──►  risk.py  ──►  stress.py         │
│   (positions,        (PnL,         (VaR, vol,     (4 scenarios,    │
│    expositions)       intraday)     beta, correl,   sVaR, custom)  │
│                                     Sharpe/Sortino)                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                               │
│                                                                     │
│   Streamlit Dashboard  (app/dashboard.py)                          │
│   - KPI cards  - PnL chart  - Position table                       │
│   - Correlation heatmap  - VaR gauge  - Alerts                     │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      INFRA LAYER (MVP)                              │
│                                                                     │
│   Docker  ──►  docker-compose  ──►  Local / Cloud deploy           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Cloud cible (AWS)

```
┌─────────────────────────────────────────────────────────────────────┐
│  INGESTION                                                          │
│  Lambda / ECS Task  ──►  Market Data APIs  ──►  S3 (raw data)      │
│                                              ──►  RDS PostgreSQL    │
└─────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────┐
│  STREAMING (version avancée)                                        │
│  AWS Kinesis Data Streams  ──►  Lambda processor  ──►  RDS / Redis │
└─────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────┐
│  COMPUTE                                                            │
│  ECS Fargate (Streamlit app)                                        │
│  ├── app/dashboard.py                                               │
│  ├── src/ (risk engine)                                             │
│  └── env vars via AWS Secrets Manager                               │
└─────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────┐
│  NETWORKING                                                         │
│  ALB (Application Load Balancer)  ──►  Route53 (DNS)               │
│  VPC  ──►  Public subnet (ALB) + Private subnet (ECS, RDS)         │
└─────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────┐
│  IaC                                                                │
│  Terraform  ──►  (VPC, ECS, RDS, S3, IAM, ALB)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Stack technique

| Couche | MVP | Cloud cible |
|---|---|---|
| Données marché | yfinance (Yahoo Finance) | Kinesis + Lambda |
| Calculs risque | Python (pandas, numpy, scipy) | idem |
| Stockage | SQLite | AWS RDS PostgreSQL |
| Données historiques | fichiers CSV locaux | AWS S3 |
| Dashboard | Streamlit | Streamlit on ECS Fargate |
| Containerisation | Docker + docker-compose | ECS Fargate |
| IaC | — | Terraform |
| Cache | — | ElastiCache Redis |
| CI/CD | — | GitHub Actions → ECR → ECS |

---

## Flux de données détaillé

```
[Tick / Prix de marché]
        │
        ▼
  market_data.py
  - fetch_prices(tickers, period)
  - fetch_realtime_price(ticker)
  - store_to_db(df, db_connection)
        │
        ▼
  portfolio.py
  - load_positions()            ← config/portfolio.yaml
  - compute_market_values()     ← prix actuels × quantités
  - compute_exposures()         ← gross / net / geo / sector
        │
        ▼
  pnl.py
  - compute_position_pnl()      ← (prix_actuel - prix_entrée) × qty
  - compute_total_pnl()
  - compute_intraday_pnl()      ← prix_actuel vs open
  - compute_pnl_history()       ← série temporelle
        │
        ▼
  risk.py
  - compute_beta()              ← régression vs SPY
  - compute_rolling_vol()       ← std(returns) × √252
  - compute_var()               ← méthode historique ou paramétrique
  - compute_correlation()       ← matrice de corrélation
  - compute_drawdown()          ← max drawdown glissant
  - compute_tracking_error()    ← std(portfolio_ret - benchmark_ret) × √252
  - compute_sharpe_ratio()      ← (R_ptf - R_rf) / σ × √252
  - compute_sortino_ratio()     ← (R_ptf - R_rf) / σ_downside × √252
        │
        ▼
  stress.py
  - run_all_scenarios()         ← 4 scénarios prédéfinis (Crash, VIX, FX, Rally)
  - build_custom_scenario()     ← chocs manuels via sliders
  - compute_stressed_var()      ← sVaR = VaR paramétrique × vol_multiplier
        │
        ▼
  dashboard.py
  - st.metric()   : KPIs (NAV, PnL, VaR, Sharpe, Sortino, beta…)
  - px.line()     : PnL historique + NAV normalisée vs SPY (base 100)
  - px.bar()      : expositions géo / asset class / PnL attribution
  - px.imshow()   : heatmap corrélation
  - st.dataframe(): table positions colorisée
  - alertes       : dépassement seuils VaR / drawdown / levier / concentration
  - stress        : 4 scénarios + custom sliders + sVaR
```

---

## Formules financières clés

### PnL position
```
PnL_i = (P_current_i − P_entry_i) × Qty_i
```

### Gross / Net Exposure
```
Gross Exposure = Σ |MktValue_i|
Net Exposure   = Σ MktValue_i   (longs positifs, shorts négatifs)
```

### Beta du portefeuille
```
β_portfolio = Σ (w_i × β_i)
β_i = Cov(R_i, R_benchmark) / Var(R_benchmark)
```

### Rolling Volatility (annualisée)
```
σ_rolling = std(R_daily, window=20) × √252
```

### Value at Risk (méthode historique, 95%)
```
VaR_95% = Percentile(P&L_historique, 5%)
```

### Maximum Drawdown
```
Drawdown_t = (P_t − max(P_0..P_t)) / max(P_0..P_t)
MaxDrawdown = min(Drawdown_t)
```

### Tracking Error
```
TE = std(R_portfolio − R_benchmark) × √252
```

### Sharpe Ratio
```
Sharpe = (R_portfolio − R_rf) / σ_portfolio × √252
R_rf = taux sans risque annualisé / 252 (T-bill US, ~4.5%)
```

### Sortino Ratio
```
Sortino = (R_portfolio − R_rf) / σ_downside × √252
σ_downside = std(R_t pour R_t < 0) × √252   (volatilité négative uniquement)
```

### Stressed VaR (sVaR)
```
sVaR = -(μ + z_α × σ × vol_multiplier) × NAV
vol_multiplier : 2.5x (Equity Crash), 2.0x (VIX Spike), 1.3x (FX Shock)
```
