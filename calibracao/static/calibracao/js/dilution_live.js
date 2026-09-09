(function () {
    "use strict";

    let padraoOrigem = null;

    function numero(valor) {
        if (valor === null || valor === undefined || valor === "") return null;
        const normalizado = String(valor).trim().replace(/\s/g, "").replace(",", ".");
        const resultado = Number(normalizado);
        return Number.isFinite(resultado) ? resultado : null;
    }

    function formatar(valor) {
        if (!Number.isFinite(valor)) return "—";
        return valor.toLocaleString("pt-BR", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 9,
        });
    }

    function escrever(row, classe, texto) {
        const celula = row.querySelector("." + classe);
        if (!celula) return;
        const alvo = celula.querySelector(".readonly") || celula;
        alvo.textContent = texto;
        alvo.classList.toggle("dilution-live-value", texto !== "—");
    }

    function calcularLinha(row) {
        const alvoInput = row.querySelector('[name$="-valor_alvo"]');
        const finalInput = row.querySelector('[name$="-volume_final"]');
        const unidadeInput = row.querySelector('[name$="-unidade_volume"]');
        if (!alvoInput || !finalInput) return;

        const tipo = document.getElementById("id_tipo_preparacao");
        if (tipo && tipo.value !== "volumetrica") {
            escrever(row, "field-volume_aliquota_planejado", "Modelo não volumétrico");
            escrever(row, "field-volume_diluente_aproximado", "—");
            return;
        }

        const concentracaoOrigem = padraoOrigem ? numero(padraoOrigem.valor_nominal) : null;
        const alvo = numero(alvoInput.value);
        const volumeFinal = numero(finalInput.value);
        const unidade = (unidadeInput && unidadeInput.value) || "mL";

        if (!concentracaoOrigem || alvo === null || !volumeFinal) {
            escrever(row, "field-volume_aliquota_planejado", "—");
            escrever(row, "field-volume_diluente_aproximado", "—");
            return;
        }

        const aliquota = (alvo * volumeFinal) / concentracaoOrigem;
        const diluente = volumeFinal - aliquota;
        escrever(row, "field-volume_aliquota_planejado", formatar(aliquota) + " " + unidade);
        escrever(
            row,
            "field-volume_diluente_aproximado",
            diluente >= 0 ? formatar(diluente) + " " + unidade + " (completar até o traço)" : "Alvo acima do padrão-mãe"
        );
    }

    function recalcularTudo() {
        document.querySelectorAll("#resultados-group tr.form-row").forEach(calcularLinha);
    }

    function urlDadosPadrao(id) {
        const trecho = "/admin/calibracao/preparacaopadrao/";
        const indice = window.location.pathname.indexOf(trecho);
        const base = indice >= 0
            ? window.location.pathname.slice(0, indice) + trecho
            : trecho;
        return base + "padrao-dados/?id=" + encodeURIComponent(id);
    }

    async function buscarPadrao(id) {
        if (!id) return null;
        try {
            const resposta = await fetch(urlDadosPadrao(id), {
                headers: {"X-Requested-With": "XMLHttpRequest"},
                credentials: "same-origin",
            });
            return resposta.ok ? await resposta.json() : null;
        } catch (erro) {
            return null;
        }
    }

    async function carregarPadraoOrigem() {
        const select = document.getElementById("id_padrao_origem");
        const id = select && select.value;
        if (!id) {
            padraoOrigem = null;
            recalcularTudo();
            return;
        }
        padraoOrigem = await buscarPadrao(id);
        recalcularTudo();
    }

    async function preencherPeloRecipiente(select) {
        const row = select.closest("tr.form-row");
        if (!row || !select.value) return;
        const dados = await buscarPadrao(select.value);
        if (!dados) return;
        const finalInput = row.querySelector('[name$="-volume_final"]');
        const unidadeInput = row.querySelector('[name$="-unidade_volume"]');
        if (finalInput && !numero(finalInput.value) && numero(dados.valor_nominal)) {
            finalInput.value = dados.valor_nominal;
        }
        if (unidadeInput && dados.unidade && (!unidadeInput.value || unidadeInput.value === "mL")) {
            unidadeInput.value = dados.unidade;
        }
        calcularLinha(row);
    }

    document.addEventListener("input", function (evento) {
        if (evento.target.matches('[name$="-valor_alvo"], [name$="-volume_final"], [name$="-unidade_volume"]')) {
            const row = evento.target.closest("tr.form-row");
            if (row) calcularLinha(row);
        }
    });
    document.addEventListener("change", function (evento) {
        if (evento.target.id === "id_padrao_origem") carregarPadraoOrigem();
        if (evento.target.id === "id_tipo_preparacao") recalcularTudo();
        if (evento.target.matches('[name$="-recipiente_final"]')) preencherPeloRecipiente(evento.target);
    });

    if (window.django && django.jQuery) {
        django.jQuery(document).on("formset:added", function (_evento, row, formsetName) {
            if (formsetName === "resultados") calcularLinha(row.get ? row.get(0) : row);
        });
    }

    document.addEventListener("DOMContentLoaded", carregarPadraoOrigem);
})();
