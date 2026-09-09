from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.templatetags.static import static
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from comercial.models import Prospecto

from .marketing import preparar_envios_campanha, processar_envio_campanha
from .models import (
    CampanhaMarketing,
    EnvioCampanha,
    MidiaMarketing,
    Projeto,
    ProjetoArquivo,
    ProjetoCusto,
    ProjetoTarefa,
    ProjetoTeste,
)


class CampanhaMarketingForm(forms.ModelForm):
    class Meta:
        model = CampanhaMarketing
        fields = "__all__"

    def clean(self):
        dados = super().clean()
        tem_destinatarios = any(
            (
                dados.get("enviar_todos_contatos_autorizados"),
                dados.get("enviar_todos_prospectos_email_autorizados"),
                dados.get("destinatarios"),
                dados.get("destinatarios_prospectos"),
            )
        )
        if (
            dados.get("autorizar_disparo")
            and not tem_destinatarios
        ):
            self.add_error(
                "destinatarios",
                "Selecione contatos/prospects ou marque uma opção de envio para todos os autorizados.",
            )
        tem_prospectos = bool(
            dados.get("enviar_todos_prospectos_email_autorizados")
            or dados.get("destinatarios_prospectos")
        )
        if dados.get("autorizar_disparo") and tem_prospectos and not dados.get("enviar_email"):
            self.add_error(
                "enviar_email",
                "Prospects desta base podem ser incluídos somente no canal de e-mail.",
            )
        return dados


class HiddenFromMenuAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}


class ProjetoTarefaInline(admin.TabularInline):
    model = ProjetoTarefa
    extra = 0
    fields = ("ordem", "titulo", "responsavel", "prazo", "status")


class ProjetoCustoInline(admin.TabularInline):
    model = ProjetoCusto
    extra = 0
    fields = ("descricao", "custo_componentes", "horas_tecnicas", "valor_hora_tecnica", "preco_estimado_venda", "viabilidade")


class ProjetoTesteInline(admin.TabularInline):
    model = ProjetoTeste
    extra = 0
    fields = ("tipo_teste", "data_teste", "padrao", "resultado")
    autocomplete_fields = ("padrao", "documento_tecnico")


class ProjetoArquivoInline(admin.TabularInline):
    model = ProjetoArquivo
    extra = 0
    fields = ("titulo", "tipo_arquivo", "arquivo", "responsavel")


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    change_form_template = "admin/projetos/projeto/change_form.html"
    list_display = (
        "codigo",
        "nome",
        "tipo",
        "area",
        "status_badge",
        "prioridade_badge",
        "cliente",
        "responsavel",
        "previsao_conclusao",
    )
    list_filter = ("tipo", "area", "status", "prioridade", "responsavel", "cliente")
    search_fields = ("codigo", "nome", "cliente__codigo", "cliente__razao_social", "objetivo", "justificativa")
    autocomplete_fields = ("cliente", "responsavel", "produto_servico_gerado")
    readonly_fields = ("codigo",)
    ordering = ("-created_at", "nome")
    inlines = [ProjetoTarefaInline, ProjetoCustoInline, ProjetoTesteInline, ProjetoArquivoInline]

    fieldsets = (
        ("Identificacao", {"fields": ("codigo", "nome", "tipo", "area", "status", "prioridade")}),
        ("Responsabilidade", {"fields": ("responsavel", "cliente", "produto_servico_gerado")}),
        ("Escopo", {"fields": ("objetivo", "justificativa", "resultado_esperado")}),
        ("Cronograma e custo", {"fields": (("data_inicio", "previsao_conclusao"), ("orcamento_previsto", "custo_real"))}),
    )

    def status_badge(self, obj):
        cores = {
            "ideia": "#64748b",
            "em_analise": "#1d4ed8",
            "aprovado_desenvolvimento": "#0f766e",
            "em_desenvolvimento": "#2563eb",
            "aguardando_compra": "#b45309",
            "em_teste": "#7c3aed",
            "em_validacao": "#0f766e",
            "aprovado": "#15803d",
            "reprovado": "#b91c1c",
            "cancelado": "#991b1b",
            "liberado_comercialmente": "#166534",
        }
        return format_html(
            "<span style='background:{};color:#fff;padding:4px 8px;border-radius:999px;font-weight:700;'>{}</span>",
            cores.get(obj.status, "#475569"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def prioridade_badge(self, obj):
        cores = {
            "baixa": ("#e2e8f0", "#334155"),
            "media": ("#dbeafe", "#1d4ed8"),
            "alta": ("#fef3c7", "#92400e"),
            "urgente": ("#fee2e2", "#991b1b"),
        }
        fundo, texto = cores.get(obj.prioridade, ("#e2e8f0", "#334155"))
        return format_html(
            "<span style='background:{};color:{};padding:4px 8px;border-radius:999px;font-weight:700;'>{}</span>",
            fundo,
            texto,
            obj.get_prioridade_display(),
        )

    prioridade_badge.short_description = "Prioridade"


@admin.register(ProjetoTarefa)
class ProjetoTarefaAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "ordem", "titulo", "responsavel", "prazo", "status")
    list_filter = ("status", "responsavel", "projeto")
    search_fields = ("projeto__codigo", "projeto__nome", "titulo", "descricao")
    autocomplete_fields = ("projeto", "responsavel")
    ordering = ("projeto__codigo", "ordem", "prazo")


@admin.register(ProjetoTeste)
class ProjetoTesteAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "tipo_teste", "data_teste", "padrao", "resultado")
    list_filter = ("resultado", "data_teste")
    search_fields = ("projeto__codigo", "projeto__nome", "tipo_teste", "observacao_tecnica")
    autocomplete_fields = ("projeto", "padrao", "documento_tecnico")
    ordering = ("-data_teste",)


@admin.register(ProjetoCusto)
class ProjetoCustoAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "descricao", "custo_componentes", "custo_desenvolvimento", "custo_total", "preco_estimado_venda", "viabilidade")
    list_filter = ("viabilidade", "projeto")
    search_fields = ("projeto__codigo", "projeto__nome", "descricao")
    autocomplete_fields = ("projeto",)
    ordering = ("projeto__codigo", "-created_at")


@admin.register(ProjetoArquivo)
class ProjetoArquivoAdmin(HiddenFromMenuAdmin):
    list_display = ("projeto", "titulo", "tipo_arquivo", "responsavel", "created_at")
    list_filter = ("tipo_arquivo", "responsavel")
    search_fields = ("projeto__codigo", "projeto__nome", "titulo", "tags")
    autocomplete_fields = ("projeto", "responsavel")
    ordering = ("-created_at",)


class MidiaMarketingInline(admin.TabularInline):
    model = MidiaMarketing
    extra = 0
    fields = ("titulo", "tipo", "categoria", "canal_sugerido", "uso_autorizado", "arquivo")


@admin.register(CampanhaMarketing)
class CampanhaMarketingAdmin(admin.ModelAdmin):
    form = CampanhaMarketingForm
    change_form_template = "admin/projetos/campanhamarketing/change_form.html"
    list_display = ("codigo", "nome", "tipo", "status", "projeto", "produto_servico", "responsavel", "data_inicio", "data_final")
    list_filter = ("tipo", "status", "responsavel")
    search_fields = ("codigo", "nome", "objetivo", "publico_alvo", "projeto__codigo", "projeto__nome")
    autocomplete_fields = (
        "produto_servico",
        "projeto",
        "responsavel",
        "destinatarios",
        "destinatarios_prospectos",
        "aprovada_por",
    )
    readonly_fields = (
        "codigo",
        "aprovada_em",
        "disparo_solicitado_em",
        "resumo_envios",
        "resumo_prospectos_email",
        "visualizar_email",
    )
    inlines = [MidiaMarketingInline]
    ordering = ("-created_at", "nome")

    fieldsets = (
        ("Identificacao", {"fields": ("codigo", "nome", "tipo", "status")}),
        ("Vinculos", {"fields": ("projeto", "produto_servico", "responsavel")}),
        ("Planejamento", {"fields": ("objetivo", "publico_alvo", ("data_inicio", "data_final"), "orcamento", "observacoes")}),
        (
            "Destinatários e canais",
            {
                "classes": ("campanha-disparo",),
                "fields": (
                    ("enviar_email", "enviar_whatsapp"),
                    "enviar_todos_contatos_autorizados",
                    "destinatarios",
                    "enviar_todos_prospectos_email_autorizados",
                    "destinatarios_prospectos",
                    "resumo_prospectos_email",
                    "agendado_para",
                )
            },
        ),
        (
            "Conteúdo do e-mail",
            {
                "classes": ("campanha-disparo",),
                "fields": ("assunto_email", "conteudo_email", "visualizar_email"),
            },
        ),
        (
            "Modelo oficial do WhatsApp",
            {
                "classes": ("campanha-disparo",),
                "fields": (
                    ("whatsapp_template_nome", "whatsapp_template_idioma"),
                    "mensagem_whatsapp_referencia",
                )
            },
        ),
        (
            "Aprovação e disparo",
            {
                "classes": ("campanha-disparo",),
                "fields": (
                    ("aprovada_por", "aprovada_em"),
                    "autorizar_disparo",
                    "disparo_solicitado_em",
                    "resumo_envios",
                ),
                "description": "Salvar não envia diretamente: a autorização prepara uma fila rastreável e idempotente.",
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if obj.status == "aprovada" and not obj.aprovada_por_id:
            obj.aprovada_por = request.user
        if obj.status == "aprovada" and not obj.aprovada_em:
            obj.aprovada_em = timezone.now()
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if not form.instance.autorizar_disparo:
            return
        resultado = preparar_envios_campanha(form.instance.pk)
        messages.info(
            request,
            (
                "Fila da campanha preparada: "
                f"{resultado['criados']} novo(s), {resultado['existentes']} já existente(s) e "
                f"{resultado['ignorados']} ignorado(s) por falta de autorização ou contato válido."
            ),
        )

    def resumo_envios(self, obj):
        if not obj or not obj.pk:
            return "A fila ainda não foi criada."
        totais = {item["status"]: item["total"] for item in obj.envios.values("status").annotate(total=models.Count("pk"))}
        if not totais:
            return "A fila ainda não foi criada."
        return ", ".join(f"{status}: {total}" for status, total in sorted(totais.items()))

    resumo_envios.short_description = "Resumo da fila"

    def resumo_prospectos_email(self, obj):
        com_email = Prospecto.objects.exclude(email="").count()
        autorizados = (
            Prospecto.objects.filter(
                status__in=("disponivel", "em_prospeccao"),
                marketing_email_autorizado=True,
                marketing_autorizado_em__isnull=False,
                marketing_revogado_em__isnull=True,
            )
            .exclude(email="")
            .exclude(marketing_base_legal="")
            .exclude(marketing_origem="")
            .count()
        )
        selecionados = obj.destinatarios_prospectos.count() if obj and obj.pk else 0
        return (
            f"{autorizados} prospect(s) elegível(is) entre {com_email} com e-mail; "
            f"{selecionados} selecionado(s) individualmente."
        )

    resumo_prospectos_email.short_description = "Resumo dos prospects por e-mail"

    def get_urls(self):
        urls = super().get_urls()
        personalizados = [
            path(
                "<path:object_id>/duplicar/",
                self.admin_site.admin_view(self.duplicar_campanha_view),
                name="projetos_campanhamarketing_duplicar",
            ),
            path(
                "<path:object_id>/visualizar-email/",
                self.admin_site.admin_view(self.visualizar_email_view),
                name="projetos_campanhamarketing_visualizar_email",
            )
        ]
        return personalizados + urls

    def duplicar_campanha_view(self, request, object_id):
        if request.method != "POST":
            return HttpResponseNotAllowed(("POST",))
        original = self.get_object(request, object_id)
        if original is None:
            from django.http import Http404

            raise Http404("Campanha não encontrada.")
        if not self.has_view_or_change_permission(request, original) or not self.has_add_permission(request):
            raise PermissionDenied

        with transaction.atomic():
            duplicada = CampanhaMarketing.objects.create(
                nome=f"{original.nome} - cópia",
                tipo=original.tipo,
                objetivo=original.objetivo,
                publico_alvo=original.publico_alvo,
                produto_servico=original.produto_servico,
                projeto=original.projeto,
                status="em_criacao",
                data_inicio=original.data_inicio,
                data_final=original.data_final,
                orcamento=original.orcamento,
                responsavel=original.responsavel,
                enviar_email=original.enviar_email,
                enviar_whatsapp=original.enviar_whatsapp,
                assunto_email=original.assunto_email,
                conteudo_email=original.conteudo_email,
                whatsapp_template_nome=original.whatsapp_template_nome,
                whatsapp_template_idioma=original.whatsapp_template_idioma,
                mensagem_whatsapp_referencia=original.mensagem_whatsapp_referencia,
                enviar_todos_contatos_autorizados=original.enviar_todos_contatos_autorizados,
                enviar_todos_prospectos_email_autorizados=(
                    original.enviar_todos_prospectos_email_autorizados
                ),
                observacoes=original.observacoes,
            )
            duplicada.destinatarios.set(original.destinatarios.all())
            duplicada.destinatarios_prospectos.set(original.destinatarios_prospectos.all())
            for midia in original.midias.all():
                MidiaMarketing.objects.create(
                    campanha=duplicada,
                    projeto=midia.projeto,
                    titulo=midia.titulo,
                    tipo=midia.tipo,
                    categoria=midia.categoria,
                    canal_sugerido=midia.canal_sugerido,
                    tags=midia.tags,
                    uso_autorizado=midia.uso_autorizado,
                    arquivo=midia.arquivo.name,
                    responsavel=midia.responsavel,
                    observacoes=midia.observacoes,
                )

        messages.success(
            request,
            (
                f"Campanha {original.codigo} duplicada como {duplicada.codigo}. "
                "Revise o conteúdo e faça uma nova aprovação antes do disparo."
            ),
        )
        return redirect("admin:projetos_campanhamarketing_change", object_id=duplicada.pk)

    def visualizar_email(self, obj):
        if not obj or not obj.pk:
            return "Salve a campanha para habilitar a pré-visualização."
        url = reverse("admin:projetos_campanhamarketing_visualizar_email", args=(obj.pk,))
        return format_html(
            '<a class="button" href="{}" target="_blank" rel="noopener">Abrir pré-visualização do e-mail</a>',
            url,
        )

    visualizar_email.short_description = "Pré-visualização"

    def visualizar_email_view(self, request, object_id):
        campanha = self.get_object(request, object_id)
        if campanha is None:
            from django.http import Http404

            raise Http404("Campanha não encontrada.")
        envio_preview = type(
            "EnvioPreview",
            (),
            {
                "assunto_snapshot": campanha.assunto_email,
                "conteudo_snapshot": campanha.conteudo_email,
                "destinatario_nome": "Cliente",
            },
        )()
        midias_inline = []
        for midia in campanha.midias.filter(
            uso_autorizado=True,
            canal_sugerido="email",
            tipo__in=("imagem", "logo", "arte"),
        ):
            midias_inline.append({"titulo": midia.titulo, "src": midia.arquivo.url})
        return TemplateResponse(
            request,
            "projetos/email/campanha.html",
            {
                "campanha": campanha,
                "envio": envio_preview,
                "midias_inline": midias_inline,
                "logo_src": static("img/logo_ds.png"),
            },
        )


@admin.register(EnvioCampanha)
class EnvioCampanhaAdmin(admin.ModelAdmin):
    list_display = (
        "campanha",
        "canal",
        "destinatario_nome",
        "destinatario_endereco",
        "prospecto",
        "status",
        "tentativas",
        "agendado_para",
        "enviado_em",
    )
    list_filter = ("canal", "status", "campanha")
    search_fields = (
        "campanha__codigo",
        "campanha__nome",
        "destinatario_nome",
        "destinatario_endereco",
        "prospecto__codigo",
        "prospecto__razao_social",
        "identificador_provedor",
    )
    readonly_fields = tuple(field.name for field in EnvioCampanha._meta.fields)
    actions = ("processar_selecionados",)
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def processar_selecionados(self, request, queryset):
        totais = {}
        for envio_id in queryset.values_list("pk", flat=True):
            resultado = processar_envio_campanha(envio_id)
            totais[resultado] = totais.get(resultado, 0) + 1
        resumo = ", ".join(f"{status}: {total}" for status, total in sorted(totais.items()))
        self.message_user(request, resumo or "Nenhum envio processado.", level=messages.INFO)

    processar_selecionados.short_description = "Processar envios selecionados agora"


@admin.register(MidiaMarketing)
class MidiaMarketingAdmin(HiddenFromMenuAdmin):
    list_display = ("titulo", "tipo", "categoria", "canal_sugerido", "campanha", "projeto", "uso_autorizado", "created_at")
    list_filter = ("tipo", "categoria", "canal_sugerido", "uso_autorizado")
    search_fields = ("titulo", "tags", "campanha__codigo", "campanha__nome", "projeto__codigo", "projeto__nome")
    autocomplete_fields = ("campanha", "projeto", "responsavel")
    ordering = ("-created_at", "titulo")
