import uuid
from django.db import models
from django.contrib.auth.models import User

import uuid
from django.db import models
from django.contrib.auth.models import User


# =========================
# CLIENTE
# =========================
class Cliente(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    codigo = models.CharField(max_length=20, unique=True, blank=True)

    razao_social = models.CharField(max_length=255)
    nome_empresa = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=18, unique=True)
    ie = models.CharField("Inscrição Estadual", max_length=30, blank=True)

    endereco = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=10, blank=True)

    telefone = models.CharField(max_length=20, blank=True)
    telefone2 = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    referencia_cliente = models.CharField(max_length=100, blank=True)

    ativo = models.BooleanField(default=True)

    # 🔥 ANEXO DIRETO
    nome_anexo = models.CharField(max_length=200, blank=True)
    anexo = models.FileField(upload_to="clientes/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =========================
    # GERAR CÓDIGO
    # =========================
    def gerar_codigo(self):
        ultimo = Cliente.objects.exclude(codigo="").order_by("-created_at").first()

        if ultimo and ultimo.codigo:
            try:
                numero = int(ultimo.codigo.split("-")[1]) + 1
            except:
                numero = 1
        else:
            numero = 1

        return f"CL-{numero:04d}"

    # =========================
    # SAVE
    # =========================
    def save(self, *args, **kwargs):
        if not self.codigo:
            while True:
                codigo = self.gerar_codigo()
                if not Cliente.objects.filter(codigo=codigo).exists():
                    self.codigo = codigo
                    break

        super().save(*args, **kwargs)

    class Meta:
        ordering = ("razao_social",)

    def __str__(self):
        return f"{self.codigo} - {self.razao_social}"
    
# =========================
# CONTATO
# =========================

class ContatoCliente(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="contatos"
    )

    nome = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    telefone = models.CharField(max_length=20, blank=True)
    principal = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Contato do Cliente"
        verbose_name_plural = "Contatos do Cliente"
        ordering = ("-principal", "nome")

    def __str__(self):
        return f"{self.nome} — {self.cliente.codigo}"


# =========================
# ANEXOS DO CLIENTE
# =========================

class ClienteAnexo(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="anexos"
    )

    nome = models.CharField(max_length=200)
    arquivo = models.FileField(upload_to="clientes/anexos/")
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-data_upload",)

    def __str__(self):
        return f"{self.nome} - {self.cliente.codigo}"


# =========================
# PERFIL DO USUÁRIO
# =========================

class PerfilUsuario(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    empresa = models.CharField(max_length=200)
    numero_sequencial = models.CharField(max_length=50, unique=True, blank=True)

    def gerar_codigo(self):
        ultimo = PerfilUsuario.objects.exclude(numero_sequencial="").order_by("-id").first()

        if ultimo and ultimo.numero_sequencial:
            try:
                numero = int(ultimo.numero_sequencial.split("-")[1]) + 1
            except:
                numero = PerfilUsuario.objects.count() + 1
        else:
            numero = 1

        return f"DS-{numero:03d}"

    def save(self, *args, **kwargs):
        if not self.numero_sequencial or not self.numero_sequencial.startswith("DS-"):
            self.numero_sequencial = self.gerar_codigo()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.empresa}"
