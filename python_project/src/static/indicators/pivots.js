/* Standard pivots from the previous completed trading session. */
(function () {
  const indicators = window.ChartIndicators || {};

  indicators.pivots = (rows, interval = "1d") => {
    const valid = (rows || []).filter(row => row.high != null && row.low != null && row.close != null);
    if (!valid.length) return null;

    let session;
    if (["1wk", "1mo", "3mo"].includes(interval)) {
      session = valid.length > 1 ? [valid[valid.length - 2]] : [];
    } else {
      const byDay = new Map();
      valid.forEach(row => {
        // Intraday rows carry a UTC epoch-seconds number; daily+ rows carry a
        // 'YYYY-MM-DD[THH:MM]' string — derive the calendar day from either.
        const day = typeof row.date === "number"
          ? new Date(row.date * 1000).toISOString().slice(0, 10)
          : String(row.date).slice(0, 10);
        byDay.set(day, [...(byDay.get(day) || []), row]);
      });
      const days = [...byDay.keys()].sort();
      const today = new Date().toISOString().slice(0, 10);
      const sourceDay = days.at(-1) === today ? days.at(-2) : days.at(-1);
      session = sourceDay ? byDay.get(sourceDay) : [];
    }
    if (!session?.length) return null;

    const high = Math.max(...session.map(row => row.high));
    const low = Math.min(...session.map(row => row.low));
    const close = session.at(-1).close;
    const pp = (high + low + close) / 3;
    return {
      PP: pp, R1: 2 * pp - low, R2: pp + (high - low), R3: high + 2 * (pp - low),
      S1: 2 * pp - high, S2: pp - (high - low), S3: low - 2 * (high - pp),
    };
  };

  window.ChartIndicators = indicators;
}());
