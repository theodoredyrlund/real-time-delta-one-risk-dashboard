# Roadmap — Real-Time Delta One Risk Dashboard

---

## Phase 1 — MVP (2–3 semaines) 🎯 START HERE

**Objectif:** Avoir un dashboard fonctionnel qui tourne localement.

### Étape 1 — Setup (Jour 1)
- [ ] Créer le repo GitHub avec cette structure
- [ ] Créer un virtual environment Python
- [ ] `pip install -r requirements.txt`
- [ ] Tester que `yfinance` fonctionne : `python -c "import yfinance as yf; print(yf.Ticker('SPY').fast_info.last_price)"`

### Étape 2 — Market Data (Jour 1–2)
- [ ] Tester `src/market_data.py` : `fetch_historical_prices(["SPY", "QQQ"])`
- [ ] Vérifier que `fetch_realtime_prices()` retourne des prix cohérents
- [ ] Tester le fallback `simulate_price_feed()` (utile le week-end ou hors marché)

### Étape 3 — Portfolio & PnL (Jour 2–3)
- [ ] Vérifier `config/config.yaml` : ajuster les `entry_price` aux prix réels actuels
- [ ] Tester `load_positions()` → `enrich_with_live_prices()`
- [ ] Tester `build_pnl_history()` : doit retourner un DataFrame avec `portfolio_pnl`

### Étape 4 — Calculs de risque (Jour 3–4)
- [ ] Lancer les tests : `pytest tests/ -v`
- [ ] Tester `compute_full_risk_report()` sur des données réelles
- [ ] Vérifier que la VaR, le beta et la vol ont des valeurs sensées

### Étape 5 — Dashboard (Jour 4–5)
- [ ] `streamlit run app/dashboard.py`
- [ ] Vérifier que tous les graphiques s'affichent
- [ ] Tester le refresh manuel
- [ ] Ajuster les couleurs et la mise en page si nécessaire

### Étape 6 — Docker (Jour 5–6)
- [ ] `docker build -t delta-one-dashboard .`
- [ ] `docker run -p 8501:8501 delta-one-dashboard`
- [ ] Vérifier que le dashboard fonctionne dans le conteneur

**Livrable Phase 1:** Dashboard Streamlit fonctionnel, Dockerisé, testé.

---

## Phase 2 — Enhanced Features (2–3 semaines)

**Objectif:** Rendre le projet plus riche et plus démontrable.

### Fonctionnalités à ajouter

- [ ] **Intraday data** : utiliser `interval="1m"` pour du vrai temps réel
- [ ] **Stress testing** : scénario -10% marché, spike VIX, shock EUR/USD
- [ ] **Trade blotter** : historique des entrées/sorties en position
- [ ] **Export** : bouton pour exporter positions + métriques en CSV ou Excel
- [ ] **Alertes email** : notification si VaR dépasse le seuil (via SMTP ou AWS SES)
- [ ] **Greeks proxy** : calculer le delta pondéré du portefeuille vs SPY/STOXX
- [ ] **Performance chart** : courbe NAV normalisée vs benchmark (type "depuis le début")
- [ ] **Sharpe Ratio** : `(R_portfolio - R_rf) / σ_portfolio` annualisé

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
