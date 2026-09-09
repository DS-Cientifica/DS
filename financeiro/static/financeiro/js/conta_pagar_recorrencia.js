(function () {
    "use strict";

    function atualizarRecorrencia() {
        const tipo = document.getElementById("id_tipo_recorrencia");
        const total = document.getElementById("id_total_ocorrencias");
        if (!tipo || !total) return;

        const linha = total.closest(".form-row");
        const recorrente = tipo.value !== "unica";
        if (linha) linha.style.display = recorrente ? "" : "none";

        if (!recorrente) {
            total.value = "1";
        } else if (Number(total.value || 0) < 2) {
            total.value = tipo.value === "fixa_mensal" ? "12" : "2";
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const tipo = document.getElementById("id_tipo_recorrencia");
        if (tipo) tipo.addEventListener("change", atualizarRecorrencia);
        atualizarRecorrencia();
    });
}());
