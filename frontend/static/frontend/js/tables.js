(function () {
  const normalize = (value) =>
    String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();

  const debounce = (callback, delay = 180) => {
    let timer;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback(...args), delay);
    };
  };

  const getScope = (table) => table.closest(".container-xl, .page-body, body") || document;

  const getCellValue = (row, index, type) => {
    const text = row.children[index]?.textContent.trim() || "";
    if (type === "number") {
      const number = Number(text.replace(/[^\d,-]/g, "").replace(",", "."));
      return Number.isFinite(number) ? number : -Infinity;
    }

    if (type === "date") {
      const match = text.match(/(\d{2})\/(\d{2})\/(\d{4})/);
      if (!match) return 0;
      return new Date(`${match[3]}-${match[2]}-${match[1]}T00:00:00`).getTime();
    }

    return normalize(text);
  };

  const updateUrl = (prefix, state) => {
    const url = new URL(window.location.href);
    const entries = {
      [`${prefix}_q`]: state.query,
      [`${prefix}_status`]: state.status === "todos" ? "" : state.status,
      [`${prefix}_sort`]: state.sortIndex >= 0 ? String(state.sortIndex) : "",
      [`${prefix}_dir`]: state.sortDir === "desc" ? "desc" : "",
    };

    Object.entries(entries).forEach(([key, value]) => {
      if (value) url.searchParams.set(key, value);
      else url.searchParams.delete(key);
    });

    window.history.replaceState({}, "", url);
  };

  const hydrateState = (prefix) => {
    const params = new URLSearchParams(window.location.search);
    return {
      query: params.get(`${prefix}_q`) || "",
      status: params.get(`${prefix}_status`) || "todos",
      sortIndex: Number(params.get(`${prefix}_sort`) ?? -1),
      sortDir: params.get(`${prefix}_dir`) === "desc" ? "desc" : "asc",
    };
  };

  const initResponsiveLabels = (table) => {
    const labels = [...table.querySelectorAll("thead th")].map((heading) =>
      heading.textContent.trim()
    );

    table.querySelectorAll("tbody tr").forEach((row) => {
      [...row.children].forEach((cell, index) => {
        if (cell.tagName !== "TD" || cell.hasAttribute("colspan")) return;
        cell.dataset.label = labels[index] || "";
      });
    });
  };

  const initTable = (table) => {
    if (table.dataset.tableReady) return;
    table.dataset.tableReady = "true";

    initResponsiveLabels(table);

    const prefix = table.dataset.tableParamPrefix || "tabela";
    const scope = getScope(table);
    const tbody = table.querySelector("tbody");
    const searchInput = scope.querySelector("[data-table-search], .search-input");
    const clearButton = scope.querySelector("[data-table-clear]");
    const countTarget = scope.querySelector("[data-table-count]");
    const pills = [...scope.querySelectorAll(".filter-pills [data-status]")];
    const sortButtons = [...table.querySelectorAll("[data-sort]")];
    const emptyRow = table.querySelector(".filter-empty-row");
    const emptyMessage = table.querySelector("[data-filter-empty-message]");
    const staticEmptyRows = [...table.querySelectorAll(".table-empty-row")];
    const rows = [...table.querySelectorAll("tbody tr")].filter(
      (row) => row.cells.length > 1 && !row.classList.contains("filter-empty-row") && !row.classList.contains("table-empty-row")
    );
    const state = hydrateState(prefix);

    if (!Number.isInteger(state.sortIndex)) state.sortIndex = -1;
    if (state.sortIndex >= sortButtons.length) state.sortIndex = -1;
    if (searchInput) searchInput.value = state.query;

    const setActivePill = () => {
      pills.forEach((pill) => {
        const isActive = (pill.dataset.status || "todos") === state.status;
        pill.classList.toggle("active", isActive);
        pill.setAttribute("aria-pressed", String(isActive));
      });
    };

    const setSortState = () => {
      sortButtons.forEach((button, index) => {
        const active = index === state.sortIndex;
        button.classList.toggle("is-sorted", active);
        button.dataset.sortDir = active ? state.sortDir : "";
        button.closest("th")?.setAttribute("aria-sort", active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none");
      });
    };

    const sortRows = () => {
      if (state.sortIndex < 0) return;

      const type = sortButtons[state.sortIndex]?.dataset.sort || "text";
      rows.sort((a, b) => {
        const valueA = getCellValue(a, state.sortIndex, type);
        const valueB = getCellValue(b, state.sortIndex, type);
        if (valueA > valueB) return state.sortDir === "asc" ? 1 : -1;
        if (valueA < valueB) return state.sortDir === "asc" ? -1 : 1;
        return Number(a.dataset.initialIndex) - Number(b.dataset.initialIndex);
      });

      rows.forEach((row) => tbody.appendChild(row));
      staticEmptyRows.forEach((row) => tbody.appendChild(row));
      if (emptyRow) tbody.appendChild(emptyRow);
    };

    const applyFilters = ({ highlight = false, persist = true } = {}) => {
      const query = normalize(state.query);
      let visibleRows = 0;

      rows.forEach((row, index) => {
        row.dataset.initialIndex = row.dataset.initialIndex || String(index);
        const rowText = normalize(row.textContent);
        const rowStatus = normalize(row.dataset.status || row.querySelector(".status-indicator, .status-pill")?.textContent || "");
        const visible = (!query || rowText.includes(query)) && (state.status === "todos" || rowStatus === state.status);

        row.classList.toggle("is-filtered-out", !visible);
        if (visible) {
          visibleRows += 1;
          if (highlight) {
            row.classList.remove("row-highlight");
            window.requestAnimationFrame(() => row.classList.add("row-highlight"));
            window.setTimeout(() => row.classList.remove("row-highlight"), 900);
          }
        }
      });

      const hasFilter = Boolean(query) || state.status !== "todos";
      const showingInitialEmptyState = rows.length === 0 && !hasFilter;
      staticEmptyRows.forEach((row) => row.classList.toggle("is-filtered-out", hasFilter));

      if (emptyRow) {
        emptyRow.classList.toggle("is-filtered-out", visibleRows > 0 || showingInitialEmptyState);
      }

      if (emptyMessage) {
        const parts = [];
        if (state.query) parts.push(`busca "${state.query}"`);
        if (state.status !== "todos") parts.push(`status selecionado`);
        emptyMessage.textContent = parts.length
          ? `Nenhum resultado encontrado para ${parts.join(" e ")}.`
          : "Nenhum resultado encontrado para este filtro.";
      }

      if (countTarget) {
        const noun = visibleRows === 1 ? "resultado" : "resultados";
        countTarget.textContent = `${visibleRows} ${noun}`;
      }

      if (clearButton) clearButton.disabled = !hasFilter && state.sortIndex < 0;
      sortRows();
      setActivePill();
      setSortState();
      if (persist) updateUrl(prefix, state);
    };

    const debouncedSearch = debounce(() => {
      state.query = searchInput?.value || "";
      applyFilters({ highlight: true });
    });

    searchInput?.addEventListener("input", debouncedSearch);

    pills.forEach((pill) => {
      pill.addEventListener("click", () => {
        state.status = pill.dataset.status || "todos";
        applyFilters({ highlight: true });
      });
    });

    sortButtons.forEach((button, index) => {
      button.addEventListener("click", () => {
        if (state.sortIndex === index) {
          state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        } else {
          state.sortIndex = index;
          state.sortDir = "asc";
        }
        applyFilters({ highlight: true });
      });
    });

    clearButton?.addEventListener("click", () => {
      state.query = "";
      state.status = "todos";
      state.sortIndex = -1;
      state.sortDir = "asc";
      if (searchInput) searchInput.value = "";
      rows
        .sort((a, b) => Number(a.dataset.initialIndex) - Number(b.dataset.initialIndex))
        .forEach((row) => tbody.appendChild(row));
      staticEmptyRows.forEach((row) => tbody.appendChild(row));
      if (emptyRow) tbody.appendChild(emptyRow);
      applyFilters({ highlight: true });
    });

    applyFilters({ persist: false });
  };

  const initTables = () => {
    document.querySelectorAll("[data-table-enhanced]").forEach(initTable);
  };

  window.CesariModules = window.CesariModules || {};
  window.CesariModules.tables = { init: initTables, initResponsiveLabels };
})();
