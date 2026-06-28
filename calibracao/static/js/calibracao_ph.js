(function () {
    function byId(id) {
        return document.getElementById(id);
    }

    function setValue(id, value) {
        var el = byId(id);
        if (!el || value === undefined || value === null) {
            return;
        }
        el.value = value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        el.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function setSelected(id, value) {
        var el = byId(id);
        if (!el || value === undefined || value === null) {
            return;
        }
        el.value = value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    async function preencherInstrumento() {
        var instrumento = byId("id_instrumento");
        if (!instrumento || !instrumento.value) {
            return;
        }
        var url = instrumento.getAttribute("data-instrumento-dados-url");
        if (!url) {
            return;
        }

        var response = await fetch(url.replace("__instrumento__", instrumento.value), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        if (!response.ok) {
            return;
        }

        var data = await response.json();
        if (!data) {
            return;
        }

        setValue("id_cliente", data.cliente && data.cliente.id ? data.cliente.id : "");
        setValue("id_contratante", data.contratante || "");
        setValue("id_endereco_contratante", data.endereco_contratante || "");
        setValue("id_endereco_cliente", data.endereco_cliente || "");
        setSelected("id_local_calibracao", data.local_calibracao || "");
        setValue("id_equipamento_calibrado", data.equipamento_calibrado || "");
        setValue("id_numero_identificacao", data.numero_identificacao || "");
        setValue("id_marca", data.marca || "");
        setValue("id_modelo", data.modelo || "");
        setValue("id_numero_serie", data.numero_serie || "");
        setValue("id_capacidade_total", data.capacidade_total || "");
        setValue("id_faixa_calibrada", data.faixa_calibrada || "");
        setValue("id_menor_resolucao", data.menor_resolucao || "");
        setValue("id_resolucao_mv", data.resolucao_mv || "");
        setValue("id_resolucao_ph", data.resolucao_ph || "");
        setValue("id_identificacao_eletrodo", data.identificacao_eletrodo || "");
        setValue("id_id_sensor_temperatura", data.id_sensor_temperatura || "");
        setValue("id_unidade_leitura", data.unidade_leitura || "");
        setSelected("id_tipo_indicacao", data.tipo_indicacao || "");
    }

    document.addEventListener("DOMContentLoaded", function () {
        var instrumento = byId("id_instrumento");
        if (!instrumento) {
            return;
        }

        instrumento.addEventListener("change", function () {
            preencherInstrumento().catch(function () {});
        });

        if (instrumento.value) {
            preencherInstrumento().catch(function () {});
        }
    });
})();
