(function () {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const formatBytes = (bytes) => {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, index);
    return `${value.toLocaleString("pt-BR", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
  };

  const hasEvidence = (question) => {
    const fileInput = question.querySelector("[data-file-input]");
    const hasExistingFile = Boolean(question.querySelector(".badge.bg-green-lt"));
    const hasSelectedFile = fileInput?.files && fileInput.files.length > 0;
    return hasExistingFile || hasSelectedFile;
  };

  const countSection = (section) => {
    if (section.id === "dados") {
      const fields = [...section.querySelectorAll("input, select, textarea")].filter(
        (field) => field.type !== "hidden" && field.type !== "file"
      );
      const done = fields.filter((field) => String(field.value || "").trim()).length;
      return { done, total: fields.length || Number(section.dataset.total || 0) };
    }

    const questions = [...section.querySelectorAll(".supplier-question")].filter(
      (question) => !question.hidden && question.dataset.dispensed !== "true"
    );
    const done = questions.filter((question) => {
      const fileInput = question.querySelector('[type="file"]:not([data-conditional-file])');
      if (fileInput) {
        const missingFile = Boolean(question.querySelector(".bg-yellow-lt"));
        return hasEvidence(question) || !missingFile;
      }

      const checked = question.querySelector("input[type='radio']:checked, input[type='checkbox']:checked");
      const evidenceWhenSim = question.querySelector("[data-evidence-when-sim]");
      if (evidenceWhenSim && checked?.value === "SIM") {
        return hasEvidence(question);
      }
      const select = question.querySelector("select");
      const text = question.querySelector("textarea, input:not([type='hidden']):not([type='radio']):not([type='checkbox']):not([type='file'])");
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

  const setQuestionDispensed = (question, dispensed) => {
    question.dataset.dispensed = dispensed ? "true" : "false";
    question.hidden = dispensed;
    question.classList.toggle("is-dispensed", dispensed);
    question.style.display = dispensed ? "none" : "";
    question.querySelectorAll("input, select, textarea, button").forEach((field) => {
      if (dispensed) {
        field.disabled = true;
      } else {
        field.disabled = question.dataset.baseEditable !== "true";
      }
    });
  };

  const applyDispensaRules = (form) => {
    form.querySelectorAll("[data-section-progress]").forEach((section) => {
      const questions = [...section.querySelectorAll("[data-question-row]")];
      let dispensaAtiva = false;
      questions.forEach((question) => {
        if (dispensaAtiva) {
          setQuestionDispensed(question, true);
          return;
        }

        setQuestionDispensed(question, false);
        if (question.dataset.dispensaTrigger === "true") {
          const sim = question.querySelector("input[type='radio'][value='SIM']:checked");
          dispensaAtiva = Boolean(sim);
        }
      });
    });
  };

  const syncEvidenceWhenSim = (form) => {
    form.querySelectorAll("[data-evidence-when-sim]").forEach((block) => {
      const question = block.closest("[data-question-row]");
      if (!question) return;

      const simChecked = Boolean(question.querySelector("input[type='radio'][value='SIM']:checked"));
      const hidden = !simChecked || question.hidden || question.dataset.dispensed === "true";
      const editable = question.dataset.baseEditable === "true" && !hidden;
      block.hidden = hidden;
      block.querySelectorAll("input, button").forEach((field) => {
        field.disabled = !editable;
        if (hidden && field.matches("[data-file-input]")) {
          field.value = "";
          const selected = block.querySelector("[data-file-selected]");
          const clear = block.querySelector("[data-file-clear]");
          if (selected) {
            selected.textContent = "Nenhum arquivo selecionado";
            selected.classList.add("is-empty");
          }
          if (clear) clear.classList.add("is-filtered-out");
        }
      });
    });
  };

  const getProgressTotals = (form) => {
    return [...form.querySelectorAll("[data-section-progress]")].reduce(
      (totals, section) => {
        const { done, total } = countSection(section);
        totals.done += done;
        totals.total += total;
        if (section.id !== "dados") {
          totals.pendingFiles += [...section.querySelectorAll("[data-question-row]")].filter((question) => {
            if (question.hidden || question.dataset.dispensed === "true") return false;
            const fileInput = question.querySelector("[data-file-input]");
            if (!fileInput) return false;
            const evidenceWhenSim = question.querySelector("[data-evidence-when-sim]");
            if (evidenceWhenSim && !question.querySelector("input[type='radio'][value='SIM']:checked")) return false;
            const missingFile = Boolean(question.querySelector(".bg-yellow-lt"));
            return (missingFile || evidenceWhenSim) && !hasEvidence(question);
          }).length;
        }
        return totals;
      },
      { done: 0, total: 0, pendingFiles: 0 }
    );
  };

  const updateOverallProgress = (form) => {
    const { done, total, pendingFiles } = getProgressTotals(form);
    const pending = Math.max(total - done, 0);
    const percent = total ? Math.round((done / total) * 100) : 0;
    const progressNumber = form.querySelector("[data-overall-progress]");
    const progressBar = form.querySelector("[data-overall-progress-bar]");
    const pendingCopy = form.querySelector("[data-pending-copy]");
    const submitFinal = form.querySelector("[data-submit-final]");

    if (progressNumber) progressNumber.innerHTML = `${percent}<span>%</span>`;
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (pendingCopy) {
      const respostaLabel = pending === 1 ? "resposta" : "respostas";
      const anexoLabel = pendingFiles === 1 ? "anexo" : "anexos";
      pendingCopy.textContent = `Faltam ${pending} ${respostaLabel} e ${pendingFiles} ${anexoLabel}.`;
    }
    if (submitFinal) submitFinal.disabled = pending > 0;
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
        const maxFiles = Number(input.dataset.maxFiles || 1);
        const files = [...(input.files || [])];
        if (files.length > maxFiles) {
          if (window.DataTransfer) {
            const transfer = new DataTransfer();
            files.slice(0, maxFiles).forEach((file) => transfer.items.add(file));
            input.files = transfer.files;
          } else {
            input.value = "";
          }
        }

        const selectedFiles = [...(input.files || [])];
        if (selectedFiles.length) {
          const names = selectedFiles.map((file) => `${file.name} (${formatBytes(file.size)})`).join(", ");
          selected.textContent =
            files.length > maxFiles ? `Máximo de ${maxFiles} arquivos. Selecionados: ${names}` : names;
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

    applyDispensaRules(form);
    syncEvidenceWhenSim(form);
    updateSectionProgress(form);
    updateOverallProgress(form);
    updateSummary(form);
    initSectionNavigation(form);
    initFileInputs(form);
    initProgressAnimation(form);
    initFirstPending(form);

    form.addEventListener("input", () => {
      applyDispensaRules(form);
      syncEvidenceWhenSim(form);
      updateSectionProgress(form);
      updateOverallProgress(form);
      updateSummary(form);
    });
    form.addEventListener("change", () => {
      applyDispensaRules(form);
      syncEvidenceWhenSim(form);
      updateSectionProgress(form);
      updateOverallProgress(form);
      updateSummary(form);
    });
  };

  const initForms = () => {
    document.querySelectorAll("[data-evaluation-form]").forEach(initForm);
  };

  window.CesariModules = window.CesariModules || {};
  window.CesariModules.forms = { init: initForms };
})();
