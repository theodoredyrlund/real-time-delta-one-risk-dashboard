# Roadmap — Real-Time Delta One Risk Dashboard

---

## Phase 1 — MVP ✅ TERMINÉ

**Objectif:** Avoir un dashboard fonctionnel qui tourne localement.

### Étape 1 — Setup
- [x] Créer le repo GitHub avec cette structure
- [x] Créer un virtual environment Python (conda delta1 / Python 3.11)
- [x] `pip install -r requirements.txt`
- [x] yfinance fonctionnel (version 1.4.0+)

### Étape 2 — Market Data
- [x] `src/market_data.py` : fetch_historical_prices, fetch_realtime_prices
- [x] Fallback simulate_price_feed() opérationnel
- [x] Portefeuille : SPY long, TLT short, EWQ long, IWM long

### Étape 3 — Portfolio & PnL
- [x] `config/config.yaml` : entry_price alignés sur les vrais prix marché
- [x] `load_positions()` → `enrich_with_live_prices()` fonctionnel
- [x] `build_pnl_history()` : DataFrame avec portfolio_pnl, daily_pnl

### Étape 4 — Calculs de risque
- [x] 12 tests unitaires passent (`pytest tests/ -v`)
- [x] `compute_full_risk_report()` : VaR, beta, vol, drawdown, TE, Sharpe, Sortino

### Étape 5 — Dashboard
- [x] `streamlit run app/dashboard.py` → localhost:8501
- [x] Tous les graphiques affichés
- [x] Auto-refresh 30s, refresh manuel

### Étape 6 — Docker
- [x] Dockerfile + docker-compose.yml configurés
- [x] `docker-compose up --build` fonctionnel

**Livrable Phase 1:** ✅ Dashboard Streamlit fonctionnel, Dockerisé, testé, sur GitHub.

---

## Phase 2 — Enhanced Features ✅ PARTIELLEMENT TERMINÉ

**Objectif:** Rendre le projet plus riche et plus démontrable.

### Fonctionnalités implémentées
- [x] **Stress testing** : 4 scénarios (Equity Crash, VIX Spike, EUR/USD Shock, Rally) + custom sliders (`src/stress.py`)
- [x] **Sharpe Ratio** : `(R_portfolio - R_rf) / σ_portfolio × √252`
- [x] **Sortino Ratio** : `(R_portfolio - R_rf) / σ_downside × √252`
- [x] **NAV vs Benchmark** : courbe normalisée base 100 vs SPY avec alpha

### À faire
- [ ] **Intraday data** : utiliser `interval="1m"` pour du vrai temps réel
- [ ] **Trade blotter** : historique des entrées/sorties en position
- [ ] **Export** : bouton pour exporter positions + métriques en CSV ou Excel
- [ ] **Alertes email** : notification si VaR dépasse le seuil (via SMTP ou AWS SES)

---

## Phase 3 — Cloud Production (3–4 semaines)

**Objectif:** Déployer sur AWS, infrastructure as code.

### AWS Setup

1. **ECR** : créer un repository Docker
   ```bash
   aws ecr create-repository --repository-name delta-one-dashboard
   ```

2. **ECS Fargate** : créer un cluster et une task definition pointant vers l'image ECR

3. **RDS PostgreSQL** : lancer une instance db.t3.micro, changer `DB_TYPE=postgresql` dans `.env`

4. **S3** : créer un bucket pour stocker les données historiques (CSV quotidiens)

5. **Terraform** : écrire `terraform/main.tf` pour tout provisionner proprement

### Streaming (optionnel mais très impactant)
- Kinesis Data Stream pour ingérer les ticks prix
- Lambda function pour consommer le stream et mettre à jour la base
- Remplace le polling yfinance par du vrai near-real-time

### CI/CD GitHub Actions
```yaml
# .github/workflows/deploy.yml
on: [push]
jobs:
  deploy:
    - Build Docker image
    - Push to ECR
    - Update ECS service (rolling update)
```

---

## Critères de réussite du projet

| Critère | MVP | Phase 2 | Phase 3 |
|---------|-----|---------|---------|
| Dashboard fonctionne en local | ✅ | ✅ | ✅ |
| PnL et risque calculés correctement | ✅ | ✅ | ✅ |
| Tests unitaires passent | ✅ | ✅ | ✅ |
| Docker build réussit | ✅ | ✅ | ✅ |
| Graphiques propres et lisibles | ✅ | ✅ | ✅ |
| Déployé sur AWS | ❌ | ❌ | ✅ |
| URL publique accessible | ❌ | ❌ | ✅ |
| Streaming temps réel | ❌ | Partiel | ✅ |
| Stress tests | ❌ | ✅ | ✅ |

---

## Pour mettre le projet sur GitHub

```bash
git init
git add .
git commit -m "feat: initial MVP — Delta One Risk Dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/real-time-delta-one-risk-dashboard.git
git push -u origin main
```

**Pense à :**
- Ajouter un `.gitignore` (exclure `data/`, `logs/`, `.env`, `__pycache__/`)
- Ajouter des screenshots du dashboard dans le README
- Lier le repo sur ton profil LinkedIn et ton CV
