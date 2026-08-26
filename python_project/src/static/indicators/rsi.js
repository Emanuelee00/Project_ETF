/* Wilder RSI. */
(function () {
  const indicators = window.ChartIndicators || {};

  indicators.rsi = (closes, period = 14) => {
    const result = new Array(closes.length).fill(null);
    if (closes.length <= period) return result;

    const gains = [];
    const losses = [];
    for (let index = 1; index < closes.length; index += 1) {
      if (closes[index] == null || closes[index - 1] == null) {
        gains.push(null);
        losses.push(null);
        continue;
      }
      const change = closes[index] - closes[index - 1];
      gains.push(Math.max(change, 0));
      losses.push(Math.max(-change, 0));
    }
    if (gains.slice(0, period).some(value => value == null)) return result;

    let averageGain = gains.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
    let averageLoss = losses.slice(0, period).reduce((sum, value) => sum + value, 0) / period;
    result[period] = averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);

    for (let index = period; index < gains.length; index += 1) {
      if (gains[index] == null || losses[index] == null) continue;
      averageGain = (averageGain * (period - 1) + gains[index]) / period;
      averageLoss = (averageLoss * (period - 1) + losses[index]) / period;
      result[index + 1] = averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);
    }
    return result;
  };

  window.ChartIndicators = indicators;
}());
