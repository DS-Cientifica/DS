(function () {
  function getFields() {
    return {
      cliente: document.getElementById("id_cliente"),
      responsavel: document.getElementById("id_responsavel"),
      adicionar: document.getElementById("add_id_responsavel")
    };
  }

  function updateAddLink(link, clienteId) {
    if (!link) {
      return;
    }
    var url = new URL(link.href, window.location.origin);
    if (clienteId) {
      url.searchParams.set("cliente", clienteId);
    } else {
      url.searchParams.delete("cliente");
    }
    link.href = url.toString();
  }

  function replaceOptions(select, contatos, selectedId, clientChanged) {
    select.innerHTML = "";
    select.appendChild(new Option("---------", ""));

    contatos.forEach(function (contato) {
      var detalhes = [];
      if (contato.cargo) {
        detalhes.push(contato.cargo);
      }
      if (contato.email) {
        detalhes.push(contato.email);
      }
      var texto = contato.nome + (detalhes.length ? " — " + detalhes.join(" — ") : "");
      select.appendChild(new Option(texto, contato.id));
    });

    var selecionadoAindaExiste = contatos.some(function (contato) {
      return String(contato.id) === String(selectedId);
    });
    if (!clientChanged && selecionadoAindaExiste) {
      select.value = selectedId;
      return;
    }

    var principal = contatos.find(function (contato) {
      return contato.principal;
    });
    if (principal) {
      select.value = principal.id;
    } else if (contatos.length === 1) {
      select.value = contatos[0].id;
    } else {
      select.value = "";
    }
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function loadContacts(clientChanged) {
    var fields = getFields();
    var config = window.propostaContatosConfig || {};
    if (!fields.cliente || !fields.responsavel || !config.url) {
      return;
    }

    var clienteId = fields.cliente.value;
    var selectedId = fields.responsavel.value;
    updateAddLink(fields.adicionar, clienteId);

    if (!clienteId) {
      replaceOptions(fields.responsavel, [], "", true);
      fields.responsavel.disabled = true;
      return;
    }

    fields.responsavel.disabled = true;
    fetch(config.url + "?cliente=" + encodeURIComponent(clienteId), {
      headers: { "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Não foi possível carregar os contatos do cliente.");
        }
        return response.json();
      })
      .then(function (payload) {
        replaceOptions(fields.responsavel, payload.contatos || [], selectedId, clientChanged);
        fields.responsavel.disabled = false;
      })
      .catch(function () {
        replaceOptions(fields.responsavel, [], "", true);
        fields.responsavel.disabled = false;
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var fields = getFields();
    if (!fields.cliente) {
      return;
    }
    if (window.django && window.django.jQuery) {
      window.django.jQuery(fields.cliente).on("change.propostaContatos", function () {
        loadContacts(true);
      });
    } else {
      fields.cliente.addEventListener("change", function () {
        loadContacts(true);
      });
    }
    loadContacts(false);
  });
})();
