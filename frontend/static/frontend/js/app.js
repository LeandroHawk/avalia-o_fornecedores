(function () {
  const onReady = (callback) => {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
    } else {
      callback();
    }
  };

  const initSubmitFeedback = () => {
    document.addEventListener("submit", (event) => {
      const submitter = event.submitter;
      if (!submitter || !submitter.classList.contains("btn")) return;
      submitter.classList.add("disabled");
      submitter.setAttribute("aria-disabled", "true");
    });
  };

  const initResponsiveTables = () => {
    const helper = window.CesariModules?.tables?.initResponsiveLabels;
    if (!helper) return;
    document.querySelectorAll("table:not([data-table-enhanced])").forEach(helper);
  };

  onReady(() => {
    initResponsiveTables();
    window.CesariModules?.charts?.init();
    window.CesariModules?.tables?.init();
    window.CesariModules?.forms?.init();
    initSubmitFeedback();
  });
})();
