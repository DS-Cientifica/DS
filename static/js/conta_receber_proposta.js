(function ($) {
    "use strict";

    function setCliente(clienteId, clienteLabel) {
        var $cliente = $("#id_cliente");

        if (!$cliente.length || !clienteId) {
            return;
        }

        if (!$cliente.find("option[value='" + clienteId + "']").length) {
            $cliente.append(new Option(clienteLabel, clienteId, true, true));
        }

        $cliente.val(clienteId).trigger("change");
    }

    function preencherContaReceber(propostaId) {
        if (!propostaId) {
            return;
        }

        $.getJSON("/admin/financeiro/contareceber/proposta/" + propostaId + "/dados/", function (data) {
            setCliente(data.cliente_id, data.cliente_label);

            if (data.descricao) {
                $("#id_descricao").val(data.descricao);
            }

            if (data.valor) {
                $("#id_valor").val(data.valor);
            }
        });
    }

    $(function () {
        var $proposta = $("#id_proposta");

        if (!$proposta.length) {
            return;
        }

        $proposta.on("change", function () {
            preencherContaReceber($(this).val());
        });
    });
})(django.jQuery);
