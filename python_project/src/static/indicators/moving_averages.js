/* Simple and exponential moving averages for the chart. */
(function () {
  const indicators = window.ChartIndicators || {};

  indicators.sma = (data, period) => data.map((_, index) => {
    if (index < period - 1) return null;
    const windowValues = data.slice(index - period + 1, index + 1);
    return windowValues.some(value => value == null)
      ? null
      : windowValues.reduce((sum, value) => sum + value, 0) / period;
  });

  indicators.ema = (data, period) => {
    const multiplier = 2 / (period + 1);
    const result = new Array(data.length).fill(null);
    let previous = null;
    data.forEach((value, index) => {
      if (value == null) return;
      previous = previous == null ? value : value * multiplier + previous * (1 - multiplier);
      result[index] = previous;
    });
    return result;
  };

  window.ChartIndicators = indicators;
}());
