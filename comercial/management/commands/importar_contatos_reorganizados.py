import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import load_workbook

from comercial.models import Prospecto


class Command(BaseCommand):
    help = "Pré-valida e importa CONTATOS_DS_REORGANIZADOS.xlsx para a Base de prospects."

    COLUMN_MAP = {
        "ID": "referencia_externa",
        "Empresa": "razao_social",
        "Contato": "contato_nome",
        "Cargo / Departamento": "cargo",
        "Telefone": "telefone",
        "Celular / WhatsApp": "whatsapp",
        "E-mail": "email",
        "Cidade": "cidade",
        "UF": "uf",
        "CNPJ": "cnpj",
        "Categoria / Ramo": "segmento",
        "Endereço": "endereco",
        "CEP": "cep",
        "Observações": "observacoes",
        "Fonte": "origem",
    }

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=Path)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Confirma a gravação. Sem esta opção, executa somente a pré-validação.",
        )
        parser.add_argument(
            "--relatorio",
            type=Path,
            default=Path("docs/importacoes/relatorio_contatos_ds_reorganizados.json"),
        )

    def handle(self, *args, **options):
        arquivo = options["arquivo"].resolve()
        if not arquivo.exists():
            raise CommandError(f"Arquivo não encontrado: {arquivo}")
        if arquivo.suffix.lower() != ".xlsx":
            raise CommandError("Formato inválido. Use um arquivo .xlsx.")

        resultado, objetos = self._analisar(arquivo)
        resultado["modo"] = "aplicacao" if options["apply"] else "pre_validacao"
        resultado["arquivo"] = str(arquivo)
        resultado["sha256"] = self._sha256(arquivo)
        resultado["executado_em"] = datetime.now().astimezone().isoformat()

        if options["apply"]:
            with transaction.atomic():
                codigos = Prospecto.reservar_codigos(len(objetos))
                for objeto, codigo in zip(objetos, codigos):
                    objeto.codigo = codigo
                Prospecto.objects.bulk_create(objetos, batch_size=500)
            resultado["importados"] = len(objetos)
        else:
            resultado["importados"] = 0

        relatorio = options["relatorio"].resolve()
        relatorio.parent.mkdir(parents=True, exist_ok=True)
        relatorio.write_text(
            json.dumps(resultado, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.stdout.write(json.dumps(resultado, ensure_ascii=False, indent=2))
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Pré-validação concluída. Nenhum registro foi gravado."))
        else:
            self.stdout.write(self.style.SUCCESS(f"{len(objetos)} prospects importados com sucesso."))

    def _analisar(self, arquivo):
        workbook = load_workbook(arquivo, read_only=True, data_only=True)
        if "CONTATOS" not in workbook.sheetnames:
            workbook.close()
            raise CommandError("A aba obrigatória CONTATOS não foi encontrada.")
        worksheet = workbook["CONTATOS"]
        linhas = worksheet.iter_rows(values_only=True)
        try:
            cabecalhos = [self._texto(valor) for valor in next(linhas)]
        except StopIteration as exc:
            workbook.close()
            raise CommandError("A planilha está vazia.") from exc

        faltantes = [coluna for coluna in self.COLUMN_MAP if coluna not in cabecalhos]
        if faltantes:
            workbook.close()
            raise CommandError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

        indices = {nome: cabecalhos.index(nome) for nome in self.COLUMN_MAP}
        chaves_db = set(
            Prospecto.objects.values_list("chave_duplicidade", flat=True).iterator(chunk_size=2000)
        )
        chaves_email_telefone_db = set(
            Prospecto.objects.exclude(chave_email_telefone__isnull=True).values_list(
                "chave_email_telefone", flat=True
            ).iterator(chunk_size=2000)
        )
        referencias_db = set(
            Prospecto.objects.exclude(referencia_externa="").values_list(
                "origem", "referencia_externa"
            ).iterator(chunk_size=2000)
        )
        chaves_arquivo = set()
        chaves_email_telefone_arquivo = set()
        referencias_arquivo = set()
        lote = uuid.uuid4()
        objetos = []
        pendencias = []
        contadores = {
            "linhas_dados": 0,
            "aptos": 0,
            "sem_empresa": 0,
            "duplicados_por_contato": 0,
            "duplicados_por_email_telefone": 0,
            "duplicados_por_referencia": 0,
            "emails_invalidos_detectados": 0,
            "emails_invalidos_preservados": 0,
            "linhas_vazias": 0,
        }

        for numero_linha, valores in enumerate(linhas, start=2):
            contadores["linhas_dados"] += 1
            registro = {
                destino: self._texto(valores[indice] if indice < len(valores) else "")
                for origem, destino in self.COLUMN_MAP.items()
                for indice in [indices[origem]]
            }
            if not any(registro.values()):
                contadores["linhas_vazias"] += 1
                continue
            if not registro["razao_social"]:
                contadores["sem_empresa"] += 1
                if len(pendencias) < 200:
                    pendencias.append({
                        "linha": numero_linha,
                        "id": registro["referencia_externa"],
                        "motivo": "Empresa não identificada",
                        "contato": registro["contato_nome"],
                        "telefone": registro["telefone"] or registro["whatsapp"],
                        "email": registro["email"],
                        "observacoes": registro["observacoes"],
                    })
                continue

            registro["email"] = registro["email"].strip().lower()
            email_invalido = False
            if registro["email"]:
                try:
                    validate_email(registro["email"])
                except ValidationError:
                    email_invalido = True
                    email_original = registro["email"]
                    registro["email"] = ""
                    registro["observacoes"] = self._juntar_observacao(
                        registro["observacoes"],
                        f"E-mail original com formato inválido: {email_original}",
                    )
                    contadores["emails_invalidos_detectados"] += 1

            registro["cnpj"] = self._formatar_cnpj(registro["cnpj"])
            registro["uf"] = registro["uf"].upper()[:2]
            registro["cep"] = registro["cep"][:12]
            registro["referencia_externa"] = registro["referencia_externa"][:50]
            registro["origem"] = registro["origem"][:120]
            registro["endereco"] = registro["endereco"][:255]

            referencia = (registro["origem"], registro["referencia_externa"])
            if registro["referencia_externa"] and (
                referencia in referencias_db or referencia in referencias_arquivo
            ):
                contadores["duplicados_por_referencia"] += 1
                continue

            chave = Prospecto.gerar_chave_duplicidade(
                razao_social=registro["razao_social"],
                cnpj=registro["cnpj"],
                email=registro["email"],
                telefone=registro["telefone"] or registro["whatsapp"],
                contato_nome=registro["contato_nome"],
            )
            if chave in chaves_db or chave in chaves_arquivo:
                contadores["duplicados_por_contato"] += 1
                continue

            chave_email_telefone = Prospecto.gerar_chave_email_telefone(
                email=registro["email"],
                telefone=registro["telefone"] or registro["whatsapp"],
            )
            if chave_email_telefone and (
                chave_email_telefone in chaves_email_telefone_db
                or chave_email_telefone in chaves_email_telefone_arquivo
            ):
                contadores["duplicados_por_email_telefone"] += 1
                continue

            chaves_arquivo.add(chave)
            if chave_email_telefone:
                chaves_email_telefone_arquivo.add(chave_email_telefone)
            if registro["referencia_externa"]:
                referencias_arquivo.add(referencia)
            objetos.append(Prospecto(
                **registro,
                lote_importacao=lote,
                linha_importacao=numero_linha,
                chave_duplicidade=chave,
                chave_email_telefone=chave_email_telefone,
                status="disponivel",
            ))
            if email_invalido:
                contadores["emails_invalidos_preservados"] += 1

        workbook.close()
        contadores["aptos"] = len(objetos)
        resultado = {
            "resumo": contadores,
            "lote_importacao": str(lote),
            "pendencias_sem_empresa_amostra": pendencias,
            "pendencias_amostra_limitada_a": 200,
            "prospects_antes": Prospecto.objects.count(),
            "prospects_depois_previsto": Prospecto.objects.count() + len(objetos),
        }
        return resultado, objetos

    @staticmethod
    def _texto(valor):
        if valor is None:
            return ""
        if isinstance(valor, float) and valor.is_integer():
            valor = int(valor)
        return str(valor).strip()

    @staticmethod
    def _formatar_cnpj(valor):
        if not valor:
            return ""
        digitos = re.sub(r"\D", "", valor)
        if len(digitos) != 14:
            return ""
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"

    @staticmethod
    def _juntar_observacao(atual, complemento):
        return f"{atual}\n{complemento}".strip() if atual else complemento

    @staticmethod
    def _sha256(arquivo):
        digest = hashlib.sha256()
        with arquivo.open("rb") as stream:
            for bloco in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(bloco)
        return digest.hexdigest()
