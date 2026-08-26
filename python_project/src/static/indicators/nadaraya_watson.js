/* Nadaraya-Watson Envelope, based on the LuxAlgo Pine implementation.
 * The repainting variant uses future bars inside the latest window; the
 * endpoint variant only uses bars available at each point in time. */
(function () {
  const gaussian = (distance, bandwidth) =>
    Math.exp(-(distance * distance) / (2 * bandwidth * bandwidth));

  const envelope = (line, source, multiplier, start, end) => {
    const errors = [];
    for (let i = start; i < end; i += 1) {
      if (line[i] != null && source[i] != null) errors.push(Math.abs(source[i] - line[i]));
    }
    const mae = errors.length ? errors.reduce((sum, value) => sum + value, 0) / errors.length * multiplier : 0;
    return {
      line,
      upper: line.map(value => value == null ? null : value + mae),
      lower: line.map(value => value == null ? null : value - mae),
    };
  };

  function repainting(source, bandwidth = 8, multiplier = 3, lookback = 500) {
    const line = new Array(source.length).fill(null);
    const start = Math.max(0, source.length - lookback);
    for (let i = start; i < source.length; i += 1) {
      let weightedSum = 0;
      let weightSum = 0;
      for (let j = start; j < source.length; j += 1) {
        if (source[j] == null) continue;
        const weight = gaussian(i - j, bandwidth);
        weightedSum += source[j] * weight;
        weightSum += weight;
      }
      line[i] = weightSum ? weightedSum / weightSum : null;
    }
    return envelope(line, source, multiplier, start, source.length);
  }

  function endpoint(source, bandwidth = 8, multiplier = 3, lookback = 500) {
    const line = new Array(source.length).fill(null);
    const errors = new Array(source.length).fill(null);
    for (let i = lookback - 1; i < source.length; i += 1) {
      let weightedSum = 0;
      let weightSum = 0;
      for (let lag = 0; lag < lookback; lag += 1) {
        const value = source[i - lag];
        if (value == null) continue;
        const weight = gaussian(lag, bandwidth);
        weightedSum += value * weight;
        weightSum += weight;
      }
      line[i] = weightSum ? weightedSum / weightSum : null;
      errors[i] = Math.abs(source[i] - line[i]);
    }

    const upper = new Array(source.length).fill(null);
    const lower = new Array(source.length).fill(null);
    for (let i = lookback * 2 - 2; i < source.length; i += 1) {
      const mae = errors.slice(i - lookback + 1, i + 1)
        .reduce((sum, value) => sum + (value ?? 0), 0) / lookback * multiplier;
      upper[i] = line[i] + mae;
      lower[i] = line[i] - mae;
    }
    return { line, upper, lower };
  }

  window.NadarayaWatsonEnvelope = { repainting, endpoint };
}());
