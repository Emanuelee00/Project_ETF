(function () {
  const config = window.CHART_CONFIG || {};
  const statusEl = document.getElementById("status");
  const periodSelect = document.getElementById("period-select");
  const smaInput = document.getElementById("sma-input");
  const emaInput = document.getElementById("ema-input");
  const tickerDisplay = document.getElementById("ticker-display");
  const priceCanvas = document.getElementById("price-chart");
  const volumeCanvas = document.getElementById("volume-chart");

  let priceChart = null;
  let volumeChart = null;
  let currentRows = [];

  tickerDisplay.value = config.ticker || "";
  if (config.defaultPeriod) {
    periodSelect.value = config.defaultPeriod;
  }

  function setStatus(message, isError) {
    statusEl.textContent = message;
    statusEl.style.color = isError ? "#fca5a5" : "#94a3b8";
  }

  function toNumber(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function computeSMA(values, windowSize) {
    const result = [];

    for (let index = 0; index < values.length; index += 1) {
      if (index + 1 < windowSize) {
        result.push(null);
        continue;
      }

      const slice = values.slice(index + 1 - windowSize, index + 1);
      const sum = slice.reduce((acc, item) => acc + item, 0);
      result.push(sum / windowSize);
    }

    return result;
  }

  function computeEMA(values, windowSize) {
    const result = [];
    const multiplier = 2 / (windowSize + 1);
    let previous = null;

    values.forEach((value, index) => {
      if (index === 0) {
        previous = value;
      } else {
        previous = (value - previous) * multiplier + previous;
      }
      result.push(previous);
    });

    return result;
  }

  function destroyCharts() {
    if (priceChart) {
      priceChart.destroy();
      priceChart = null;
    }

    if (volumeChart) {
      volumeChart.destroy();
      volumeChart = null;
    }
  }

  function renderCharts() {
    if (!currentRows.length) {
      destroyCharts();
      setStatus("No data available for this ticker.", true);
      return;
    }

    const labels = currentRows.map((row) => row.date);
    const closeValues = currentRows.map((row) => row.close);
    const volumeValues = currentRows.map((row) => row.volume || 0);

    const smaWindow = Math.max(2, toNumber(smaInput.value) || 20);
    const emaWindow = Math.max(2, toNumber(emaInput.value) || 50);

    const smaValues = computeSMA(closeValues, smaWindow);
    const emaValues = computeEMA(closeValues, emaWindow);

    destroyCharts();

    priceChart = new Chart(priceCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Close",
            data: closeValues,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.14)",
            pointRadius: 0,
            borderWidth: 2,
            tension: 0.12,
          },
          {
            label: `SMA ${smaWindow}`,
            data: smaValues,
            borderColor: "#22c55e",
            pointRadius: 0,
            borderWidth: 1.5,
            tension: 0.12,
          },
          {
            label: `EMA ${emaWindow}`,
            data: emaValues,
            borderColor: "#f59e0b",
            pointRadius: 0,
            borderWidth: 1.5,
            tension: 0.12,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: "index",
        },
        plugins: {
          legend: {
            labels: {
              color: "#e5e7eb",
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: "#94a3b8",
              maxTicksLimit: 10,
            },
            grid: {
              color: "rgba(148, 163, 184, 0.15)",
            },
          },
          y: {
            ticks: {
              color: "#94a3b8",
            },
            grid: {
              color: "rgba(148, 163, 184, 0.15)",
            },
          },
        },
      },
    });

    volumeChart = new Chart(volumeCanvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Volume",
            data: volumeValues,
            backgroundColor: "rgba(239, 68, 68, 0.55)",
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: {
              color: "#e5e7eb",
            },
          },
        },
        scales: {
          x: {
            ticks: {
              color: "#94a3b8",
              maxTicksLimit: 10,
            },
            grid: {
              color: "rgba(148, 163, 184, 0.15)",
            },
          },
          y: {
            ticks: {
              color: "#94a3b8",
            },
            grid: {
              color: "rgba(148, 163, 184, 0.15)",
            },
          },
        },
      },
    });

    setStatus(`Loaded ${currentRows.length} rows for ${config.ticker}.`, false);
  }

  async function fetchChart() {
    if (!config.apiBase || !config.ticker) {
      setStatus("Missing chart configuration.", true);
      return;
    }

    const period = periodSelect.value;
    const endpoint = `${config.apiBase}/chart/${encodeURIComponent(config.ticker)}?period=${encodeURIComponent(period)}`;

    setStatus("Loading chart data...", false);

    try {
      const response = await fetch(endpoint, { method: "GET" });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || "Unable to load chart data.");
      }

      currentRows = Array.isArray(payload.rows) ? payload.rows : [];
      renderCharts();
    } catch (error) {
      currentRows = [];
      destroyCharts();
      setStatus(error.message || "Unexpected chart error.", true);
    }
  }

  periodSelect.addEventListener("change", fetchChart);
  smaInput.addEventListener("input", renderCharts);
  emaInput.addEventListener("input", renderCharts);

  fetchChart();
})();
