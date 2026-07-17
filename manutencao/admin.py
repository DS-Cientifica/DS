import calendar
from datetime import date

from django import forms
from django.contrib import admin
from django.db.models import Q
from django.shortcuts import render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from calibracao.models import ResponsavelCertificado
from clientes.models import Cliente

from .models import Manutencao, ManutencaoEvidencia


class ManutencaoEvidenciaInline(admin.TabularInline):
    model = ManutencaoEvidencia
    extra = 1


class ManutencaoAdminForm(forms.ModelForm):
    class Meta:
        model = Manutencao
        fields = "__all__"
        widgets = {
            "intervencoes": forms.Textarea(attrs={"rows": 4}),
            "materiais": forms.Textarea(attrs={"rows": 4}),
            "verificacoes": forms.Textarea(attrs={"rows": 4}),
            "rastreabilidade": forms.Textarea(attrs={"rows": 4}),
            "resultados": forms.Textarea(attrs={"rows": 4}),
        }


@admin.register(Manutencao)
class ManutencaoAdmin(admin.ModelAdmin):
    form = ManutencaoAdminForm
    change_list_template = "admin/manutencao/manutencao/change_list.html"
    list_display = (
        "numero_relatorio",
        "cliente",
        "instrumento",
        "tipo_manutencao",
        "data_servico",
        "status",
        "pdf_manutencao",
    )
    list_filter = ("tipo_manutencao", "status", "data_servico")
    search_fields = (
        "numero_relatorio",
        "ordem_servico",
        "cliente__razao_social",
        "instrumento__codigo",
        "instrumento__descricao",
        "responsavel_tecnico",
        "responsavel_cliente_ref__nome",
    )
    autocomplete_fields = ("cliente", "instrumento", "responsavel_cliente_ref", "responsavel_tecnico_ref")
    readonly_fields = ("numero_relatorio", "pdf_manutencao")
    inlines = (ManutencaoEvidenciaInline,)
    fieldsets = (
        ("Identificação", {
            "fields": (
                "numero_relatorio",
                "cliente",
                "responsavel_cliente_ref",
                "instrumento",
                "responsavel_tecnico_ref",
                "ordem_servico",
                "tipo_manutencao",
                "pdf_manutencao",
            )
        }),
        ("Datas e status", {
            "fields": (
                "data_recepcao",
                "data_servico",
                "data_saida",
                "proxima_manutencao",
                "status",
            )
        }),
        ("Execução", {
            "fields": (
                "condicao_recebida",
                "condicao_saida",
                "diagnostico",
                "parecer_tecnico",
                "criterio_aceitacao",
                "responsavel_tecnico",
            )
        }),
        ("Controle", {
            "fields": (
                "intervencoes",
                "materiais",
                "verificacoes",
                "rastreabilidade",
                "resultados",
                "aprovado_por",
                "aprovado_cargo",
                "aprovado_em",
                "observacoes",
            )
        }),
    )

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("data_servico", timezone.localdate())
        initial.setdefault("status", Manutencao.Status.CONFORME)
        if not initial.get("responsavel_tecnico_ref"):
            responsavel = ResponsavelCertificado.objects.filter(ativo=True).order_by("nome").first()
            if responsavel:
                initial.setdefault("responsavel_tecnico_ref", responsavel.pk)
        return initial

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="manutencao_manutencao_calendario",
            ),
            path(
                "<int:pk>/pdf/",
                self.admin_site.admin_view(self.pdf_view),
                name="manutencao_manutencao_pdf",
            ),
        ]
        return custom_urls + urls

    def calendario_view(self, request):
        hoje = date.today()
        try:
            ano = int(request.GET.get("ano", hoje.year))
        except (TypeError, ValueError):
            ano = hoje.year
        try:
            mes = int(request.GET.get("mes", hoje.month))
        except (TypeError, ValueError):
            mes = hoje.month

        if mes < 1:
            mes = 12
            ano -= 1
        elif mes > 12:
            mes = 1
            ano += 1

        primeiro_dia = date(ano, mes, 1)
        ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])

        manutencoes = (
            Manutencao.objects.filter(
                Q(data_servico__range=(primeiro_dia, ultimo_dia))
                | Q(proxima_manutencao__range=(primeiro_dia, ultimo_dia))
            )
            .select_related("cliente", "instrumento", "responsavel_tecnico_ref")
            .order_by("data_servico", "cliente__razao_social", "instrumento__codigo")
        )

        status = request.GET.get("status", "").strip()
        tipo = request.GET.get("tipo", "").strip()
        cliente = request.GET.get("cliente", "").strip()

        if status:
            manutencoes = manutencoes.filter(status=status)
        if tipo:
            manutencoes = manutencoes.filter(tipo_manutencao=tipo)
        if cliente:
            manutencoes = manutencoes.filter(cliente_id=cliente)

        manutencoes = list(manutencoes)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for item in manutencoes:
                    if item.data_servico == dia:
                        eventos.append(self._evento_calendario(item, "servico"))
                    if item.proxima_manutencao == dia:
                        eventos.append(self._evento_calendario(item, "proxima"))
                dias.append(
                    {
                        "data": dia,
                        "fora_mes": dia.month != mes,
                        "hoje": dia == hoje,
                        "eventos": eventos,
                    }
                )
            semanas.append(dias)

        anterior_ano, anterior_mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
        proximo_ano, proximo_mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Calendario de manutencao",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "status_choices": self.model.Status.choices,
            "tipo_choices": self.model.TipoManutencao.choices,
            "clientes": Cliente.objects.filter(manutencoes__isnull=False).distinct().order_by("razao_social"),
            "filtros": {
                "status": status,
                "tipo": tipo,
                "cliente": cliente,
            },
            "link_anterior": f"?mes={anterior_mes}&ano={anterior_ano}&status={status}&tipo={tipo}&cliente={cliente}",
            "link_proximo": f"?mes={proximo_mes}&ano={proximo_ano}&status={status}&tipo={tipo}&cliente={cliente}",
            "novo_url": reverse("admin:manutencao_manutencao_add"),
            "lista_url": reverse("admin:manutencao_manutencao_changelist"),
            "legenda_status": [
                ("servico", "Servico executado"),
                ("proxima", "Proxima manutencao"),
                ("conforme", "Conforme"),
                ("nao_conforme", "Nao conforme"),
                ("bloqueado", "Bloqueado"),
            ],
        }
        return render(request, "admin/manutencao/manutencao/calendar.html", context)

    def _evento_calendario(self, item, tipo_evento):
        status_key = "proxima" if tipo_evento == "proxima" else item.status
        titulo = "Proxima manutencao" if tipo_evento == "proxima" else "Servico executado"
        instrumento = item.instrumento.codigo if item.instrumento_id else ""
        descricao = item.instrumento.descricao if item.instrumento_id else ""
        return {
            "titulo": titulo,
            "cliente": item.cliente.razao_social if item.cliente_id else "Sem cliente",
            "instrumento": " - ".join(part for part in (instrumento, descricao) if part),
            "relatorio": item.numero_relatorio,
            "ordem_servico": item.ordem_servico,
            "tipo": item.get_tipo_manutencao_display(),
            "status": item.get_status_display(),
            "status_key": status_key,
            "responsavel": item.responsavel_tecnico_ref.nome if item.responsavel_tecnico_ref_id else item.responsavel_tecnico,
            "url": reverse("admin:manutencao_manutencao_change", args=[item.pk]),
        }

    def pdf_view(self, request, pk):
        from .views import pdf_manutencao

        return pdf_manutencao(request, pk)

    def pdf_manutencao(self, obj):
        if not obj.pk:
            return "-"
        return format_html(
            "<a class='button' href='{}' target='_blank'>Gerar PDF</a>",
            reverse("admin:manutencao_manutencao_pdf", args=[obj.pk]),
        )

    pdf_manutencao.short_description = "Impressão"
