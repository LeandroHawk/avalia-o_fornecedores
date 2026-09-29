(function () {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const numberFormatter = new Intl.NumberFormat("pt-BR");

  const getChartItems = (chart, selector) =>
    [...chart.querySelectorAll(selector)]
      .map((item) => ({
        label: item.dataset.label || "",
        count: Number(String(item.dataset.count || "0").replace(",", ".")),
        color: item.dataset.color || "#4f80c9",
      }))
      .filter((item) => Number.isFinite(item.count));

  const commonTooltip = {
    backgroundColor: "#101828",
    titleColor: "#fff",
    bodyColor: "#eef4ff",
    borderColor: "rgba(255, 255, 255, .14)",
    borderWidth: 1,
    padding: 12,
    displayColors: true,
    boxPadding: 6,
    callbacks: {
      label(context) {
        const value = Number(context.parsed?.y ?? context.parsed ?? 0);
        return ` ${context.label}: ${numberFormatter.format(value)}`;
      },
    },
  };

  const setActiveSlice = (chartInstance, legendItems, index) => {
    legendItems.forEach((item) => item.classList.toggle("is-active", Number(item.dataset.index) === index));

    if (index < 0) {
      chartInstance.setActiveElements([]);
      chartInstance.tooltip?.setActiveElements([], { x: 0, y: 0 });
    } else {
      const chartArea = chartInstance.chartArea;
      const point = {
        x: (chartArea.left + chartArea.right) / 2,
        y: (chartArea.top + chartArea.bottom) / 2,
      };
      chartInstance.setActiveElements([{ datasetIndex: 0, index }]);
      chartInstance.tooltip?.setActiveElements([{ datasetIndex: 0, index }], point);
    }

    chartInstance.update();
  };

  const initStatusDonut = (container) => {
    if (!window.Chart || container.dataset.chartReady) return;

    const items = getChartItems(container, ".chart-pie-slice-data").filter((item) => item.count > 0);
    const total = items.reduce((sum, item) => sum + item.count, 0);
    container.classList.toggle("chart-is-empty", total === 0);
    if (!total) return;

    const canvas = container.querySelector("canvas");
    if (!canvas) return;

    container.dataset.chartReady = "true";
    container.classList.add("chart-ready");

    const chartInstance = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: items.map((item) => item.label),
        datasets: [
          {
            data: items.map((item) => item.count),
            backgroundColor: items.map((item) => item.color),
            borderColor: "#fff",
            borderWidth: 4,
            hoverOffset: 10,
          },
        ],
      },
      options: {
        animation: reducedMotion ? false : { duration: 850, easing: "easeOutQuart" },
        cutout: "62%",
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: commonTooltip,
        },
        onHover(event, elements) {
          const index = elements[0]?.index ?? -1;
          setActiveSlice(chartInstance, legendItems, index);
        },
      },
    });

    const legendItems = [
      ...container.closest(".innovation-chart-card")?.querySelectorAll("[data-chart-legend]") || [],
    ];

    legendItems.forEach((item) => {
      const index = Number(item.dataset.index || -1);
      item.addEventListener("mouseenter", () => setActiveSlice(chartInstance, legendItems, index));
      item.addEventListener("focus", () => setActiveSlice(chartInstance, legendItems, index));
      item.addEventListener("mouseleave", () => setActiveSlice(chartInstance, legendItems, -1));
      item.addEventListener("blur", () => setActiveSlice(chartInstance, legendItems, -1));
      item.addEventListener("click", () => {
        const isActive = item.classList.contains("is-active");
        setActiveSlice(chartInstance, legendItems, isActive ? -1 : index);
      });
    });
  };

  const initScoreBars = (container) => {
    if (!window.Chart || container.dataset.chartReady) return;

    const items = getChartItems(container, ".chart-bar-data");
    const total = items.reduce((sum, item) => sum + item.count, 0);
    container.classList.toggle("chart-is-empty", total === 0);
    if (!total) return;

    const canvas = container.querySelector("canvas");
    if (!canvas) return;

    container.dataset.chartReady = "true";
    container.classList.add("chart-ready");

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: items.map((item) => item.label),
        datasets: [
          {
            label: "Fornecedores",
            data: items.map((item) => item.count),
            backgroundColor: items.map((item) => item.color),
            borderColor: "#2f5f9f",
            borderWidth: 1,
            borderRadius: 7,
            maxBarThickness: 56,
          },
        ],
      },
      options: {
        animation: reducedMotion ? false : { duration: 780, easing: "easeOutQuart" },
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: "#667085", font: { size: 12, weight: "700" } },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0, color: "#667085", font: { size: 12, weight: "700" } },
            grid: { color: "#e4ecf6" },
          },
        },
        plugins: {
          legend: {
            display: true,
            labels: { color: "#344054", boxWidth: 12, usePointStyle: true },
            onClick(event, legendItem, legend) {
              Chart.defaults.plugins.legend.onClick.call(this, event, legendItem, legend);
            },
          },
          tooltip: commonTooltip,
        },
      },
    });
  };

  const initCounters = () => {
    document.querySelectorAll("[data-counter]").forEach((counter) => {
      if (counter.dataset.counterReady) return;

      const target = Number(String(counter.dataset.counterValue || counter.textContent || "0").replace(",", "."));
      if (!Number.isFinite(target)) return;

      counter.dataset.counterReady = "true";
      const suffix = counter.dataset.counterSuffix || "";
      const duration = reducedMotion ? 0 : 650;
      const startedAt = performance.now();

      const render = (now) => {
        const progress = duration ? Math.min((now - startedAt) / duration, 1) : 1;
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = Math.round(target * eased);
        counter.textContent = `${numberFormatter.format(value)}${suffix}`;
        if (progress < 1) requestAnimationFrame(render);
      };

      requestAnimationFrame(render);
    });
  };

  const initCharts = () => {
    document.querySelectorAll('[data-chart="status-donut"]').forEach(initStatusDonut);
    document.querySelectorAll('[data-chart="score-bars"]').forEach(initScoreBars);
    initCounters();
  };

  window.CesariModules = window.CesariModules || {};
  window.CesariModules.charts = { init: initCharts };
})();
