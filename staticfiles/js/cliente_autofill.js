document.addEventListener("DOMContentLoaded", function () {

    // =========================
    // CNPJ (PRINCIPAL)
    // =========================
    alert("JS carregado");
    const cnpjField = document.querySelector("#id_cnpj");

    if (cnpjField) {
        cnpjField.addEventListener("blur", function () {

            const cnpj = cnpjField.value.replace(/\D/g, "");

            if (cnpj.length === 14) {
                fetch(`https://brasilapi.com.br/api/cnpj/v1/${cnpj}`)
                    .then(response => response.json())
                    .then(data => {

                        document.querySelector("#id_razao_social").value = data.razao_social || "";
                        document.querySelector("#id_nome_empresa").value = data.nome_fantasia || "";

                        document.querySelector("#id_endereco").value = data.logradouro || "";
                        document.querySelector("#id_numero").value = data.numero || "";
                        document.querySelector("#id_bairro").value = data.bairro || "";
                        document.querySelector("#id_cidade").value = data.municipio || "";
                        document.querySelector("#id_uf").value = data.uf || "";
                        document.querySelector("#id_cep").value = data.cep || "";

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

                            document.querySelector("#id_endereco").value = data.logradouro || "";
                            document.querySelector("#id_bairro").value = data.bairro || "";
                            document.querySelector("#id_cidade").value = data.localidade || "";
                            document.querySelector("#id_uf").value = data.uf || "";

                        })
                        .catch(error => console.log("Erro ao buscar CEP:", error));
                }
            }
        });
    }

});