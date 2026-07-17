(function () {
  function parseDecimal(value) {
    if (value === null || value === undefined) {
      return 0;
    }

    var normalized = String(value).trim().replace(/\./g, "").replace(",", ".");
    var parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function formatDecimal(value) {
    return value.toFixed(2).replace(".", ",");
  }

  function marginFactor(margemPercentual) {
    if (margemPercentual >= 100) {
      return 1;
    }
    return 1 / (1 - (margemPercentual / 100));
  }

  function getInlineRows() {
    return Array.from(document.querySelectorAll(".dynamic-itens, .dynamic-itemproposta_set"));
  }

  function recalculateTotals() {
    var margemField = document.getElementById("id_margem_percentual");
    var totalField = document.getElementById("id_total");
    var descontoGeralField = document.getElementById("id_desconto_geral");
    var freteField = document.getElementById("id_frete_valor");
    var outrasDespesasField = document.getElementById("id_outras_despesas");
    var seguroField = document.getElementById("id_seguro_valor");

    var margemPercentual = parseDecimal(margemField ? margemField.value : 0);
    var fatorMargem = marginFactor(margemPercentual);
    var subtotal = 0;
    var descontoItens = 0;

    getInlineRows().forEach(function (row) {
      if (row.style.display === "none") {
        return;
      }

      var quantidadeField = row.querySelector('input[name$="-quantidade"]');
      var valorUnitarioField = row.querySelector('input[name$="-valor_unitario"]');
      var descontoField = row.querySelector('input[name$="-desconto"]');
      var valorTotalField = row.querySelector('input[name$="-valor_total"]');
      var deleteField = row.querySelector('input[name$="-DELETE"]');

      if (!quantidadeField || !valorUnitarioField || !descontoField || !valorTotalField) {
        return;
      }
      if (deleteField && deleteField.checked) {
        return;
      }

      var quantidade = parseDecimal(quantidadeField.value || 0);
      var valorUnitario = parseDecimal(valorUnitarioField.value || 0);
      var desconto = parseDecimal(descontoField.value || 0);
      var brutoComMargem = quantidade * (valorUnitario * fatorMargem);
      var totalItem = brutoComMargem - desconto;

      if (totalItem < 0) {
        totalItem = 0;
      }

      valorTotalField.value = formatDecimal(totalItem);
      subtotal += brutoComMargem;
      descontoItens += desconto;
    });

    var subtotalLiquido = subtotal - descontoItens;
    var descontoGeral = parseDecimal(descontoGeralField ? descontoGeralField.value : 0);
    var frete = parseDecimal(freteField ? freteField.value : 0);
    var outrasDespesas = parseDecimal(outrasDespesasField ? outrasDespesasField.value : 0);
    var seguro = parseDecimal(seguroField ? seguroField.value : 0);
    var total = subtotalLiquido - descontoGeral + frete + outrasDespesas + seguro;

    if (total < 0) {
      total = 0;
    }

    if (totalField) {
      totalField.value = formatDecimal(total);
    }
  }

  function bindEvents() {
    [
      "id_margem_percentual",
      "id_desconto_geral",
      "id_frete_valor",
      "id_outras_despesas",
      "id_seguro_valor"
    ].forEach(function (fieldId) {
      var field = document.getElementById(fieldId);
      if (field) {
        field.addEventListener("input", recalculateTotals);
        field.addEventListener("change", recalculateTotals);
      }
    });

    document.addEventListener("input", function (event) {
      if (event.target.matches('input[name$="-quantidade"], input[name$="-valor_unitario"], input[name$="-desconto"]')) {
        recalculateTotals();
      }
    });

    document.addEventListener("change", function (event) {
      if (event.target.matches('input[name$="-DELETE"]')) {
        recalculateTotals();
      }
    });

    if (window.django && window.django.jQuery) {
      window.django.jQuery(document).on("formset:added", function () {
        recalculateTotals();
      });
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    bindEvents();
    recalculateTotals();
  });
})();
