(function () {
  function getBasePath() {
    const path = window.location.pathname;
    const addMatch = path.match(/^(.*\/instrumento\/)add\/$/);
    if (addMatch) return addMatch[1];
    const changeMatch = path.match(/^(.*\/instrumento\/)[^/]+\/change\/$/);
    if (changeMatch) return changeMatch[1];
    return null;
  }

  function getObjectId() {
    const path = window.location.pathname;
    const changeMatch = path.match(/\/instrumento\/([^/]+)\/change\/$/);
    return changeMatch ? changeMatch[1] : "";
  }

  async function checkDuplicate() {
    const cliente = document.getElementById("id_cliente");
    const tag = document.getElementById("id_tag");
    const basePath = getBasePath();
    if (!cliente || !tag || !basePath) return { duplicate: false };

    const params = new URLSearchParams({
      cliente_id: cliente.value || "",
      tag: tag.value || "",
      object_id: getObjectId(),
    });
    const response = await fetch(basePath + "check-duplicate/?" + params.toString(), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!response.ok) return { duplicate: false };
    return response.json();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("form");
    const tag = document.getElementById("id_tag");
    if (!form) return;

    form.addEventListener("submit", async function (event) {
      if (tag && !tag.value.trim()) {
        const continuar = window.confirm(
          "A TAG do equipamento esta vazia. Isso e permitido, mas reduz a rastreabilidade operacional. Deseja continuar mesmo assim?"
        );
        if (!continuar) {
          event.preventDefault();
          return;
        }
      }

      const result = await checkDuplicate();
      if (!result || !result.duplicate) return;
      event.preventDefault();
      window.alert(result.message || "Já existe um instrumento com os mesmos dados informados.");
    });
  });
})();
