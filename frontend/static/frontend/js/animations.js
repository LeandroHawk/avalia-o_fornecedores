(function () {
  const root = document.documentElement;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  root.classList.add("app-motion-ready");

  const onReady = (callback) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  };

  const parseNumber = (value) => {
    const normalized = value.replace(/\./g, "").replace(",", ".");
    const match = normalized.match(/-?\d+(\.\d+)?/);
    return match ? Number(match[0]) : null;
  };

  const formatNumber = (value, originalText) => {
    const suffix = originalText.includes("%") ? "%" : "";
    const decimals = originalText.includes(",") || originalText.includes(".") ? 1 : 0;
    return `${value.toLocaleString("pt-BR", {
      maximumFractionDigits: decimals,
      minimumFractionDigits: decimals,
    })}${suffix}`;
  };

  const animateNumber = (element) => {
    const originalText = element.textContent.trim();
    const target = parseNumber(originalText);
    if (target === null || target < 1 || reduceMotion || element.dataset.animatedNumber) return;

    element.dataset.animatedNumber = "true";
    const duration = 820;
    const startTime = performance.now();

    const step = (time) => {
      const progress = Math.min((time - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = formatNumber(target * eased, originalText);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        element.textContent = originalText;
      }
    };

    requestAnimationFrame(step);
  };

  const animateProgress = (element) => {
    if (reduceMotion || element.dataset.animatedProgress) return;

    const targetWidth = element.style.width;
    if (!targetWidth) return;

    element.dataset.animatedProgress = "true";
    element.style.width = "0%";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        element.style.width = targetWidth;
      });
    });
  };

  const animateVerticalProgress = (element) => {
    if (reduceMotion || element.dataset.animatedVerticalProgress) return;

    const targetHeight = element.style.height;
    if (!targetHeight) return;

    element.dataset.animatedVerticalProgress = "true";
    element.style.height = "0%";
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        element.style.height = targetHeight;
      });
    });
  };

  const revealElements = () => {
    const selectors = [
      ".app-header",
      ".hero-cesari > .container-xl",
      ".page-header",
      ".toolbar-line",
      ".metric-strip > div",
      ".metric-card",
      ".dashboard-card",
      ".card:not(.metric-card)",
      ".supplier-nav-item",
      ".analysis-hero",
      ".supplier-card",
      ".supplier-question",
      ".progress-card",
      ".login-shell",
    ];

    const elements = [...document.querySelectorAll(selectors.join(","))];
    elements.forEach((element, index) => {
      element.classList.add("app-reveal");
      element.style.setProperty("--motion-delay", `${Math.min(index * 42, 300)}ms`);
    });

    if (reduceMotion || !("IntersectionObserver" in window)) {
      elements.forEach((element) => element.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    );

    elements.forEach((element) => observer.observe(element));
  };

  const initHeaderMotion = () => {
    const header = document.querySelector(".app-header");
    if (!header) return;

    const refresh = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    refresh();
    window.addEventListener("scroll", refresh, { passive: true });
  };

  const initCounters = () => {
    const counters = document.querySelectorAll(
      ".metric-card .h1, .metric-strip strong, .progress-number, .review-score strong"
    );
    counters.forEach(animateNumber);
  };

  const initProgressBars = () => {
    document.querySelectorAll(".progress-bar, .score-track i, .mini-bar i").forEach(animateProgress);
    document.querySelectorAll(".chart-bar-fill").forEach(animateVerticalProgress);
  };

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

    const normalize = (value) =>
      value
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .trim();

    const applyFilters = () => {
      const term = normalize(searchInput.value);
      let visibleRows = 0;
      rows.forEach((row) => {
        const rowText = normalize(row.textContent);
        const status = row.dataset.status || normalize(row.querySelector(".status-indicator, .status-pill")?.textContent || "");
        const matchesText = !term || rowText.includes(term);
        const matchesStatus = activeStatus === "todos" || status === activeStatus;
        const isVisible = matchesText && matchesStatus;
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
      submitter.classList.add("is-submitting");
    });
  };

  onReady(() => {
    root.classList.add("app-motion-loaded");
    revealElements();
    initHeaderMotion();
    initCounters();
    initProgressBars();
    initResponsiveTables();
    initTableTools();
    initSubmitFeedback();
  });
})();
