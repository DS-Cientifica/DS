import hashlib
import mimetypes
import re
import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from documentos.models import DocumentoArquivo, DocumentoVinculo, SincronizacaoDocumento
from .storages import R2DocumentStorage, storage_para_backend, storage_primario_configurado


def calcular_sha256(stream):
    digest = hashlib.sha256()
    for bloco in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(bloco)
    return digest.hexdigest()


def registrar_documento(arquivo, *, tipo_documento, objeto=None, usuario=None, imutavel=False, documento_anterior=None):
    if not tipo_documento:
        raise ValidationError("Informe o tipo do documento.")
    nome = PurePosixPath(str(getattr(arquivo, "name", "documento.bin")).replace("\\", "/")).name
    nome = re.sub(r"[^A-Za-z0-9._-]+", "-", nome).strip(".-")[:180] or "documento.bin"
    tipo = re.sub(r"[^a-z0-9_-]+", "-", tipo_documento.lower()).strip("-") or "outros"
    extensao = PurePosixPath(nome).suffix.lower()[:15]
    hoje = timezone.localdate()
    chave = f"{tipo}/{hoje:%Y/%m}/{uuid.uuid4().hex}{extensao}"
    mime = getattr(arquivo, "content_type", None) or mimetypes.guess_type(nome)[0] or "application/octet-stream"
    storage = storage_primario_configurado()
    storage.save(chave, arquivo, mime_type=mime)
    try:
        with storage.open(chave, "rb") as salvo:
            sha256 = calcular_sha256(salvo)
        content_type = ContentType.objects.get_for_model(objeto, for_concrete_model=False) if objeto else None
        object_id = str(objeto.pk) if objeto else None
        with transaction.atomic():
            documento = DocumentoArquivo.objects.create(
                tipo_documento=tipo_documento, nome_original=nome,
                chave_armazenamento=chave, backend_primario=storage.backend,
                sha256=sha256, tamanho=storage.size(chave), mime_type=mime,
                imutavel=imutavel, content_type=content_type, object_id=object_id,
                documento_anterior=documento_anterior,
                criado_por=usuario if getattr(usuario, "is_authenticated", False) else None,
            )
            if content_type:
                DocumentoVinculo.objects.create(documento=documento, content_type=content_type, object_id=object_id)
            if settings.DOCUMENT_R2_ENABLED and storage.backend != DocumentoArquivo.Backend.R2:
                SincronizacaoDocumento.objects.create(documento=documento)
        return documento
    except Exception:
        storage.delete(chave)
        raise


def verificar_integridade(documento, *, atualizar=True):
    storage = storage_para_backend(documento.backend_primario)
    if not storage.exists(documento.chave_armazenamento):
        return False, "arquivo_nao_localizado"
    if storage.size(documento.chave_armazenamento) != documento.tamanho:
        return False, "tamanho_divergente"
    with storage.open(documento.chave_armazenamento, "rb") as arquivo:
        integro = calcular_sha256(arquivo) == documento.sha256
    if atualizar:
        documento.verificado_em = timezone.now()
        documento.save(update_fields=("verificado_em", "atualizado_em"))
    return integro, "ok" if integro else "hash_divergente"


def sincronizar_com_r2(documento):
    if not settings.DOCUMENT_R2_ENABLED:
        raise ValidationError("A sincronização com o R2 não está habilitada.")
    if documento.backend_primario == DocumentoArquivo.Backend.R2:
        raise ValidationError("O documento já utiliza o R2 como backend primário.")
    sincronizacao, _ = SincronizacaoDocumento.objects.get_or_create(documento=documento)
    sincronizacao.status = SincronizacaoDocumento.Status.PROCESSANDO
    sincronizacao.tentativas += 1
    sincronizacao.ultimo_erro = ""
    sincronizacao.save()
    origem, destino = storage_para_backend(documento.backend_primario), R2DocumentStorage()
    try:
        with origem.open(documento.chave_armazenamento, "rb") as arquivo:
            destino.save(documento.chave_armazenamento, arquivo, sha256=documento.sha256, mime_type=documento.mime_type)
        remoto = destino.head(documento.chave_armazenamento)
        if remoto.get("ContentLength") != documento.tamanho or remoto.get("Metadata", {}).get("sha256") != documento.sha256:
            raise ValueError("O arquivo enviado ao R2 não passou na verificação de integridade.")
        sincronizacao.status = SincronizacaoDocumento.Status.SINCRONIZADO
        sincronizacao.sincronizado_em = timezone.now()
        sincronizacao.etag_remoto = str(remoto.get("ETag", "")).strip('"')
    except Exception as exc:
        sincronizacao.status = SincronizacaoDocumento.Status.FALHA
        sincronizacao.ultimo_erro = str(exc)[:4000]
        sincronizacao.save()
        raise
    sincronizacao.save()
    return sincronizacao
