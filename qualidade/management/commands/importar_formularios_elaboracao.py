import hashlib
from collections import defaultdict
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from qualidade.models import Documento


ARQUIVOS = (
    ("CAIBRAÇÃO RASTREADA TEMPERATURA.ods", "Calibração rastreada de temperatura", "formulario", "Metrologia - Temperatura"),
    ("CALIBRAÇÃO DE MEIO TÉRMICO (RBC) – 240 PONTOS.ods", "Calibração de meio térmico (RBC) - 240 pontos", "formulario", "Metrologia - Temperatura"),
    ("CALIBRAÇÃO DE PRESSÃO.xlsx", "Calibração de pressão", "formulario", "Metrologia - Pressão"),
    ("CERTIFCADO DE BALANÇA REVISADO.xlsx", "Certificado de balança - formulário revisado", "formulario", "Metrologia - Massa"),
    ("certificado medidor de ph rastreado.ods", "Certificado de medidor de pH rastreado", "formulario", "Metrologia - Físico-química"),
    ("DADOS DOS EQUIPAMETNO OPTICO.ods", "Dados de equipamentos ópticos", "outros", "Metrologia - Óptica"),
    ("DSC_Modelo_Calibracao_Vazao_Independente.xlsx", "Modelo de calibração de vazão independente", "formulario", "Metrologia - Vazão"),
    ("ENSAIO DE DESEMPENHO.pdf", "Ensaio de desempenho do processo de esterilização", "procedimento", "Qualidade - Esterilização"),
    ("FILTRO OPTICO.ods", "Filtro óptico - dados de apoio", "outros", "Metrologia - Óptica"),
    ("FM - 7.2.1-206RV00 Informacoes Gerais de Termohigrometros.ods", "Informações gerais de termohigrômetros", "formulario", "Metrologia - Temperatura e Umidade"),
    ("FM - 7.2.1-XXXRV00  Ensaio de Desempenho de Processo de Esterilização .ods", "Ensaio de desempenho de processo de esterilização", "formulario", "Qualidade - Esterilização"),
    ("FM - 7.2.1-XXXRV00  Ensaio de Desempenho de Processo de Esterilização_.ods", "Ensaio de desempenho de processo de esterilização - variante", "formulario", "Qualidade - Esterilização"),
    ("FM - 7.2.1-xxxRV00 Calibração de Autoclave.ods", "Calibração de autoclave", "formulario", "Metrologia - Temperatura"),
    ("FM - 7.2.1-XXXRV00 Calibração de Cronometro e Temporizador.ods", "Calibração de cronômetro e temporizador", "formulario", "Metrologia - Tempo e Frequência"),
    ("FM - 7.2.1-xxxRV00 Calibração de Espectrofotômetro UV-Vis com fenda ate 10 nm (rastreada).ods", "Calibração rastreada de espectrofotômetro UV-Vis com fenda até 10 nm", "formulario", "Metrologia - Óptica"),
    ("FM - 7.2.1-xxxRV00 Calibração de Espectrofotômetro UV-Vis com fenda ate 10 nm.ods", "Calibração de espectrofotômetro UV-Vis com fenda até 10 nm", "formulario", "Metrologia - Óptica"),
    ("FM - 7.2.1-xxxRV00 Calibração de Fotocolorimetro.ods", "Calibração de fotocolorímetro", "formulario", "Metrologia - Óptica"),
    ("FM - 7.2.1-xxxRV00 Calibração de Medidor de Condutividade.ods", "Calibração de medidor de condutividade", "formulario", "Metrologia - Físico-química"),
    ("FM - 7.2.1-xxxRV00 Calibração de Medidor de pH - Multiponto.ods", "Calibração multiponto de medidor de pH", "formulario", "Metrologia - Físico-química"),
    ("FM - 7.2.1-xxxRV00 Calibração de Medidor de pH_.ods", "Calibração de medidor de pH", "formulario", "Metrologia - Físico-química"),
    ("FM - 7.2.1-xxxRV00 Calibração de Medidor de Pressão Digital - Analogico.ods", "Calibração de medidor de pressão - indicação analógica", "formulario", "Metrologia - Pressão"),
    ("FM - 7.2.1-xxxRV00 Calibração de Medidor de Pressão Digital - Digital.ods", "Calibração de medidor de pressão - indicação digital", "formulario", "Metrologia - Pressão"),
    ("FM - 7.2.1-XXXRV00 Calibração de Meio Térmico - 240 pontos.ods", "Calibração de meio térmico - 240 pontos", "formulario", "Metrologia - Temperatura"),
    ("FM - 7.2.1-XXXRV00 Calibração de Meio Térmico 240 pontos.ods", "Calibração de meio térmico - 240 pontos (variante de nome)", "formulario", "Metrologia - Temperatura"),
    ("FM - 7.2.1-xxxRV00 Calibração de Polarímetro_.ods", "Calibração de polarímetro", "formulario", "Metrologia - Óptica"),
    ("FM - 7.2.1-XXXRV00 Calibração de Reator de Digestão.ods", "Calibração de reator de digestão", "formulario", "Metrologia - Temperatura"),
    ("FM - 7.2.1-XXXRV00 Calibração Externa de Medidor de Temperatura.ods", "Calibração externa de medidor de temperatura", "formulario", "Metrologia - Temperatura"),
    ("FM - 7.2.1-xxxRV00 Calibração Externa de Medidor de Temperatura_.ods", "Calibração externa de medidor de temperatura (variante de nome)", "formulario", "Metrologia - Temperatura"),
    ("FM - 7.2.1-XXXRV00 Qualificacao de Autoclave.ods", "Qualificação de autoclave", "formulario", "Qualidade - Esterilização"),
    ("FM - 7.2.1-xxxRV00 Verificacao de Purificador de Agua.ods", "Verificação de purificador de água", "formulario", "Metrologia - Físico-química"),
    ("FM-7.2.1-xxxRV00 Calibração de Balança_.ods", "Calibração de balança", "formulario", "Metrologia - Massa"),
    ("INCERTEZA.pdf", "Incerteza de medição no ensaio de desempenho do processo de esterilização", "procedimento", "Qualidade - Esterilização"),
    ("PROTOCOLO.pdf", "Protocolo de ensaio de desempenho do processo de esterilização", "formulario", "Qualidade - Esterilização"),
    ("TURBIDIMETRO.xls", "Calibração de turbidímetro", "formulario", "Metrologia - Físico-química"),
)

REFERENCIAS_EXTERNAS = {
    "ENSAIO DE DESEMPENHO.pdf": "Documento-fonte externo Evagon PO-7.2.1-240, revisão 01, aprovado em 15/01/2021.",
    "INCERTEZA.pdf": "Documento-fonte externo Evagon PO-7.2.1-241, revisão 02, aprovado em 21/01/2021.",
    "PROTOCOLO.pdf": "Documento-fonte externo Evagon FM-7.2.1-241, revisão 00, aprovado em 28/01/2021.",
}


def sha256_arquivo(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validar_formato(path):
    assinatura = path.read_bytes()[:8]
    extensao = path.suffix.lower()
    if extensao == ".pdf" and not assinatura.startswith(b"%PDF-"):
        raise CommandError(f"PDF inválido: {path.name}")
    if extensao == ".xls" and assinatura != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise CommandError(f"XLS inválido: {path.name}")
    if extensao in {".ods", ".xlsx"}:
        try:
            with ZipFile(path) as archive:
                names = set(archive.namelist())
                if "META-INF/manifest.xml" not in names and "xl/workbook.xml" not in names:
                    raise CommandError(f"Planilha sem estrutura reconhecida: {path.name}")
                bad_entry = archive.testzip()
                if bad_entry:
                    raise CommandError(f"Planilha com entrada ZIP corrompida ({bad_entry}): {path.name}")
        except BadZipFile as exc:
            raise CommandError(f"Planilha ZIP inválida: {path.name}") from exc


class Command(BaseCommand):
    help = "Cadastra formulários e procedimentos como documentos em elaboração."

    def add_arguments(self, parser):
        parser.add_argument("--diretorio", type=Path, required=True)
        parser.add_argument("--apply", action="store_true", dest="aplicar")

    def handle(self, *args, **options):
        diretorio = options["diretorio"].expanduser().resolve()
        aplicar = options["aplicar"]
        if not diretorio.is_dir():
            raise CommandError(f"Diretório não encontrado: {diretorio}")

        esperados = {item[0] for item in ARQUIVOS}
        encontrados = {item.name for item in diretorio.iterdir() if item.is_file()}
        ausentes = sorted(esperados - encontrados)
        if ausentes:
            raise CommandError("Arquivos ausentes:\n- " + "\n- ".join(ausentes))

        hashes = {}
        for nome, *_ in ARQUIVOS:
            path = diretorio / nome
            validar_formato(path)
            hashes[nome] = sha256_arquivo(path)

        grupos = defaultdict(list)
        for nome, digest in hashes.items():
            grupos[digest].append(nome)
        duplicados = [nomes for nomes in grupos.values() if len(nomes) > 1]

        existentes = {}
        for nome, *_ in ARQUIVOS:
            marcador = f"Arquivo-fonte original: {nome}"
            encontrados_db = list(Documento.objects.filter(observacoes__contains=marcador))
            if len(encontrados_db) > 1:
                raise CommandError(f"Mais de um cadastro existente para {nome}")
            if encontrados_db:
                documento = encontrados_db[0]
                if not documento.arquivo:
                    raise CommandError(f"Cadastro existente sem arquivo: {nome}")
                with documento.arquivo.open("rb") as stream:
                    digest_db = hashlib.sha256(stream.read()).hexdigest()
                if digest_db != hashes[nome]:
                    raise CommandError(f"Conflito: o cadastro existente de {nome} possui conteúdo diferente")
                existentes[nome] = documento

        self.stdout.write(f"Arquivos validados: {len(ARQUIVOS)}")
        self.stdout.write(f"Conteúdos SHA-256 distintos: {len(grupos)}")
        self.stdout.write(f"Cadastros já existentes e íntegros: {len(existentes)}")
        for nomes in duplicados:
            self.stdout.write(self.style.WARNING("Duplicidade binária: " + " | ".join(nomes)))

        pendentes = [item for item in ARQUIVOS if item[0] not in existentes]
        for nome, titulo, tipo, area in pendentes:
            self.stdout.write(f"CRIAR | {tipo} | {titulo} | {nome}")
        if not aplicar:
            self.stdout.write(self.style.WARNING("Prévia concluída; nenhuma alteração foi gravada. Use --apply para confirmar."))
            return

        caminhos_salvos = []
        try:
            with transaction.atomic():
                for indice, (nome, titulo, tipo, area) in enumerate(pendentes, start=1):
                    iguais = [outro for outro in grupos[hashes[nome]] if outro != nome]
                    notas = [
                        f"Arquivo-fonte original: {nome}",
                        f"SHA-256: {hashes[nome]}",
                        "Cadastro inicial em elaboração; código, revisão, emissão, aprovação e conteúdo técnico pendentes de análise crítica.",
                    ]
                    if nome in REFERENCIAS_EXTERNAS:
                        notas.append(REFERENCIAS_EXTERNAS[nome])
                        notas.append("A aprovação do documento-fonte não constitui aprovação pela DS Científica.")
                    if iguais:
                        notas.append("Conteúdo binário idêntico a: " + " | ".join(iguais))
                        notas.append("Confirmar se é duplicidade, variante válida ou renomeação incorreta antes da aprovação.")
                    documento = Documento(
                        codigo="",
                        titulo=titulo,
                        tipo=tipo,
                        revisao="RASCUNHO",
                        data_emissao=None,
                        data_ultima_revisao=None,
                        aprovado_por="",
                        status="em_elaboracao",
                        responsavel="",
                        area=area,
                        observacoes="\n".join(notas),
                    )
                    nome_armazenamento = (
                        f"elaboracao-{hashes[nome][:16]}-{indice:02d}{Path(nome).suffix.lower()}"
                    )
                    with (diretorio / nome).open("rb") as stream:
                        documento.arquivo.save(nome_armazenamento, File(stream), save=False)
                    caminhos_salvos.append((documento.arquivo.storage, documento.arquivo.name))
                    documento.save()
        except Exception:
            for storage, caminho in caminhos_salvos:
                storage.delete(caminho)
            raise

        self.stdout.write(self.style.SUCCESS(f"Importação concluída: {len(pendentes)} criado(s), {len(existentes)} preservado(s)."))
