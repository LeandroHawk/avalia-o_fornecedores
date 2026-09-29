(function () {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const formatBytes = (bytes) => {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, index);
    return `${value.toLocaleString("pt-BR", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
  };

  const countSection = (section) => {
    if (section.id === "dados") {
      const fields = [...section.querySelectorAll("input, select, textarea")].filter(
        (field) => field.type !== "hidden" && field.type !== "file"
      );
      const done = fields.filter((field) => String(field.value || "").trim()).length;
      return { done, total: fields.length || Number(section.dataset.total || 0) };
    }

    const questions = [...section.querySelectorAll(".supplier-question")];
    const done = questions.filter((question) => {
      const fileInput = question.querySelector('[type="file"]');
      if (fileInput) {
        const hasExistingFile = Boolean(question.querySelector(".badge.bg-green-lt"));
        const hasSelectedFile = fileInput.files && fileInput.files.length > 0;
        const missingFile = Boolean(question.querySelector(".bg-yellow-lt"));
        return hasExistingFile || hasSelectedFile || !missingFile;
      }

      const checked = question.querySelector("input[type='radio']:checked, input[type='checkbox']:checked");
      const select = question.querySelector("select");
      const text = question.querySelector("textarea, input:not([type='hidden']):not([type='radio']):not([type='checkbox'])");
      return Boolean(checked || (select && select.value) || (text && String(text.value || "").trim()));
    }).length;

    return { done, total: questions.length || Number(section.dataset.total || 0) };
  };

  const updateSectionProgress = (form) => {
    form.querySelectorAll("[data-section-progress]").forEach((section) => {
      const { done, total } = countSection(section);
      const percent = total ? Math.round((done / total) * 100) : 0;
      const bar = section.querySelector(".section-progress-track i");
      const headerText = section.querySelector(".supplier-card-header span");
      const navLink = form.querySelector(`.supplier-nav-item[href="#${section.id}"] strong`);

      section.dataset.done = String(done);
      section.dataset.total = String(total);
      section.classList.toggle("section-complete", total > 0 && done >= total);
      section.classList.toggle("section-has-pending", total > 0 && done < total);
      if (bar) bar.style.setProperty("--section-progress-value", `${percent}%`);
      if (headerText) {
        const noun = section.id === "dados" ? "preenchidos" : "respondidas";
        headerText.textContent = `${done} de ${total} ${noun}`;
      }
      if (navLink) navLink.textContent = `${done}/${total}`;
    });
  };

  const createSummary = (form) => {
    const sidebar = form.querySelector(".supplier-progress");
    if (!sidebar || sidebar.querySelector("[data-floating-summary]")) return null;

    const summary = document.createElement("div");
    summary.className = "floating-summary-card";
    summary.dataset.floatingSummary = "true";
    summary.innerHTML = `
      <strong>Resumo dinâmico</strong>
      <span data-summary-pending>0 pendências</span>
      <span data-summary-files>0 anexos selecionados</span>
      <span data-summary-adjustments>0 ajustes marcados</span>
    `;
    sidebar.appendChild(summary);
    return summary;
  };

  const updateSummary = (form) => {
    const summary = form.querySelector("[data-floating-summary]") || createSummary(form);
    if (!summary) return;

    const sections = [...form.querySelectorAll("[data-section-progress]")];
    const pending = sections.filter((section) => {
      const done = Number(section.dataset.done || 0);
      const total = Number(section.dataset.total || 0);
      return total > 0 && done < total;
    }).length;
    const selectedFiles = [...form.querySelectorAll("[data-file-input]")].filter(
      (input) => input.files && input.files.length > 0
    ).length;
    const adjustments = [...form.querySelectorAll("input[name^='ajuste_q_']:checked")].length;

    summary.querySelector("[data-summary-pending]").textContent =
      pending === 1 ? "1 seção com pendência" : `${pending} seções com pendências`;
    summary.querySelector("[data-summary-files]").textContent =
      selectedFiles === 1 ? "1 anexo selecionado" : `${selectedFiles} anexos selecionados`;
    summary.querySelector("[data-summary-adjustments]").textContent =
      adjustments === 1 ? "1 ajuste marcado" : `${adjustments} ajustes marcados`;
  };

  const initSectionNavigation = (form) => {
    const links = [...form.querySelectorAll("[data-section-link]")];
    const sections = links
      .map((link) => document.querySelector(link.getAttribute("href")))
      .filter(Boolean);
    if (!links.length || !sections.length) return;

    const setActive = (id) => {
      links.forEach((link) => link.classList.toggle("active", link.getAttribute("href") === `#${id}`));
    };

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
          if (visible) setActive(visible.target.id);
        },
        { rootMargin: "-25% 0px -60% 0px", threshold: [0.15, 0.35, 0.6] }
      );
      sections.forEach((section) => observer.observe(section));
    }

    links.forEach((link) => {
      link.addEventListener("click", () => setActive(link.getAttribute("href").slice(1)));
    });
  };

  const initFileInputs = (form) => {
    form.querySelectorAll("[data-file-input]").forEach((input) => {
      const control = input.closest(".question-control") || input.parentElement;
      const selected = control?.querySelector("[data-file-selected]");
      const clear = control?.querySelector("[data-file-clear]");
      if (!selected || !clear) return;

      const render = () => {
        const file = input.files?.[0];
        if (file) {
          selected.textContent = `${file.name} (${formatBytes(file.size)})`;
          selected.classList.remove("is-empty");
          clear.classList.remove("is-filtered-out");
        } else {
          selected.textContent = "Nenhum arquivo selecionado";
          selected.classList.add("is-empty");
          clear.classList.add("is-filtered-out");
        }
        updateSectionProgress(form);
        updateSummary(form);
      };

      input.addEventListener("change", render);
      clear.addEventListener("click", () => {
        input.value = "";
        render();
      });
    });
  };

  const initProgressAnimation = (form) => {
    if (reducedMotion) {
      form.classList.add("section-progress-ready");
      return;
    }

    window.requestAnimationFrame(() => form.classList.add("section-progress-ready"));
  };

  const initFirstPending = (form) => {
    const target =
      form.querySelector(".is-invalid")?.closest("[data-section-progress]") ||
      form.querySelector("[data-has-pending='true']") ||
      form.querySelector(".section-has-pending");

    if (!target) return;
    target.classList.add("section-attention");
    target.dataset.autoExpanded = "true";
  };

  const initForm = (form) => {
    if (form.dataset.formReady) return;
    form.dataset.formReady = "true";

    updateSectionProgress(form);
    updateSummary(form);
    initSectionNavigation(form);
    initFileInputs(form);
    initProgressAnimation(form);
    initFirstPending(form);

    form.addEventListener("input", () => {
      updateSectionProgress(form);
      updateSummary(form);
    });
    form.addEventListener("change", () => {
      updateSectionProgress(form);
      updateSummary(form);
    });
  };

  const initForms = () => {
    document.querySelectorAll("[data-evaluation-form]").forEach(initForm);
  };

  window.CesariModules = window.CesariModules || {};
  window.CesariModules.forms = { init: initForms };
})();
