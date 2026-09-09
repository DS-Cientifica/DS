import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
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
    cnpj_provisorio = models.BooleanField(
        "CNPJ pendente de confirmação",
        default=False,
        help_text="Indica cliente convertido de prospecção sem CNPJ informado.",
    )
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
    def clean(self):
        super().clean()
        if (self.cnpj or "").upper().startswith(("PROS-", "PROSPECT-")) and not self.cnpj_provisorio:
            raise ValidationError({
                "cnpj_provisorio": (
                    "Substitua o identificador provisório por um CNPJ válido antes de retirar esta marcação."
                )
            })

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

    BASE_LEGAL_MARKETING_CHOICES = (
        ("consentimento", "Consentimento"),
        ("legitimo_interesse", "Legítimo interesse documentado"),
    )
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

    marketing_email_autorizado = models.BooleanField(
        "Autoriza marketing por e-mail",
        default=False,
    )
    marketing_whatsapp_autorizado = models.BooleanField(
        "Autoriza marketing por WhatsApp",
        default=False,
    )
    marketing_base_legal = models.CharField(
        "Base legal do tratamento",
        max_length=30,
        choices=BASE_LEGAL_MARKETING_CHOICES,
        blank=True,
    )
    marketing_autorizado_em = models.DateTimeField(
        "Autorizado/avaliado em",
        null=True,
        blank=True,
    )
    marketing_origem = models.CharField(
        "Origem/evidência da autorização",
        max_length=255,
        blank=True,
        help_text="Ex.: formulário assinado, contrato, evento ou referência do teste de legítimo interesse.",
    )
    marketing_revogado_em = models.DateTimeField(
        "Revogado em",
        null=True,
        blank=True,
    )
    marketing_observacoes = models.TextField(
        "Observações de privacidade",
        blank=True,
    )

    class Meta:
        verbose_name = "Contato do Cliente"
        verbose_name_plural = "Contatos do Cliente"
        ordering = ("-principal", "nome")

    def __str__(self):
        return f"{self.nome} — {self.cliente.codigo}"

    def clean(self):
        super().clean()
        erros = {}
        possui_autorizacao = self.marketing_email_autorizado or self.marketing_whatsapp_autorizado
        if possui_autorizacao and not self.marketing_base_legal:
            erros["marketing_base_legal"] = "Informe a base legal antes de autorizar campanhas."
        if possui_autorizacao and not self.marketing_origem.strip():
            erros["marketing_origem"] = "Registre a origem ou evidência da autorização."
        if self.marketing_whatsapp_autorizado and not self.telefone.strip():
            erros["telefone"] = "Informe o telefone antes de autorizar campanhas por WhatsApp."
        if self.marketing_revogado_em and possui_autorizacao:
            erros["marketing_revogado_em"] = "Desmarque os canais autorizados ao registrar a revogação."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        if (
            (self.marketing_email_autorizado or self.marketing_whatsapp_autorizado)
            and not self.marketing_autorizado_em
        ):
            self.marketing_autorizado_em = timezone.now()
        super().save(*args, **kwargs)

    def marketing_autorizado(self, canal):
        if not self.cliente.ativo or self.marketing_revogado_em:
            return False
        if not self.marketing_base_legal or not self.marketing_origem or not self.marketing_autorizado_em:
            return False
        if canal == "email":
            return self.marketing_email_autorizado and bool(self.email.strip())
        if canal == "whatsapp":
            return self.marketing_whatsapp_autorizado and bool(self.telefone.strip())
        return False


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

    empresa = models.CharField(max_length=200, blank=True, default="DS Científica")
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
