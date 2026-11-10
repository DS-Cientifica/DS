(function ($) {
    "use strict";

    function atualizarModoEtiqueta() {
        const modo = $("input[name='modo_etiqueta_qr']:checked").val();
        const $campo = $("#id_etiqueta_qr_selecionada");
        const $linha = $(".form-row.field-etiqueta_qr_selecionada");
        const mostrar = modo === "manual" || $campo.prop("disabled");
        $linha.toggle(mostrar);
    }

    $(function () {
        const $campo = $("#id_etiqueta_qr_selecionada");
        if (!$campo.length) {
            return;
        }

        if ($.fn.select2 && !$campo.hasClass("select2-hidden-accessible")) {
            $campo.select2({
                width: "100%",
                allowClear: true,
                placeholder: $campo.data("placeholder"),
                language: "pt-BR",
            });
        }

        $("input[name='modo_etiqueta_qr']").on("change", atualizarModoEtiqueta);
        atualizarModoEtiqueta();
    });
})(django.jQuery);
