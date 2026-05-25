# CV Description & Interview Guide
# Real-Time Delta One Risk Dashboard

---

## ✅ CV Bullet Points (English)

Choose 2–3 of these depending on the role you're targeting:

### Version complète (pour CV technique / quant)
```
Built a real-time Delta One risk dashboard replicating desk-level risk monitoring:
fetched live market data (SPY, QQQ, EWQ, IWM) via yfinance, computed portfolio PnL,
beta exposure, VaR (historical & parametric), rolling volatility, max drawdown, and
correlation matrices; deployed as a Dockerized Streamlit application designed for
AWS ECS with SQLite/PostgreSQL persistence.
```

### Version courte (pour la plupart des CVs)
```
Developed a cloud-ready Delta One risk dashboard in Python/Streamlit: live PnL tracking,
VaR (95%), portfolio beta, drawdown, and correlation heatmap across a simulated ETF book
(SPY/QQQ/EWQ); containerized with Docker, designed for AWS deployment (ECS, RDS, S3).
```

### Bullet points individuels (pour formater en liste)
```
• Engineered a real-time portfolio risk engine in Python computing PnL, gross/net
  exposure, portfolio beta, historical VaR (95%), rolling volatility (20d), and
  maximum drawdown for a simulated Delta One ETF book (SPY, QQQ, EWQ, IWM).

• Built an interactive Streamlit dashboard displaying live market data, PnL attribution,
  correlation heatmap, geographic/asset-class exposure breakdown, and automated
  risk alerts with configurable thresholds.

• Designed a cloud-native architecture targeting AWS ECS Fargate (app), RDS PostgreSQL
  (database), S3 (historical data), and Kinesis (streaming) with Docker containerization
  and IaC via Terraform.

• Implemented data ingestion pipeline using yfinance with fallback to stochastic
  simulation (GBM) and SQLAlchemy-based persistence layer supporting both SQLite
  (dev) and PostgreSQL (prod).
```

---

## 🎤 Interview Pitch (1 minute)

*Version à mémoriser pour la question "Tell me about a project you've worked on."*

> "I built a real-time risk dashboard that simulates the kind of tool a Delta One desk
> would use to monitor its book. The portfolio contains long and short positions across
> ETFs — SPY, QQQ, and a European proxy — which is typical of a Delta One setup where
> you're running long-short equity trades, hedging via futures, and managing basis risk.
>
> On the data side, the app fetches live prices using Yahoo Finance, then runs a set
> of calculations: PnL per position, gross and net exposure, portfolio beta via OLS
> regression, rolling volatility annualized at √252, Value at Risk using both historical
> and parametric methods, drawdown, and correlation matrices.
>
> Everything feeds into a Streamlit dashboard with auto-refresh — position book,
> PnL chart, geographic exposure, correlation heatmap, and automated risk alerts
> when VaR or drawdown exceed defined thresholds.
>
> For the infrastructure, it's Dockerized and architected for AWS — I designed it
> so you'd deploy the app on ECS Fargate, store data on RDS PostgreSQL, put historical
> data in S3, and eventually use Kinesis for real-time streaming to replace the
> polling approach."

---

## ❓ Questions that could be asked — and how to answer them

---

### "What is a Delta One product?"

> "A Delta One product is a derivative or instrument whose price moves approximately
> one-for-one with the underlying asset — so delta = 1, no convexity, no optionality.
> The classic examples are ETFs, total return swaps (TRS), equity futures, CFDs, and
> index basket replication. Delta One desks make money through financing, dividends,
> and basis trading rather than through directional or volatility bets."

---

### "How did you calculate VaR?"

> "I implemented two methods. The historical method takes the actual distribution of
> daily PnL over the past year and reads off the 5th percentile — so the 95% VaR is
> the loss you'd only exceed 5% of the time historically, without assuming a normal
> distribution. The parametric method assumes normality: VaR = μ + z × σ where z
> is the 1.645 quantile of the normal distribution for 95% confidence. The historical
> method is more conservative when returns have fat tails, which is typically the case
> in equity markets."

---

### "Why use gross vs net exposure?"

> "Net exposure tells you the directional risk — if it's +50% you're net long and
> exposed to market downturns. But a book can be net neutral while running huge
> gross exposure, for example long $10M and short $9M — net $1M but gross $19M.
> Gross exposure is the real measure of leverage and funding risk. On a Delta One
> desk, risk limits are typically set on both: a net limit to control directional
> bias and a gross limit to control leverage."

---

### "What is tracking error and why does it matter here?"

> "Tracking error is the annualized standard deviation of the difference between
> the portfolio's daily returns and the benchmark's returns: TE = std(Rp - Rb) × √252.
> On a Delta One desk that runs an index replication strategy or a basket hedge,
> you want tracking error to be as low as possible — it measures how closely you're
> replicating the benchmark. A high TE means your hedge isn't working and you're
> taking on unintended factor exposures."

---

### "How would you deploy this in production?"

> "In production I'd move from SQLite to RDS PostgreSQL for reliability. The app
> itself would run in a Docker container on ECS Fargate — serverless, so you don't
> manage EC2 instances. Historical data goes to S3. For real-time market data,
> instead of polling Yahoo Finance every minute, you'd connect to a proper data
> vendor — Bloomberg B-PIPE or Refinitiv — and feed prices into Kinesis or Kafka
> for sub-second latency. CI/CD would go through GitHub Actions: on push to main,
> build and push to ECR, then deploy to ECS via a rolling update. Terraform manages
> the entire infrastructure — VPC, subnets, security groups, RDS, ECS cluster."

---

### "What would you add if you had more time?"

> "A few things. First, stress testing — systematic scenarios like a 10% market drop,
> a VIX spike, or a rates shock, to see how the book behaves. Second, a proper trade
> blotter so you can log entries and exits, not just hold static positions. Third,
> futures roll tracking — a real Delta One desk hedges with futures and has to manage
> roll dates. And for the cloud, I'd add Redis caching for the most-requested price
> queries to avoid hammering the data vendor on every dashboard refresh."

---

## 🏷️ Keywords for your CV / LinkedIn

`Python` · `Streamlit` · `Pandas` · `NumPy` · `Financial Risk` · `Value at Risk` ·
`Delta One` · `Portfolio Management` · `Market Data Pipelines` · `Docker` ·
`AWS ECS` · `PostgreSQL` · `Real-Time Data` · `Quantitative Finance` ·
`Risk Analytics` · `ETF` · `Equity Derivatives`
