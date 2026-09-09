from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage

from documentos.models import DocumentoArquivo


def validar_chave(chave):
    if not chave or "\\" in chave:
        raise ValueError("Chave de armazenamento inválida.")
    caminho = PurePosixPath(chave)
    if caminho.is_absolute() or ".." in caminho.parts:
        raise ValueError("Chave de armazenamento inválida.")
    return str(caminho)


class LocalDocumentStorage:
    backend = DocumentoArquivo.Backend.LOCAL

    def __init__(self):
        self.storage = FileSystemStorage(location=settings.DOCUMENT_LOCAL_ROOT, base_url=None)

    def save(self, chave, arquivo, *, sha256=None, mime_type=None):
        chave = validar_chave(chave)
        if self.storage.exists(chave):
            raise FileExistsError(f"A chave documental já existe: {chave}")
        nome_salvo = self.storage.save(chave, arquivo)
        if nome_salvo != chave:
            self.storage.delete(nome_salvo)
            raise FileExistsError(f"Não foi possível preservar a chave documental: {chave}")
        return chave

    def open(self, chave, mode="rb"):
        return self.storage.open(validar_chave(chave), mode)

    def exists(self, chave):
        return self.storage.exists(validar_chave(chave))

    def size(self, chave):
        return self.storage.size(validar_chave(chave))

    def delete(self, chave):
        self.storage.delete(validar_chave(chave))


class LegacyMediaStorage(LocalDocumentStorage):
    backend = DocumentoArquivo.Backend.MEDIA

    def __init__(self):
        self.storage = FileSystemStorage(location=settings.MEDIA_ROOT, base_url=None)


class R2DocumentStorage:
    backend = DocumentoArquivo.Backend.R2

    def __init__(self):
        campos = {
            "DOCUMENT_R2_BUCKET": settings.DOCUMENT_R2_BUCKET,
            "DOCUMENT_R2_ENDPOINT_URL": settings.DOCUMENT_R2_ENDPOINT_URL,
            "DOCUMENT_R2_ACCESS_KEY_ID": settings.DOCUMENT_R2_ACCESS_KEY_ID,
            "DOCUMENT_R2_SECRET_ACCESS_KEY": settings.DOCUMENT_R2_SECRET_ACCESS_KEY,
        }
        ausentes = [nome for nome, valor in campos.items() if not valor]
        if ausentes:
            raise ImproperlyConfigured("Configuração R2 incompleta: " + ", ".join(ausentes))
        import boto3

        self.bucket = settings.DOCUMENT_R2_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.DOCUMENT_R2_ENDPOINT_URL,
            aws_access_key_id=settings.DOCUMENT_R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.DOCUMENT_R2_SECRET_ACCESS_KEY,
            region_name=settings.DOCUMENT_R2_REGION,
        )

    def save(self, chave, arquivo, *, sha256=None, mime_type=None):
        chave = validar_chave(chave)
        extras = {"ContentType": mime_type or "application/octet-stream"}
        if sha256:
            extras["Metadata"] = {"sha256": sha256}
        self.client.upload_fileobj(arquivo, self.bucket, chave, ExtraArgs=extras)
        return chave

    def open(self, chave, mode="rb"):
        if mode != "rb":
            raise ValueError("O R2 permite somente leitura binária.")
        return self.client.get_object(Bucket=self.bucket, Key=validar_chave(chave))["Body"]

    def head(self, chave):
        return self.client.head_object(Bucket=self.bucket, Key=validar_chave(chave))

    def exists(self, chave):
        from botocore.exceptions import ClientError
        try:
            self.head(chave)
            return True
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code", "")) in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def size(self, chave):
        return self.head(chave)["ContentLength"]

    def delete(self, chave):
        self.client.delete_object(Bucket=self.bucket, Key=validar_chave(chave))

    def presigned_url(self, chave, *, expires_in=None):
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": validar_chave(chave)},
            ExpiresIn=expires_in or settings.DOCUMENT_R2_PRESIGNED_URL_TTL,
        )


def storage_para_backend(backend):
    storages = {
        DocumentoArquivo.Backend.LOCAL: LocalDocumentStorage,
        DocumentoArquivo.Backend.MEDIA: LegacyMediaStorage,
        DocumentoArquivo.Backend.R2: R2DocumentStorage,
    }
    try:
        return storages[backend]()
    except KeyError as exc:
        raise ValueError(f"Backend documental desconhecido: {backend}") from exc


def storage_primario_configurado():
    modo = settings.DOCUMENT_STORAGE_MODE
    if modo not in {DocumentoArquivo.Backend.LOCAL, DocumentoArquivo.Backend.R2}:
        raise ImproperlyConfigured("DOCUMENT_STORAGE_MODE deve ser 'local' ou 'r2'.")
    if modo == DocumentoArquivo.Backend.R2 and not settings.DOCUMENT_R2_ENABLED:
        raise ImproperlyConfigured("Habilite DOCUMENT_R2_ENABLED para usar o R2 como primário.")
    return storage_para_backend(modo)
