document.addEventListener("DOMContentLoaded", function () {
    function setFieldValue(selector, value) {
        const field = document.querySelector(selector);
        if (field) {
            field.value = value || "";
        }
    }

    function formatPhone(value) {
        const digits = (value || "").replace(/\D/g, "");

        if (!digits) {
            return "";
        }

        if (digits.length === 10) {
            return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
        }

        if (digits.length === 11) {
            return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
        }

        return value || "";
    }

    // =========================
    // CNPJ (PRINCIPAL)
    // =========================
  
    const cnpjField = document.querySelector("#id_cnpj");

    if (cnpjField) {
        cnpjField.addEventListener("blur", function () {

            const cnpj = cnpjField.value.replace(/\D/g, "");

            if (cnpj.length === 14) {
                fetch(`https://brasilapi.com.br/api/cnpj/v1/${cnpj}`)
                    .then(response => response.json())
                    .then(data => {
                        const telefone1 = formatPhone(data.ddd_telefone_1 || "");
                        const telefone2 = formatPhone(data.ddd_telefone_2 || "");
                        const inscricaoEstadual = data.inscricao_estadual || data.ie || "";

                        setFieldValue("#id_razao_social", data.razao_social || "");
                        setFieldValue("#id_nome_empresa", data.nome_fantasia || data.razao_social || "");

                        setFieldValue("#id_endereco", data.logradouro || "");
                        setFieldValue("#id_numero", data.numero || "");
                        setFieldValue("#id_bairro", data.bairro || "");
                        setFieldValue("#id_cidade", data.municipio || "");
                        setFieldValue("#id_uf", data.uf || "");
                        setFieldValue("#id_cep", data.cep || "");

                        setFieldValue("#id_ie", inscricaoEstadual);
                        setFieldValue("#id_telefone", telefone1);
                        setFieldValue("#id_telefone2", telefone2);
                        setFieldValue("#id_email", data.email || "");

                    })
                    .catch(error => console.log("Erro ao buscar CNPJ:", error));
            }
        });
    }

    // =========================
    // CEP (FALLBACK)
    // =========================
    const cepField = document.querySelector("#id_cep");

    if (cepField) {
        cepField.addEventListener("blur", function () {

            const cep = cepField.value.replace(/\D/g, "");

            if (cep.length === 8) {

                // Só busca se endereço estiver vazio
                if (!document.querySelector("#id_endereco").value) {

                    fetch(`https://viacep.com.br/ws/${cep}/json/`)
                        .then(response => response.json())
                        .then(data => {
                            setFieldValue("#id_endereco", data.logradouro || "");
                            setFieldValue("#id_bairro", data.bairro || "");
                            setFieldValue("#id_cidade", data.localidade || "");
                            setFieldValue("#id_uf", data.uf || "");

                        })
                        .catch(error => console.log("Erro ao buscar CEP:", error));
                }
            }
        });
    }

});
