import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from calibracao.models import Padrao
from clientes.models import Cliente, ContatoCliente
from comercial.models import ProdutoServico, Prospecto
from qualidade.models import Documento


class Projeto(models.Model):
    TIPO_CHOICES = (
        ("equipamento", "Equipamento"),
        ("servico", "Servico"),
        ("metodo", "Metodo"),
        ("automacao", "Automacao"),
        ("retrofit", "Retrofit"),
        ("produto", "Produto"),
        ("software", "Software"),
        ("melhoria_interna", "Melhoria interna"),
        ("outro", "Outro"),
    )

    AREA_CHOICES = (
        ("calibracao", "Calibracao"),
        ("manutencao", "Manutencao"),
        ("vendas", "Vendas"),
        ("qualidade", "Qualidade"),
        ("software", "Software"),
        ("marketing", "Marketing"),
        ("interno", "Interno"),
    )

    STATUS_CHOICES = (
        ("ideia", "Ideia"),
        ("em_analise", "Em analise"),
        ("aprovado_desenvolvimento", "Aprovado para desenvolvimento"),
        ("em_desenvolvimento", "Em desenvolvimento"),
        ("aguardando_compra", "Aguardando compra"),
        ("em_teste", "Em teste"),
        ("em_validacao", "Em validacao"),
        ("aprovado", "Aprovado"),
        ("reprovado", "Reprovado"),
        ("cancelado", "Cancelado"),
        ("liberado_comercialmente", "Liberado comercialmente"),
    )

    PRIORIDADE_CHOICES = (
        ("baixa", "Baixa"),
        ("media", "Media"),
        ("alta", "Alta"),
        ("urgente", "Urgente"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default="equipamento")
    area = models.CharField(max_length=30, choices=AREA_CHOICES, default="calibracao")
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default="ideia")
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default="media")
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos_responsavel",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos_desenvolvimento",
    )
    objetivo = models.TextField(blank=True)
    justificativa = models.TextField(blank=True)
    data_inicio = models.DateField(null=True, blank=True)
    previsao_conclusao = models.DateField(null=True, blank=True)
    orcamento_previsto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    custo_real = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    resultado_esperado = models.TextField(blank=True)
    produto_servico_gerado = models.ForeignKey(
        ProdutoServico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projetos_origem",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Desenvolvimento Tecnico - Projeto"
        verbose_name_plural = "Desenvolvimento Tecnico - Projetos"
        ordering = ("-created_at", "nome")

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def gerar_codigo(self):
        ultimo = Projeto.objects.exclude(codigo="").filter(codigo__startswith="DEV-").count() + 1
        return f"DEV-{ultimo:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)


class ProjetoTarefa(models.Model):
    STATUS_CHOICES = (
        ("a_fazer", "A fazer"),
        ("em_andamento", "Em andamento"),
        ("em_teste", "Em teste"),
        ("aguardando_compra", "Aguardando compra"),
        ("concluido", "Concluido"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="tarefas")
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tarefas_projeto",
    )
    prazo = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="a_fazer")
    observacao = models.TextField(blank=True)
    anexo = models.FileField(upload_to="projetos/tarefas/", blank=True, null=True)
    ordem = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Desenvolvimento Tecnico - Etapa/Tarefa"
        verbose_name_plural = "Desenvolvimento Tecnico - Etapas/Tarefas"
        ordering = ("projeto__codigo", "ordem", "prazo")

    def __str__(self):
        return f"{self.projeto.codigo} - {self.titulo}"


class ProjetoTeste(models.Model):
    RESULTADO_CHOICES = (
        ("aprovado", "Aprovado"),
        ("aprovado_restricao", "Aprovado com restricao"),
        ("reprovado", "Reprovado"),
        ("em_analise", "Em analise"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="testes")
    tipo_teste = models.CharField(max_length=120)
    data_teste = models.DateField()
    padrao = models.ForeignKey(
        Padrao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="testes_projeto",
    )
    documento_tecnico = models.ForeignKey(
        Documento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="testes_projeto",
    )
    condicao_ambiental = models.CharField(max_length=120, blank=True)
    resultado = models.CharField(max_length=30, choices=RESULTADO_CHOICES, default="em_analise")
    evidencia = models.FileField(upload_to="projetos/testes/", blank=True, null=True)
    observacao_tecnica = models.TextField(blank=True)
    conclusao_tecnica = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Desenvolvimento Tecnico - Teste e validacao"
        verbose_name_plural = "Desenvolvimento Tecnico - Testes e validacoes"
        ordering = ("-data_teste", "tipo_teste")

    def __str__(self):
        return f"{self.projeto.codigo} - {self.tipo_teste}"


class ProjetoCusto(models.Model):
    VIABILIDADE_CHOICES = (
        ("em_analise", "Em analise"),
        ("viavel", "Viavel"),
        ("nao_viavel", "Nao viavel"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="custos")
    descricao = models.CharField(max_length=255)
    custo_componentes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    horas_tecnicas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_hora_tecnica = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    custo_outros = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    preco_estimado_venda = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payback_esperado = models.CharField(max_length=120, blank=True)
    viabilidade = models.CharField(max_length=20, choices=VIABILIDADE_CHOICES, default="em_analise")
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Desenvolvimento Tecnico - Custo e viabilidade"
        verbose_name_plural = "Desenvolvimento Tecnico - Custos e viabilidade"
        ordering = ("projeto__codigo", "-created_at")

    def __str__(self):
        return f"{self.projeto.codigo} - {self.descricao}"

    @property
    def custo_desenvolvimento(self):
        return (self.horas_tecnicas or Decimal("0")) * (self.valor_hora_tecnica or Decimal("0"))

    @property
    def custo_total(self):
        return (self.custo_componentes or Decimal("0")) + self.custo_desenvolvimento + (self.custo_outros or Decimal("0"))


class ProjetoArquivo(models.Model):
    TIPO_CHOICES = (
        ("foto", "Foto"),
        ("video", "Video"),
        ("pdf", "PDF"),
        ("manual", "Manual"),
        ("orcamento", "Orcamento"),
        ("nota_fiscal", "Nota fiscal"),
        ("desenho_tecnico", "Desenho tecnico"),
        ("planilha", "Planilha"),
        ("certificado", "Certificado"),
        ("relatorio", "Relatorio"),
        ("imagem_marketing", "Imagem para marketing"),
        ("outro", "Outro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name="arquivos")
    titulo = models.CharField(max_length=255)
    tipo_arquivo = models.CharField(max_length=30, choices=TIPO_CHOICES, default="outro")
    arquivo = models.FileField(upload_to="projetos/arquivos/")
    descricao = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True)
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="arquivos_projeto",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Desenvolvimento Tecnico - Arquivo do projeto"
        verbose_name_plural = "Desenvolvimento Tecnico - Arquivos do projeto"
        ordering = ("projeto__codigo", "-created_at")

    def __str__(self):
        return f"{self.projeto.codigo} - {self.titulo}"


class CampanhaMarketing(models.Model):
    TIPO_CHOICES = (
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
        ("whatsapp", "WhatsApp"),
        ("email", "E-mail"),
        ("trafego_pago", "Trafego pago"),
        ("outro", "Outro"),
    )

    STATUS_CHOICES = (
        ("planejada", "Planejada"),
        ("em_criacao", "Em criacao"),
        ("aguardando_aprovacao", "Aguardando aprovacao"),
        ("aprovada", "Aprovada"),
        ("publicada", "Publicada"),
        ("pausada", "Pausada"),
        ("finalizada", "Finalizada"),
        ("arquivada", "Arquivada"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=20, unique=True, blank=True)
    nome = models.CharField(max_length=255)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default="instagram")
    objetivo = models.TextField(blank=True)
    publico_alvo = models.CharField(max_length=255, blank=True)
    produto_servico = models.ForeignKey(
        ProdutoServico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas_marketing",
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas_marketing",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="planejada")
    data_inicio = models.DateField(null=True, blank=True)
    data_final = models.DateField(null=True, blank=True)
    orcamento = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas_marketing",
    )
    enviar_email = models.BooleanField("Enviar por e-mail", default=False)
    enviar_whatsapp = models.BooleanField("Enviar por WhatsApp", default=False)
    assunto_email = models.CharField("Assunto do e-mail", max_length=255, blank=True)
    conteudo_email = models.TextField("Conteúdo do e-mail", blank=True)
    whatsapp_template_nome = models.CharField(
        "Nome do modelo aprovado no WhatsApp",
        max_length=255,
        blank=True,
    )
    whatsapp_template_idioma = models.CharField(
        "Idioma do modelo do WhatsApp",
        max_length=20,
        default="pt_BR",
        blank=True,
    )
    mensagem_whatsapp_referencia = models.TextField(
        "Texto de referência do WhatsApp",
        blank=True,
        help_text="Somente para conferência. O envio usa o modelo previamente aprovado pela Meta.",
    )
    destinatarios = models.ManyToManyField(
        ContatoCliente,
        blank=True,
        related_name="campanhas_marketing",
        verbose_name="Contatos destinatários",
    )
    destinatarios_prospectos = models.ManyToManyField(
        Prospecto,
        blank=True,
        related_name="campanhas_marketing",
        verbose_name="Prospects destinatários por e-mail",
    )
    enviar_todos_contatos_autorizados = models.BooleanField(
        "Enviar a todos os contatos autorizados dos clientes ativos",
        default=False,
    )
    enviar_todos_prospectos_email_autorizados = models.BooleanField(
        "Enviar a todos os prospects autorizados por e-mail",
        default=False,
        help_text=(
            "Inclui somente prospects ativos com e-mail, base legal, evidência e autorização válidas."
        ),
    )
    agendado_para = models.DateTimeField("Agendado para", null=True, blank=True)
    aprovada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campanhas_marketing_aprovadas",
        verbose_name="Aprovada por",
    )
    aprovada_em = models.DateTimeField("Aprovada em", null=True, blank=True)
    autorizar_disparo = models.BooleanField(
        "Autorizar e preparar disparo",
        default=False,
        help_text="A campanha só entra na fila após aprovação formal e seleção de destinatários.",
    )
    disparo_solicitado_em = models.DateTimeField(
        "Disparo solicitado em",
        null=True,
        blank=True,
        editable=False,
    )
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Marketing - Campanha"
        verbose_name_plural = "Marketing - Campanhas"
        ordering = ("-created_at", "nome")

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

    def gerar_codigo(self):
        ultimo = CampanhaMarketing.objects.exclude(codigo="").filter(codigo__startswith="MKT-").count() + 1
        return f"MKT-{ultimo:04d}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self.gerar_codigo()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        erros = {}
        if self.autorizar_disparo:
            if self.status != "aprovada":
                erros["status"] = "Para autorizar o disparo, a campanha deve estar aprovada."
            if not (self.enviar_email or self.enviar_whatsapp):
                erros["autorizar_disparo"] = "Selecione pelo menos um canal de envio."
            if self.enviar_email and (not self.assunto_email.strip() or not self.conteudo_email.strip()):
                erros["conteudo_email"] = "Preencha assunto e conteúdo antes de autorizar e-mail."
            if self.enviar_whatsapp and not self.whatsapp_template_nome.strip():
                erros["whatsapp_template_nome"] = "Informe o modelo aprovado antes de autorizar WhatsApp."
        if erros:
            raise ValidationError(erros)

    def marcar_aprovacao(self, usuario):
        self.status = "aprovada"
        self.aprovada_por = usuario
        self.aprovada_em = timezone.now()


class EnvioCampanha(models.Model):
    CANAL_CHOICES = (("email", "E-mail"), ("whatsapp", "WhatsApp"))
    STATUS_CHOICES = (
        ("pendente", "Pendente"),
        ("processando", "Processando"),
        ("enviado", "Enviado"),
        ("entregue", "Entregue"),
        ("lido", "Lido"),
        ("falha", "Falha"),
        ("cancelado", "Cancelado"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campanha = models.ForeignKey(
        CampanhaMarketing,
        on_delete=models.CASCADE,
        related_name="envios",
    )
    contato = models.ForeignKey(
        ContatoCliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_marketing",
    )
    prospecto = models.ForeignKey(
        Prospecto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_marketing",
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_marketing",
    )
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
    destinatario_nome = models.CharField(max_length=255, blank=True)
    destinatario_endereco = models.CharField(max_length=255)
    assunto_snapshot = models.CharField(max_length=255, blank=True)
    conteudo_snapshot = models.TextField(blank=True)
    template_snapshot = models.CharField(max_length=255, blank=True)
    idioma_template_snapshot = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    agendado_para = models.DateTimeField()
    tentativas = models.PositiveIntegerField(default=0)
    ultima_tentativa_em = models.DateTimeField(null=True, blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)
    identificador_provedor = models.CharField(max_length=255, blank=True)
    erro = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Marketing - Envio da campanha"
        verbose_name_plural = "Marketing - Envios das campanhas"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("campanha", "contato", "canal"),
                name="projetos_envio_unico_contato_canal",
            ),
            models.UniqueConstraint(
                fields=("campanha", "prospecto", "canal"),
                name="projetos_envio_unico_prospecto_canal",
            ),
            models.UniqueConstraint(
                fields=("campanha", "canal", "destinatario_endereco"),
                condition=~models.Q(status="cancelado"),
                name="projetos_envio_unico_destino_ativo",
            ),
        ]

    def __str__(self):
        return f"{self.campanha.codigo} - {self.get_canal_display()} - {self.destinatario_endereco}"


class MidiaMarketing(models.Model):
    TIPO_CHOICES = (
        ("imagem", "Imagem"),
        ("video", "Video"),
        ("logo", "Logo"),
        ("arte", "Arte"),
        ("documento", "Documento"),
    )

    CATEGORIA_CHOICES = (
        ("institucional", "Institucional"),
        ("calibracao", "Calibracao"),
        ("manutencao", "Manutencao"),
        ("equipamentos", "Equipamentos"),
        ("antes_depois", "Antes e depois"),
        ("bastidores", "Bastidores"),
        ("clientes", "Clientes"),
        ("treinamentos", "Treinamentos"),
        ("posts_prontos", "Posts prontos"),
        ("stories", "Stories"),
        ("videos_tecnicos", "Videos tecnicos"),
        ("logos", "Logos e identidade visual"),
    )

    CANAL_CHOICES = (
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
        ("whatsapp", "WhatsApp"),
        ("email", "E-mail"),
        ("site", "Site"),
        ("outro", "Outro"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campanha = models.ForeignKey(
        CampanhaMarketing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midias",
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midias_marketing",
    )
    titulo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="imagem")
    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES, default="institucional")
    canal_sugerido = models.CharField(max_length=20, choices=CANAL_CHOICES, default="instagram")
    tags = models.CharField(max_length=255, blank=True)
    uso_autorizado = models.BooleanField(default=True)
    arquivo = models.FileField(upload_to="projetos/marketing/")
    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="midias_marketing",
    )
    observacoes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Marketing - Biblioteca de midia"
        verbose_name_plural = "Marketing - Biblioteca de midias"
        ordering = ("-created_at", "titulo")

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        if not self.arquivo:
            return
        extensao = Path(self.arquivo.name).suffix.lower()
        extensoes = {
            "imagem": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
            "logo": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
            "arte": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
            "video": {".mp4", ".mov", ".webm"},
            "documento": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"},
        }
        permitidas = extensoes.get(self.tipo, set())
        if extensao not in permitidas:
            raise ValidationError(
                {
                    "arquivo": (
                        f"O arquivo {extensao or 'sem extensão'} não corresponde ao tipo "
                        f"{self.get_tipo_display()}. Corrija o tipo ou selecione outro arquivo."
                    )
                }
            )
