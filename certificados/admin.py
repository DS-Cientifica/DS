from io import StringIO
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    CertificadoCalibracao,
    EtiquetaCalibracaoQR,
    PadraoUtilizado,
    RevisaoCertificado,
)
from .qr import gerar_qr_svg


def _url_publica(request, caminho):
    base = getattr(settings, "PUBLIC_CERTIFICATE_BASE_URL", "").strip().rstrip("/")
    if not base:
        hosts = getattr(settings, "PUBLIC_CERTIFICATE_HOSTS", ())
        if hosts:
            base = f"https://{hosts[0]}"
    if not base:
        return request.build_absolute_uri(caminho)
    return urljoin(f"{base}/", caminho.lstrip("/"))


class PadraoUtilizadoInline(admin.TabularInline):
    model = PadraoUtilizado
    extra = 0
    can_delete = False
    readonly_fields = (
        "padrao", "documento", "data_utilizacao", "codigo", "descricao",
        "numero_certificado", "laboratorio_emitente", "data_calibracao",
        "validade", "situacao_na_data", "registrado_em",
    )

    def has_add_permission(self, request, obj=None):
        return False


class RevisaoCertificadoInline(admin.TabularInline):
    model = RevisaoCertificado
    extra = 0
    can_delete = False
    readonly_fields = ("acao", "justificativa", "usuario", "criado_em")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CertificadoCalibracao)
class CertificadoCalibracaoAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "cliente_exibicao", "instrumento_exibicao", "arquivo_exibicao",
        "revisao", "status", "publicado", "permitir_download_publico",
        "data_calibracao", "acoes_publicas",
    )
    list_filter = ("status", "publicado", "permitir_download_publico")
    search_fields = (
        "numero", "codigo_curto", "uuid_publico",
        "cliente__codigo", "cliente__razao_social", "cliente__nome_empresa",
        "instrumento__codigo", "instrumento__descricao", "instrumento__numero_serie",
        "documento__nome_original",
    )
    list_select_related = ("cliente", "instrumento", "documento")
    readonly_fields = (
        "uuid_publico", "codigo_curto", "links_publicos", "criado_em", "atualizado_em",
    )
    inlines = (PadraoUtilizadoInline, RevisaoCertificadoInline)

    @admin.display(description="Cliente", ordering="cliente__razao_social")
    def cliente_exibicao(self, obj):
        return f"{obj.cliente.codigo} - {obj.cliente.razao_social}"

    @admin.display(description="Equipamento", ordering="instrumento__codigo")
    def instrumento_exibicao(self, obj):
        return f"{obj.instrumento.codigo} - {obj.instrumento.descricao}"

    @admin.display(description="Arquivo")
    def arquivo_exibicao(self, obj):
        return obj.documento.nome_original if obj.documento_id else "—"

    def has_add_permission(self, request, obj=None):
        # A publicação deve passar por publicar_calibracao_existente(), que valida
        # conclusão, PDF final, padrões e registra a trilha de auditoria.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "<uuid:pk>/etiqueta/",
                self.admin_site.admin_view(self.etiqueta_view),
                name="certificados_certificadocalibracao_etiqueta",
            ),
        ] + super().get_urls()

    def _url_consulta(self, request, obj):
        caminho = reverse("certificados:consulta", args=[obj.uuid_publico])
        return _url_publica(request, caminho)

    def etiqueta_view(self, request, pk):
        certificado = get_object_or_404(CertificadoCalibracao, pk=pk)
        if not self.has_view_permission(request, certificado):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        url_consulta = self._url_consulta(request, certificado)
        return render(
            request,
            "admin/certificados/certificadocalibracao/etiqueta.html",
            {
                **self.admin_site.each_context(request),
                "certificado": certificado,
                "url_consulta": url_consulta,
                "qr_svg": gerar_qr_svg(url_consulta, tamanho=220),
                "title": f"QR Code - {certificado.numero}",
            },
        )

    @admin.display(description="Consulta e QR Code")
    def acoes_publicas(self, obj):
        if not obj.publicado:
            return "Ainda não publicado"
        consulta = reverse("certificados:consulta", args=[obj.uuid_publico])
        etiqueta = reverse("admin:certificados_certificadocalibracao_etiqueta", args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank">Consultar</a> | '
            '<a href="{}" target="_blank">Imprimir QR</a>',
            consulta,
            etiqueta,
        )

    @admin.display(description="Consulta pública")
    def links_publicos(self, obj):
        if not obj or not obj.publicado:
            return "Disponível após a publicação."
        return self.acoes_publicas(obj)

    def get_readonly_fields(self, request, obj=None):
        campos = list(super().get_readonly_fields(request, obj))
        campos.extend(
            field.name
            for field in self.model._meta.fields
            if field.name not in campos
        )
        return tuple(campos)


@admin.register(PadraoUtilizado)
class PadraoUtilizadoAdmin(admin.ModelAdmin):
    list_display = ("certificado", "codigo", "numero_certificado", "validade", "situacao_na_data")
    list_filter = ("situacao_na_data",)
    search_fields = ("certificado__numero", "codigo", "descricao", "numero_certificado")
    readonly_fields = [field.name for field in PadraoUtilizado._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(RevisaoCertificado)
class RevisaoCertificadoAdmin(admin.ModelAdmin):
    list_display = ("certificado", "acao", "usuario", "criado_em")
    search_fields = ("certificado__numero", "acao", "justificativa")
    readonly_fields = [field.name for field in RevisaoCertificado._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        return {}


@admin.register(EtiquetaCalibracaoQR)
class EtiquetaCalibracaoQRAdmin(admin.ModelAdmin):
    change_list_template = "admin/certificados/etiquetacalibracaoqr/change_list.html"
    list_display = (
        "codigo", "lote", "sequencia", "status", "certificado",
        "calibracao_exibicao", "criada_por", "ativada_por", "vinculada_por",
        "vinculada_em", "criado_em",
    )
    list_filter = ("status", "lote")
    search_fields = ("codigo", "lote", "certificado__numero")
    list_select_related = ("certificado", "vinculada_por")
    actions = ("imprimir_etiquetas",)
    readonly_fields = (
        "codigo", "lote", "sequencia", "token_publico", "status",
        "calibracao_content_type", "calibracao_object_id", "calibracao_exibicao",
        "certificado", "criada_por", "ativada_por", "ativada_em", "reservada_em",
        "vinculada_por", "vinculada_em", "motivo_bloqueio",
        "criado_em", "atualizado_em",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "lotes/",
                self.admin_site.admin_view(self.lotes_view),
                name="certificados_etiquetacalibracaoqr_lotes",
            ),
        ]
        return custom_urls + urls

    def lotes_view(self, request):
        if not request.user.is_superuser:
            raise PermissionDenied

        if request.method == "POST":
            acao = request.POST.get("acao", "").strip()
            lote = request.POST.get("lote", "").strip()
            confirmado = request.POST.get("confirmar") == "sim"
            if not confirmado:
                messages.error(request, "Marque a confirmação antes de executar a operação.")
            elif acao == "gerar":
                try:
                    quantidade = int(request.POST.get("quantidade", ""))
                except (TypeError, ValueError):
                    messages.error(request, "Informe uma quantidade inteira válida.")
                else:
                    if EtiquetaCalibracaoQR.objects.filter(lote=lote).exists():
                        messages.error(request, "Este lote já existe; nenhuma etiqueta foi criada.")
                    else:
                        saida = StringIO()
                        try:
                            with transaction.atomic():
                                call_command(
                                    "gerar_lote_etiquetas_qr",
                                    lote=lote,
                                    quantidade=quantidade,
                                    apply=True,
                                    stdout=saida,
                                )
                                EtiquetaCalibracaoQR.objects.filter(lote=lote).update(
                                    criada_por=request.user
                                )
                        except CommandError as exc:
                            messages.error(request, str(exc))
                        else:
                            messages.success(
                                request,
                                f"Lote {lote} gerado com {quantidade} etiqueta(s), aguardando impressão.",
                            )
                            return redirect(
                                reverse("admin:certificados_etiquetacalibracaoqr_changelist")
                                + f"?lote__exact={lote}"
                            )
            elif acao == "ativar":
                saida = StringIO()
                try:
                    with transaction.atomic():
                        call_command(
                            "ativar_lote_etiquetas_qr",
                            lote=lote,
                            apply=True,
                            stdout=saida,
                        )
                        EtiquetaCalibracaoQR.objects.filter(lote=lote).update(
                            ativada_por=request.user,
                            ativada_em=timezone.now(),
                        )
                except CommandError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, f"Lote {lote} ativado para uso nas calibrações DS.")
                    return redirect(
                        reverse("admin:certificados_etiquetacalibracaoqr_changelist")
                        + f"?lote__exact={lote}"
                    )
            else:
                messages.error(request, "Operação de lote inválida.")

        lotes = list(
            EtiquetaCalibracaoQR.objects.values("lote", "status")
            .annotate(total=Count("id"))
            .order_by("lote", "status")
        )
        context = {
            **self.admin_site.each_context(request),
            "title": "Controle de lotes de etiquetas QR",
            "opts": self.model._meta,
            "lotes": lotes,
            "changelist_url": reverse("admin:certificados_etiquetacalibracaoqr_changelist"),
        }
        return TemplateResponse(
            request,
            "admin/certificados/etiquetacalibracaoqr/lotes.html",
            context,
        )

    @admin.display(description="Calibração reservada")
    def calibracao_exibicao(self, obj):
        return str(obj.calibracao) if obj.calibracao else "—"

    @admin.action(description="Imprimir QR Codes das etiquetas selecionadas")
    def imprimir_etiquetas(self, request, queryset):
        etiquetas = []
        for etiqueta in queryset.order_by("lote", "sequencia"):
            caminho = reverse(
                "certificados:consulta_etiqueta",
                args=[etiqueta.token_publico],
            )
            url = _url_publica(request, caminho)
            etiquetas.append(
                {
                    "objeto": etiqueta,
                    "url": url,
                    "qr_svg": gerar_qr_svg(url, tamanho=150),
                }
            )
        return render(
            request,
            "admin/certificados/etiquetacalibracaoqr/imprimir.html",
            {
                **self.admin_site.each_context(request),
                "title": "Impressão de etiquetas de calibração",
                "etiquetas": etiquetas,
            },
        )
