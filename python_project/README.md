# 📘 README.md

---

# 📊 Portfolio Analytics & Optimization Engine

Advanced multi-asset portfolio analytics framework built in Python.

This project performs:

* ISIN → Ticker mapping
* Market data download (Yahoo Finance)
* Performance analytics
* Risk analytics
* Portfolio optimization
* Multi-horizon stability (seasonality) analysis
* Professional Excel reporting

---

# 🧱 Project Structure

```
python_project/
│
├── data/
│   ├── himalaya.xlsx
│   ├── isin_ticker_mapping.csv
│
├── output/
│   └── portfolio_analysis.xlsx
│
├── src/
│   ├── main.py
│   ├── analytics.py
│   ├── risk_metrics.py
│   ├── optimization.py
│   ├── seasonality.py
│   ├── excel_export.py
│   ├── auto_mapping.py
│   └── converter.py
│
├── env/
└── requirements.txt
```

---

# ⚙️ Setup

## 1️⃣ Create virtual environment

```bash
python -m venv env
source env/bin/activate
```

## 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

Main libraries used:

* pandas
* numpy
* yfinance
* openpyxl
* scipy

---

# 🚀 How to Run

From project root:

```bash
python src/main.py
```

Output will be generated in:

```
output/portfolio_analysis.xlsx
```

---

# 🔄 Data Flow Pipeline

```
Excel (ISIN)
    ↓
ISIN → Ticker mapping
    ↓
Market data download (Yahoo Finance)
    ↓
Performance metrics
    ↓
Risk metrics
    ↓
Portfolio optimization
    ↓
Multi-horizon stability analysis
    ↓
Professional Excel report
```

---

# 📈 Analytics Engine

## 📊 Performance Metrics (analytics.py)

Computed using daily adjusted prices.

### Metrics:

* Current Price
* Performance 1Y / 3Y / 5Y
* CAGR 3Y / 5Y
* Average Daily Return
* Annual Return
* Skewness
* Kurtosis
* Correlation vs Benchmark
* Covariance vs Benchmark

---

## 📉 Risk Metrics (risk_metrics.py)

* Volatility (annualized)
* Sharpe Ratio
* Beta vs Benchmark
* Max Drawdown

Sharpe ratio uses:

```
Sharpe = (Annual Return - Risk Free Rate) / Annual Volatility
```

---

# 🧠 Portfolio Optimization (optimization.py)

Monte Carlo simulation (random portfolios).

### Outputs:

* Max Sharpe Portfolio
* Minimum Volatility Portfolio
* Correlation Matrix

Volatility computed via:

```
σ = sqrt(wᵀ Σ w)
```

---

# 🔁 Multi-Horizon Stability (seasonality.py)

This module computes performance consistency across time horizons:

* 3 Months
* 6 Months
* 1 Year
* 2 Years
* 3 Years
* 4 Years
* 5 Years

Method:

1. Rolling cumulative returns
2. Pivot by year
3. Correlation between years
4. Average upper-triangle correlation

Interpretation:

| Value   | Meaning          |
| ------- | ---------------- |
| > 0.6   | Strong stability |
| 0.3–0.6 | Moderate         |
| 0–0.3   | Weak             |
| < 0     | Unstable         |

---

# 📊 Excel Report Structure

The output file contains:

## 🏠 Dashboard

* Number of assets
* Average Sharpe
* Average Volatility
* Average CAGR 3Y
* Average Max Drawdown

---

## 📋 Metrics

Includes:

* Name
* Country
* Performance metrics
* Risk metrics
* Statistical metrics

Features:

* Automatic formatting
* Country color coding
* Dynamic legend

---

## 🔗 Correlation

* Full correlation matrix
* Heatmap coloring (-1 to +1)

---

## 🏆 Max Sharpe Portfolio

Portfolio weights (formatted as percentages)

---

## 🛡 Min Vol Portfolio

Portfolio weights (formatted as percentages)

---

## 🔄 Seasonality (Multi-Horizon Stability)

Columns:

* 3M
* 6M
* 1Y
* 2Y
* 3Y
* 4Y
* 5Y
* Rank (3Y)

Heatmap applied automatically.

---

# 🌍 Country Detection Logic

Ticker suffix mapping:

| Suffix         | Country     |
| -------------- | ----------- |
| .L             | UK          |
| .PA            | France      |
| .DE / .F / .MU | Germany     |
| .MI            | Italy       |
| .SW            | Switzerland |
| .AS            | Netherlands |
| .SI            | Singapore   |

---

# 📌 Benchmark

Default benchmark:

```
IWDA.AS
```

Used for:

* Beta
* Correlation
* Covariance

---

# 🧮 Mathematical Summary

### Annual Return

```
μ_annual = mean(daily_returns) * 252
```

### Volatility

```
σ_annual = std(daily_returns) * √252
```

### Beta

```
β = Cov(asset, benchmark) / Var(benchmark)
```

### Max Drawdown

```
DD = (Cumulative - RollingMax) / RollingMax
```

---

# 🔧 Customization

You can:

* Change benchmark in `main.py`
* Add new exchanges in `detect_country()`
* Adjust risk-free rate in `analytics.py`
* Modify optimization simulation size
* Extend stability horizons

---

# ⚠️ Known Constraints

* Yahoo Finance data availability limits historical depth
* Horizons above available data length return NaN
* Optimization may be slower with >100 assets

---

# 🧠 Future Improvements

Possible upgrades:

* Efficient Frontier visualization
* Rolling Sharpe stability
* Factor exposure analysis
* Risk parity optimization
* Transaction cost modelling
* Streamlit dashboard
* API integration

---

# 🏗 Design Philosophy

The project follows clean separation of concerns:

| File            | Responsibility           |
| --------------- | ------------------------ |
| analytics.py    | Performance calculations |
| risk_metrics.py | Risk calculations        |
| optimization.py | Portfolio construction   |
| seasonality.py  | Stability analysis       |
| excel_export.py | Presentation layer       |
| main.py         | Pipeline orchestration   |

---

# 📄 License

For educational and research purposes.

---

# 👨‍💻 Author
Emanuele Ielmini
Portfolio Analytics Engine
Built with Python for systematic investment research.
