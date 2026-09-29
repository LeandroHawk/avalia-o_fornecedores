(function () {
  const onReady = (callback) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  };

  const normalize = (value) =>
    value
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();

  const initTableTools = () => {
    const searchInput = document.querySelector(".search-input");
    const table = document.querySelector(".table-card table");
    const pills = [...document.querySelectorAll(".filter-pills [data-status]")];
    if (!searchInput || !table) return;

    const emptyRow = table.querySelector(".filter-empty-row");
    const staticEmptyRows = [...table.querySelectorAll(".table-empty-row")];
    const rows = [...table.querySelectorAll("tbody tr")].filter(
      (row) => row.cells.length > 1 && !row.classList.contains("filter-empty-row")
    );
    let activeStatus = "todos";

    const applyFilters = () => {
      const term = normalize(searchInput.value);
      let visibleRows = 0;

      rows.forEach((row) => {
        const rowText = normalize(row.textContent);
        const status = row.dataset.status || normalize(row.querySelector(".status-indicator, .status-pill")?.textContent || "");
        const isVisible = (!term || rowText.includes(term)) && (activeStatus === "todos" || status === activeStatus);
        row.classList.toggle("is-filtered-out", !isVisible);
        if (isVisible) visibleRows += 1;
      });

      if (emptyRow) {
        const showingInitialEmptyState = rows.length === 0 && !term && activeStatus === "todos";
        emptyRow.classList.toggle("is-filtered-out", visibleRows > 0 || showingInitialEmptyState);
      }

      staticEmptyRows.forEach((row) => {
        row.classList.toggle("is-filtered-out", Boolean(term) || activeStatus !== "todos");
      });
    };

    searchInput.addEventListener("input", applyFilters);
    pills.forEach((pill) => {
      pill.addEventListener("click", () => {
        pills.forEach((item) => item.classList.remove("active"));
        pill.classList.add("active");
        activeStatus = pill.dataset.status || normalize(pill.textContent);
        applyFilters();
      });
    });
  };

  const initResponsiveTables = () => {
    document.querySelectorAll("table").forEach((table) => {
      const labels = [...table.querySelectorAll("thead th")].map((heading) => heading.textContent.trim());
      if (!labels.length) return;

      table.querySelectorAll("tbody tr").forEach((row) => {
        [...row.children].forEach((cell, index) => {
          if (cell.tagName !== "TD" || cell.hasAttribute("colspan")) return;
          cell.dataset.label = labels[index] || "";
        });
      });
    });
  };

  const initSubmitFeedback = () => {
    document.addEventListener("submit", (event) => {
      const submitter = event.submitter;
      if (!submitter || !submitter.classList.contains("btn")) return;
      submitter.classList.add("disabled");
      submitter.setAttribute("aria-disabled", "true");
    });
  };

  const initDonutCharts = () => {
    document.querySelectorAll(".innovation-donut").forEach((chart) => {
      const slices = [...chart.querySelectorAll(".chart-pie-slice-data")]
        .map((item) => ({
          label: item.dataset.label || "",
          count: Number(item.dataset.count || 0),
          percent: Number(item.dataset.percent || 0),
          color: item.dataset.color || "#354784",
        }))
        .filter((item) => item.count > 0);

      const total = Number(chart.dataset.total || slices.reduce((sum, item) => sum + item.count, 0));
      chart.textContent = "";

      if (!total || !slices.length) {
        const empty = document.createElement("div");
        empty.className = "innovation-donut-empty";
        empty.textContent = "Sem dados";
        chart.appendChild(empty);
        return;
      }

      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 320 320");
      svg.setAttribute("class", "innovation-donut-svg");
      svg.setAttribute("aria-hidden", "true");

      const cx = 160;
      const cy = 160;
      const radius = 96;
      const circumference = 2 * Math.PI * radius;
      let offset = 0;

      const track = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      track.setAttribute("class", "innovation-donut-track");
      track.setAttribute("cx", cx);
      track.setAttribute("cy", cy);
      track.setAttribute("r", radius);
      svg.appendChild(track);

      slices.forEach((slice) => {
        const length = (slice.count / total) * circumference;
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("class", "innovation-donut-segment");
        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", radius);
        circle.setAttribute("stroke", slice.color);
        circle.setAttribute("stroke-dasharray", `${Math.max(length - 8, 0)} ${circumference}`);
        circle.style.setProperty("--segment-offset", `${-offset}`);
        circle.style.setProperty("--segment-hidden-offset", `${circumference - offset}`);
        circle.style.strokeDashoffset = `${-offset}`;
        svg.appendChild(circle);
        offset += length;
      });

      const hole = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      hole.setAttribute("class", "innovation-donut-hole");
      hole.setAttribute("cx", cx);
      hole.setAttribute("cy", cy);
      hole.setAttribute("r", 62);
      svg.appendChild(hole);

      chart.appendChild(svg);
    });
  };

  onReady(() => {
    initResponsiveTables();
    initTableTools();
    initSubmitFeedback();
    initDonutCharts();
  });
})();
