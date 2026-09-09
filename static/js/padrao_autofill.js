(function () {
    "use strict";

    const campos = {
        codigo: ["codigo"],
        descricao: ["descricao"],
        numero_certificado: ["numero_certificado"],
        laboratorio_emitente: ["laboratorio_emitente"],
        data_calibracao: ["data_calibracao"],
        validade: ["validade"],
        resolucao: ["resolucao"],
        incerteza: ["incerteza", "incerteza_expandida"],
        fator_k: ["fator_k"],
        graus_liberdade: ["graus_liberdade"],
        unidade: ["unidade"],
        valor_nominal: ["valor_nominal"],
    };

    function urlPadrao(id) {
        const marcador = "/calibracao/";
        const indice = window.location.pathname.indexOf(marcador);
        const prefixo = indice >= 0 ? window.location.pathname.slice(0, indice) : "/admin";
        return prefixo + "/calibracao/padrao/" + encodeURIComponent(id) + "/dados/";
    }

    function localizarCampo(row, nome) {
        return row.querySelector('[name$="-' + nome + '"]');
    }

    function preencherCampo(row, nome, valor) {
        const input = localizarCampo(row, nome);
        if (input) {
            input.value = valor === null || valor === undefined ? "" : String(valor);
            input.dispatchEvent(new Event("input", {bubbles: true}));
            input.classList.add("padrao-auto-preenchido");
            return true;
        }
        const celula = row.querySelector(".field-" + nome);
        const readonly = celula && (celula.querySelector(".readonly") || celula);
        if (readonly) {
            readonly.textContent = valor || "—";
            readonly.classList.add("padrao-auto-preenchido-readonly");
            return true;
        }
        return false;
    }

    function preencherLinha(row, dados) {
        Object.entries(campos).forEach(function ([origem, destinos]) {
            destinos.forEach(function (destino) {
                preencherCampo(row, destino, dados[origem]);
            });
        });
        row.dataset.padraoValorNominal = dados.valor_nominal || "";
        row.classList.add("padrao-dados-carregados");
        let aviso = row.querySelector(".padrao-autofill-status");
        if (!aviso) {
            aviso = document.createElement("span");
            aviso.className = "padrao-autofill-status";
            const celulaPadrao = row.querySelector(".field-padrao") || row.lastElementChild;
            if (celulaPadrao) celulaPadrao.appendChild(aviso);
        }
        if (aviso) aviso.textContent = "Dados metrológicos carregados";
    }

    async function carregar(select) {
        const row = select.closest("tr.form-row, .inline-related");
        if (!row || !select.value) return;
        try {
            const resposta = await fetch(urlPadrao(select.value), {
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!resposta.ok) throw new Error("Falha ao consultar o padrão");
            preencherLinha(row, await resposta.json());
        } catch (erro) {
            let aviso = row.querySelector(".padrao-autofill-status");
            if (!aviso) {
                aviso = document.createElement("span");
                aviso.className = "padrao-autofill-status is-error";
                const celulaPadrao = row.querySelector(".field-padrao") || row.lastElementChild;
                if (celulaPadrao) celulaPadrao.appendChild(aviso);
            }
            if (aviso) aviso.textContent = "Não foi possível carregar os dados";
        }
    }

    document.addEventListener("change", function (evento) {
        if (evento.target.matches('[name$="-padrao"]')) carregar(evento.target);
    });
})();
