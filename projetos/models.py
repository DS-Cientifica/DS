import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models

from calibracao.models import Padrao
from clientes.models import Cliente
from comercial.models import ProdutoServico
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
