import numpy as np

RISK_FREE_RATE = 0.02
TRADING_DAYS = 252


def portfolio_performance(weights, mean_returns, cov_matrix):

    ret = np.dot(weights, mean_returns) * TRADING_DAYS
    vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix * TRADING_DAYS, weights)))
    sharpe = (ret - RISK_FREE_RATE) / vol if vol != 0 else 0

    return ret, vol, sharpe


def random_portfolios(num_portfolios, mean_returns, cov_matrix):

    num_assets = len(mean_returns)

    results = np.zeros((3, num_portfolios))
    weights_record = []

    for i in range(num_portfolios):

        weights = np.random.random(num_assets)
        weights /= np.sum(weights)

        ret, vol, sharpe = portfolio_performance(
            weights,
            mean_returns,
            cov_matrix
        )

        results[0, i] = ret
        results[1, i] = vol
        results[2, i] = sharpe

        weights_record.append(weights)

    return results, weights_record


def optimize_portfolios(returns):

    mean_returns = returns.mean()
    cov_matrix = returns.cov()

    results, weights = random_portfolios(
        4000,
        mean_returns,
        cov_matrix
    )

    max_sharpe_idx = np.argmax(results[2])
    min_vol_idx = np.argmin(results[1])

    max_sharpe_weights = weights[max_sharpe_idx]
    min_vol_weights = weights[min_vol_idx]

    max_sharpe = dict(zip(returns.columns, max_sharpe_weights))
    min_vol = dict(zip(returns.columns, min_vol_weights))

    return max_sharpe, min_vol
