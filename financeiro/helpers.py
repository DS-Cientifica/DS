from decimal import Decimal

from comercial.views import EMPRESA_PROPOSTA


EMPRESA_COMPRADORA = {
    "empresa": EMPRESA_PROPOSTA["nome"],
    "cnpj": EMPRESA_PROPOSTA["cnpj"],
    "endereco": " Avenida Reynaldo de Porcari, 2788 - Jardim Tereza Cristina",
    "cidade": EMPRESA_PROPOSTA["cidade"].replace("-SP", ""),
    "estado": "SP",
    "telefone": EMPRESA_PROPOSTA["telefone"],
    "email": "contato@dscientifica.com.br",
}


def formatar_moeda(valor):
    valor = Decimal(valor or 0)
    texto = f"{valor:,.2f}"
    return f"R$ {texto}".replace(",", "X").replace(".", ",").replace("X", ".")


def endereco_cliente(cliente):
    partes = [
        cliente.endereco,
        cliente.numero,
        cliente.bairro,
        cliente.cidade,
        cliente.uf,
        cliente.cep,
    ]
    return " - ".join(str(parte).strip() for parte in partes if parte)


def contato_principal_cliente(cliente):
    if not cliente:
        return None
    return cliente.contatos.filter(principal=True).first() or cliente.contatos.first()
