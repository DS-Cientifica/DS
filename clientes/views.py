import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse


def _fetch_json(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Axion/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalizar_brasilapi(payload):
    return {
        "razao_social": payload.get("razao_social", ""),
        "nome_fantasia": payload.get("nome_fantasia", "") or payload.get("razao_social", ""),
        "logradouro": payload.get("logradouro", ""),
        "numero": payload.get("numero", ""),
        "bairro": payload.get("bairro", ""),
        "municipio": payload.get("municipio", ""),
        "uf": payload.get("uf", ""),
        "cep": payload.get("cep", ""),
        "inscricao_estadual": payload.get("inscricao_estadual", "") or payload.get("ie", ""),
        "ddd_telefone_1": payload.get("ddd_telefone_1", ""),
        "ddd_telefone_2": payload.get("ddd_telefone_2", ""),
        "email": payload.get("email", ""),
    }


def _normalizar_cnpjws(payload):
    estabelecimento = payload.get("estabelecimento", {}) or {}
    telefone1 = estabelecimento.get("telefone1", "") or estabelecimento.get("ddd1", "")
    telefone2 = estabelecimento.get("telefone2", "") or estabelecimento.get("ddd2", "")
    return {
        "razao_social": payload.get("razao_social", ""),
        "nome_fantasia": estabelecimento.get("nome_fantasia", "") or payload.get("razao_social", ""),
        "logradouro": estabelecimento.get("logradouro", ""),
        "numero": estabelecimento.get("numero", ""),
        "bairro": estabelecimento.get("bairro", ""),
        "municipio": estabelecimento.get("cidade", {}).get("nome", ""),
        "uf": estabelecimento.get("estado", {}).get("sigla", ""),
        "cep": estabelecimento.get("cep", ""),
        "inscricao_estadual": estabelecimento.get("inscricoes_estaduais", [{}])[0].get("inscricao_estadual", "") if estabelecimento.get("inscricoes_estaduais") else "",
        "ddd_telefone_1": telefone1,
        "ddd_telefone_2": telefone2,
        "email": estabelecimento.get("email", ""),
    }


def _normalizar_receitaws(payload):
    return {
        "razao_social": payload.get("nome", ""),
        "nome_fantasia": payload.get("fantasia", "") or payload.get("nome", ""),
        "logradouro": payload.get("logradouro", ""),
        "numero": payload.get("numero", ""),
        "bairro": payload.get("bairro", ""),
        "municipio": payload.get("municipio", ""),
        "uf": payload.get("uf", ""),
        "cep": payload.get("cep", ""),
        "inscricao_estadual": payload.get("ie", ""),
        "ddd_telefone_1": payload.get("telefone", ""),
        "ddd_telefone_2": "",
        "email": payload.get("email", ""),
    }


@staff_member_required
def consultar_cnpj(request, cnpj):
    cnpj_limpo = "".join(ch for ch in str(cnpj or "") if ch.isdigit())

    if len(cnpj_limpo) != 14:
        return JsonResponse({"ok": False, "erro": "CNPJ inválido."}, status=400)

    provedores = [
        ("BrasilAPI", f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}", _normalizar_brasilapi),
        ("CNPJ.ws", f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}", _normalizar_cnpjws),
        ("ReceitaWS", f"https://receitaws.com.br/v1/cnpj/{cnpj_limpo}", _normalizar_receitaws),
    ]
    erros = []

    for nome, url, normalizador in provedores:
        try:
            payload = _fetch_json(url)
            return JsonResponse({"ok": True, "dados": normalizador(payload), "fonte": nome})
        except HTTPError as exc:
            detalhe = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
            erros.append({"fonte": nome, "status_code": exc.code, "detalhe": detalhe})
        except URLError as exc:
            erros.append({"fonte": nome, "erro": str(exc.reason)})
        except Exception as exc:
            erros.append({"fonte": nome, "erro": str(exc)})

    return JsonResponse(
        {
            "ok": False,
            "erro": "Falha ao consultar CNPJ nos provedores disponíveis.",
            "tentativas": erros,
        },
        status=502,
    )
