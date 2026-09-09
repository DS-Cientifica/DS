import json
import re

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction

from clientes.models import Cliente
from comercial.models import Prospecto


ORIGEM = "Cliente inativo AXION"


class Command(BaseCommand):
    help = "Copia clientes inativos para a Base de prospects sem apagar o cadastro original."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Confirma a gravação. Sem esta opção, executa somente a prévia.",
        )

    def handle(self, *args, **options):
        plano = self._analisar()
        resumo = {
            "modo": "aplicacao" if options["apply"] else "pre_validacao",
            "clientes_inativos": len(plano),
            "novos_prospects": sum(item["prospecto"] is None for item in plano),
            "prospects_existentes_vinculados": sum(item["prospecto"] is not None for item in plano),
            "prospects_antes": Prospecto.objects.count(),
            "prospects_depois_previsto": Prospecto.objects.count()
            + sum(item["prospecto"] is None for item in plano),
            "clientes_preservados_como_inativos": Cliente.objects.filter(ativo=False).count(),
            "itens": [
                {
                    "cliente": item["cliente"].codigo,
                    "empresa": item["cliente"].razao_social,
                    "acao": "criar" if item["prospecto"] is None else "vincular_existente",
                    "prospecto": item["prospecto"].codigo if item["prospecto"] else None,
                }
                for item in plano
            ],
        }
        self.stdout.write(json.dumps(resumo, ensure_ascii=False, indent=2))

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Pré-validação concluída. Nenhum registro foi gravado."))
            return

        with transaction.atomic():
            novos = [item for item in plano if item["prospecto"] is None]
            codigos = iter(Prospecto.reservar_codigos(len(novos)))
            for item in plano:
                if item["prospecto"] is None:
                    self._criar(item, next(codigos))
                else:
                    self._vincular_existente(item)

        self.stdout.write(
            self.style.SUCCESS(
                f"Migração concluída: {len(novos)} criado(s) e "
                f"{len(plano) - len(novos)} prospect(s) existente(s) vinculado(s)."
            )
        )

    def _analisar(self):
        prospects = list(Prospecto.objects.all())
        por_referencia = {
            item.referencia_externa: item
            for item in prospects
            if item.origem == ORIGEM and item.referencia_externa
        }
        chaves = {item.chave_duplicidade: item for item in prospects}
        emails_empresa = {}
        for item in prospects:
            if not item.email:
                continue
            chave = (
                Prospecto._normalizar_texto(item.razao_social),
                item.email.strip().casefold(),
            )
            emails_empresa.setdefault(chave, []).append(item)

        plano = []
        destinos_usados = {}
        for cliente in Cliente.objects.filter(ativo=False).order_by("codigo", "razao_social"):
            dados = self._dados_cliente(cliente)
            referencia = str(cliente.pk)
            marcador = self._marcador(cliente)
            existente = por_referencia.get(referencia)
            motivo = "origem/referência"
            if existente is None:
                existentes_marcados = [
                    item for item in prospects if marcador in (item.observacoes or "")
                ]
                if len(existentes_marcados) > 1:
                    raise CommandError(f"Mais de um prospect vinculado ao cliente {cliente.codigo}.")
                existente = existentes_marcados[0] if existentes_marcados else None
                motivo = "marcador de origem"

            chave = Prospecto.gerar_chave_duplicidade(**dados["chave"])
            if existente is None and chave in chaves:
                existente = chaves[chave]
                motivo = "chave de duplicidade"

            if existente is None and dados["email"]:
                chave_email = (
                    Prospecto._normalizar_texto(dados["razao_social"]),
                    dados["email"].casefold(),
                )
                candidatos = emails_empresa.get(chave_email, [])
                if len(candidatos) == 1:
                    existente = candidatos[0]
                    motivo = "mesma empresa e e-mail"
                elif len(candidatos) > 1:
                    raise CommandError(
                        f"Correspondência ambígua por e-mail para {cliente.codigo}: "
                        + ", ".join(item.codigo for item in candidatos)
                    )

            if existente is not None:
                origem_anterior = destinos_usados.get(existente.pk)
                if origem_anterior and origem_anterior != cliente.pk:
                    raise CommandError(
                        f"Os clientes {origem_anterior} e {cliente.pk} apontam para o mesmo prospect {existente.codigo}."
                    )
                destinos_usados[existente.pk] = cliente.pk

            plano.append(
                {
                    "cliente": cliente,
                    "dados": dados,
                    "prospecto": existente,
                    "motivo": motivo if existente else "sem correspondência segura",
                }
            )
        return plano

    def _dados_cliente(self, cliente):
        contato = cliente.contatos.order_by("-principal", "id").first()
        email = (contato.email if contato and contato.email else cliente.email or "").strip().lower()
        observacoes = [self._marcador(cliente), "Origem: cadastro de cliente inativo preservado no AXION."]
        if email:
            try:
                validate_email(email)
            except ValidationError:
                observacoes.append(f"E-mail original com formato inválido: {email}")
                email = ""
        if cliente.telefone2:
            observacoes.append(f"Telefone secundário do cliente: {cliente.telefone2}")
        if contato and cliente.email and contato.email.casefold() != cliente.email.casefold():
            observacoes.append(f"E-mail geral do cliente: {cliente.email}")

        endereco = ", ".join(
            parte.strip()
            for parte in (cliente.endereco, cliente.numero, cliente.bairro)
            if parte and parte.strip()
        )
        cnpj = self._formatar_cnpj(cliente.cnpj)
        telefone = (
            contato.telefone if contato and contato.telefone else cliente.telefone or cliente.telefone2
        )
        dados = {
            "razao_social": cliente.razao_social,
            "nome_fantasia": cliente.nome_empresa,
            "cnpj": cnpj,
            "contato_nome": contato.nome if contato else "",
            "cargo": contato.cargo if contato else "",
            "telefone": telefone,
            "whatsapp": "",
            "email": email,
            "cidade": cliente.cidade,
            "uf": cliente.uf,
            "endereco": endereco,
            "cep": cliente.cep,
            "observacoes": "\n".join(observacoes),
        }
        dados["chave"] = {
            "razao_social": dados["razao_social"],
            "cnpj": dados["cnpj"],
            "email": dados["email"],
            "telefone": dados["telefone"],
            "contato_nome": dados["contato_nome"],
        }
        return dados

    def _criar(self, item, codigo):
        dados = {chave: valor for chave, valor in item["dados"].items() if chave != "chave"}
        Prospecto.objects.create(
            **dados,
            codigo=codigo,
            origem=ORIGEM,
            referencia_externa=str(item["cliente"].pk),
            status="disponivel",
        )

    def _vincular_existente(self, item):
        prospecto = item["prospecto"]
        dados = item["dados"]
        campos = (
            "nome_fantasia", "cnpj", "contato_nome", "cargo", "telefone",
            "email", "cidade", "uf", "endereco", "cep",
        )
        for campo in campos:
            if not getattr(prospecto, campo) and dados[campo]:
                setattr(prospecto, campo, dados[campo])
        marcador = self._marcador(item["cliente"])
        if marcador not in (prospecto.observacoes or ""):
            complemento = dados["observacoes"]
            prospecto.observacoes = (
                f"{prospecto.observacoes.rstrip()}\n{complemento}"
                if prospecto.observacoes
                else complemento
            )
        prospecto.full_clean()
        prospecto.save()

    @staticmethod
    def _marcador(cliente):
        return f"Cliente AXION inativo: {cliente.pk} ({cliente.codigo})"

    @staticmethod
    def _formatar_cnpj(valor):
        digitos = re.sub(r"\D", "", valor or "")
        if len(digitos) != 14:
            return ""
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
