(function () {
    "use strict";

    function iniciarPreenchimentoAutomatico() {
        const instrumento = document.getElementById("id_instrumento");
        const cliente = document.getElementById("id_cliente");
        const ordemServico = document.getElementById("id_ordem_servico");
        if (!instrumento || !ordemServico) {
            return;
        }

        let valorAutomatico = "";

        async function atualizarOrdemServico() {
            const instrumentoId = instrumento.value;
            const valorAtual = ordemServico.value.trim();
            const podeSubstituir = !valorAtual || valorAtual === valorAutomatico;

            if (!podeSubstituir) {
                return;
            }
            if (!instrumentoId) {
                if (valorAtual === valorAutomatico) {
                    ordemServico.value = "";
                    valorAutomatico = "";
                }
                return;
            }

            const parametros = new URLSearchParams({ instrumento_id: instrumentoId });
            if (cliente && cliente.value) {
                parametros.set("cliente_id", cliente.value);
            }

            try {
                const resposta = await fetch(
                    `/calibracao/ajax/ordem-servico-instrumento/?${parametros.toString()}`,
                    { headers: { "X-Requested-With": "XMLHttpRequest" } }
                );
                if (!resposta.ok) {
                    return;
                }
                const dados = await resposta.json();
                const novoValor = dados.encontrada ? dados.numero : "";
                ordemServico.value = novoValor;
                valorAutomatico = novoValor;
                ordemServico.dispatchEvent(new Event("change", { bubbles: true }));
            } catch (erro) {
                // O preenchimento no servidor continua garantindo a rastreabilidade ao salvar.
            }
        }

        instrumento.addEventListener("change", atualizarOrdemServico);
        if (cliente) {
            cliente.addEventListener("change", atualizarOrdemServico);
        }

        // Os campos de instrumento do Django Admin usam Select2. Esse evento
        // não é propagado como um "change" nativo em todos os navegadores.
        if (window.django && window.django.jQuery) {
            window.django.jQuery(instrumento).on(
                "select2:select",
                atualizarOrdemServico
            );
        }
        atualizarOrdemServico();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", iniciarPreenchimentoAutomatico);
    } else {
        iniciarPreenchimentoAutomatico();
    }
})();
