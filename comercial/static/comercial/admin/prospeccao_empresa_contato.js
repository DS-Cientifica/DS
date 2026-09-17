(function ($) {
  "use strict";

  $(function () {
    const $empresa = $("#id_empresa_prospecto");
    const $contato = $("#id_prospecto");
    const url = $contato.data("contatos-url");

    if (!$empresa.length || !$contato.length || !url) {
      return;
    }

    function rotulo(contato) {
      const detalhes = [contato.cargo, contato.email, contato.telefone].filter(Boolean);
      const uso = contato.em_uso ? " — já possui prospecção" : "";
      return contato.nome + (detalhes.length ? " — " + detalhes.join(" | ") : "") + uso;
    }

    function carregarContatos() {
      const empresaId = $empresa.val();
      const selecionado = $contato.val();
      $contato.empty().append(new Option("---------", ""));

      if (!empresaId) {
        $contato.prop("disabled", true).trigger("change");
        return;
      }

      $contato.prop("disabled", true);
      $.getJSON(url, { empresa_id: empresaId })
        .done(function (resposta) {
          (resposta.contatos || []).forEach(function (contato) {
            $contato.append(new Option(rotulo(contato), contato.id, false, contato.id === selecionado));
          });
        })
        .always(function () {
          $contato.prop("disabled", false).trigger("change");
        });
    }

    $empresa.on("change select2:select select2:clear", carregarContatos);
    if (!$empresa.val()) {
      $contato.prop("disabled", true);
    }
  });
})(django.jQuery);
