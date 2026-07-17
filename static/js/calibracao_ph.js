(function () {
  function setFieldValue(fieldId, value) {
    var field = document.getElementById(fieldId);
    if (!field) {
      return;
    }
    field.value = value || "";
    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function setAutocompleteValue(fieldId, value, text) {
    var select = document.getElementById(fieldId);
    if (!select) {
      return;
    }

    var option = null;
    for (var i = 0; i < select.options.length; i += 1) {
      if (select.options[i].value === value) {
        option = select.options[i];
        break;
      }
    }

    if (!option) {
      option = new Option(text || value, value, true, true);
      select.add(option);
    } else {
      option.selected = true;
      if (text) {
        option.text = text;
      }
    }

    select.value = value;
    if (window.django && window.django.jQuery) {
      window.django.jQuery(select).trigger("change");
    } else {
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function preencherDadosInstrumento(data) {
    if (!data) {
      return;
    }

    if (data.cliente && data.cliente.id) {
      setAutocompleteValue("id_cliente", data.cliente.id, data.cliente.text || data.cliente.razao_social);
    }

    setFieldValue("id_contratante", data.contratante);
    setFieldValue("id_endereco_contratante", data.endereco_contratante);
    setFieldValue("id_endereco_cliente", data.endereco_cliente);
    setFieldValue("id_local_calibracao", data.local_calibracao);
    setFieldValue("id_equipamento_calibrado", data.equipamento_calibrado);
    setFieldValue("id_numero_identificacao", data.numero_identificacao);
    setFieldValue("id_capacidade_total", data.capacidade_total);
    setFieldValue("id_faixa_calibrada", data.faixa_calibrada);
    setFieldValue("id_menor_resolucao", data.menor_resolucao);
    setFieldValue("id_unidade_leitura", data.unidade_leitura);
  }

  function preencherMetodo(data) {
    if (!data || !data.documento || !data.documento.id) {
      return;
    }

    setAutocompleteValue("id_procedimento_documento", data.documento.id, data.documento.text || data.codigo);
    setFieldValue("id_procedimento_numero", data.codigo);
    setFieldValue("id_procedimento_revisao", data.revisao);
  }

  function carregarDadosInstrumento() {
    var instrumentoField = document.getElementById("id_instrumento");
    if (!instrumentoField || !instrumentoField.value) {
      return;
    }

    var urlBase = instrumentoField.getAttribute("data-instrumento-dados-url");
    if (!urlBase) {
      return;
    }

    fetch(urlBase.replace("__instrumento__", instrumentoField.value), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Falha ao buscar dados do instrumento.");
        }
        return response.json();
      })
      .then(preencherDadosInstrumento)
      .catch(function () {
        // Mantem os campos editaveis mesmo se o preenchimento automatico falhar.
      });
  }

  function carregarMetodoPorTipo() {
    var tipoField = document.getElementById("id_tipo_aplicacao");
    if (!tipoField || !tipoField.value) {
      return;
    }

    var urlBase = tipoField.getAttribute("data-metodo-dados-url");
    if (!urlBase) {
      return;
    }

    fetch(urlBase.replace("__tipo__", tipoField.value), {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Falha ao buscar metodo.");
        }
        return response.json();
      })
      .then(preencherMetodo)
      .catch(function () {
        // Mantem os campos editaveis mesmo se o preenchimento automatico falhar.
      });
  }

  function showTab(target) {
    var sections = document.querySelectorAll("[data-turbidez-section]");
    sections.forEach(function (section) {
      section.style.display = section.getAttribute("data-turbidez-section") === target ? "" : "none";
    });

    var tabs = document.querySelectorAll(".turbidez-tab");
    tabs.forEach(function (tab) {
      tab.classList.toggle("is-active", tab.getAttribute("data-tab-target") === target);
    });
  }

  function moveSlopeFieldset(fieldsets, inlineGroups) {
    if (fieldsets.length < 5 || inlineGroups.length < 3) {
      return;
    }

    var slopeFieldset = fieldsets[2];
    var inlineQuimica = inlineGroups[2];
    if (!slopeFieldset || !inlineQuimica || slopeFieldset.dataset.slopeMoved === "1") {
      return;
    }

    inlineQuimica.insertAdjacentElement("afterend", slopeFieldset);
    slopeFieldset.dataset.slopeMoved = "1";
  }

  function decorateTabs() {
    var tabs = document.querySelectorAll(".turbidez-tab");
    if (!tabs.length) {
      return;
    }

    var fieldsets = document.querySelectorAll("#content-main form fieldset.module");
    var inlineGroups = document.querySelectorAll("#content-main form .inline-group");

    moveSlopeFieldset(fieldsets, inlineGroups);

    if (fieldsets.length >= 5) {
      fieldsets[0].setAttribute("data-turbidez-section", "planilha");
      fieldsets[1].setAttribute("data-turbidez-section", "planilha");
      fieldsets[2].setAttribute("data-turbidez-section", "calibracao");
      fieldsets[3].setAttribute("data-turbidez-section", "certificado");
      fieldsets[4].setAttribute("data-turbidez-section", "certificado");
    }

    if (inlineGroups.length >= 4) {
      inlineGroups[0].setAttribute("data-turbidez-section", "padroes");
      inlineGroups[1].setAttribute("data-turbidez-section", "calibracao");
      inlineGroups[2].setAttribute("data-turbidez-section", "calibracao");
      inlineGroups[3].setAttribute("data-turbidez-section", "incerteza");
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        showTab(tab.getAttribute("data-tab-target"));
      });
    });

    showTab("planilha");
  }

  function setupInstrumentoAutofill() {
    var instrumentoField = document.getElementById("id_instrumento");
    if (!instrumentoField) {
      return;
    }

    instrumentoField.addEventListener("change", carregarDadosInstrumento);

    if (window.django && window.django.jQuery) {
      window.django.jQuery(instrumentoField).on("select2:select", carregarDadosInstrumento);
    }

    if (instrumentoField.value) {
      carregarDadosInstrumento();
    }
  }

  function setupMetodoAutofill() {
    var tipoField = document.getElementById("id_tipo_aplicacao");
    if (!tipoField) {
      return;
    }

    tipoField.addEventListener("change", carregarMetodoPorTipo);

    if (tipoField.value) {
      carregarMetodoPorTipo();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    decorateTabs();
    setupInstrumentoAutofill();
    setupMetodoAutofill();
  });
})();
