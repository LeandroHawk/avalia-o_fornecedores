document.addEventListener("DOMContentLoaded", () => {
  const respostaSelect = document.querySelector("[data-resposta-select]");
  if (!respostaSelect) return;

  const evidencia = document.querySelector("[data-evidencia-field]");
  const justificativa = document.querySelector("[data-justificativa-field]");
  const refresh = () => {
    if (evidencia) evidencia.classList.toggle("d-none", respostaSelect.value !== "SIM");
    if (justificativa) justificativa.classList.toggle("d-none", respostaSelect.value !== "NAO");
  };
  respostaSelect.addEventListener("change", refresh);
  refresh();
});
