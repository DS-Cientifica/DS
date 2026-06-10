import calendar
from datetime import date

from django.contrib import admin
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from clientes.models import Cliente

from .models import PlanejamentoServico


@admin.register(PlanejamentoServico)
class PlanejamentoServicoAdmin(admin.ModelAdmin):
    change_form_template = "admin/planejamento/planejamentoservico/change_form.html"
    change_list_template = "admin/planejamento/planejamentoservico/change_list.html"
    list_display = (
        "codigo",
        "tipo_agendamento",
        "cliente",
        "periodo",
        "status_badge",
        "situacao_padroes_badge",
        "confirmado_cliente",
        "necessita_veiculo",
        "veiculo_descricao",
        "responsavel",
        "botao_impressao",
    )
    list_filter = (
        "tipo_agendamento",
        "status",
        "confirmado_cliente",
        "necessita_veiculo",
        "dia_inteiro",
        "data_inicio",
        "responsavel",
    )
    search_fields = (
        "codigo",
        "titulo",
        "cliente__codigo",
        "cliente__razao_social",
        "local_servico",
        "veiculo_descricao",
        "ordem_servico__numero",
        "proposta__codigo",
    )
    autocomplete_fields = (
        "cliente",
        "contato",
        "proposta",
        "ordem_servico",
        "responsavel",
        "tecnicos",
    )
    filter_horizontal = ("instrumentos", "padroes")
    readonly_fields = ("codigo",)
    date_hierarchy = "data_inicio"
    ordering = ("data_inicio", "hora_inicio", "cliente__razao_social")

    fieldsets = (
        (
            "Agenda",
            {
                "fields": (
                    "codigo",
                    "titulo",
                    "tipo_agendamento",
                    "status",
                    "confirmado_cliente",
                )
            },
        ),
        (
            "Cliente e vinculos",
            {
                "description": "O responsavel e o cargo do cliente sao puxados automaticamente do contato selecionado.",
                "fields": (
                    "cliente",
                    "contato",
                    "telefone_contato",
                    "email_contato",
                    "proposta",
                    "ordem_servico",
                )
            },
        ),
        (
            "Data e local",
            {
                "fields": (
                    ("data_inicio", "data_fim"),
                    ("hora_inicio", "hora_fim"),
                    "dia_inteiro",
                    "local_servico",
                )
            },
        ),
        (
            "Logistica e equipe",
            {
                "description": "Selecione um ou mais tecnicos para executar o servico.",
                "fields": (
                    "necessita_veiculo",
                    "veiculo_descricao",
                    "responsavel",
                    "tecnicos",
                    "recursos_necessarios",
                )
            },
        ),
        (
            "Equipamentos e padroes",
            {
                "fields": (
                    "instrumentos",
                    "padroes",
                    "retirada_equipamentos",
                    "observacoes",
                )
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "calendario/",
                self.admin_site.admin_view(self.calendario_view),
                name="planejamento_planejamentoservico_calendario",
            ),
            path(
                "<uuid:pk>/imprimir/",
                self.admin_site.admin_view(self.impressao_view),
                name="planejamento_planejamentoservico_imprimir",
            ),
        ]
        return custom_urls + urls

    def periodo(self, obj):
        return obj.intervalo_resumido()

    periodo.short_description = "Periodo"

    def save_model(self, request, obj, form, change):
        if not obj.responsavel_id:
            obj.responsavel = request.user
        super().save_model(request, obj, form, change)

    def status_badge(self, obj):
        cores = {
            "rascunho": "#64748b",
            "agendado": "#1d4ed8",
            "confirmado": "#15803d",
            "em_execucao": "#c2410c",
            "concluido": "#166534",
            "cancelado": "#b91c1c",
        }
        return format_html(
            "<span style='background:{};color:#fff;padding:4px 8px;border-radius:999px;font-weight:700;'>{}</span>",
            cores.get(obj.status, "#475569"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def situacao_padroes_badge(self, obj):
        codigo = obj.situacao_padroes_codigo()
        cores = {
            "ok": ("#dcfce7", "#166534"),
            "vencido": ("#fee2e2", "#991b1b"),
            "faltando": ("#fef3c7", "#92400e"),
            "nao_aplicavel": ("#e2e8f0", "#334155"),
        }
        fundo, texto = cores.get(codigo, ("#e2e8f0", "#334155"))
        return format_html(
            "<span style='background:{};color:{};padding:4px 8px;border-radius:999px;font-weight:700;'>{}</span>",
            fundo,
            texto,
            obj.situacao_padroes_label(),
        )

    situacao_padroes_badge.short_description = "Padroes"

    def botao_impressao(self, obj):
        return format_html(
            "<a class='button' href='{}' target='_blank'>Imprimir</a>",
            reverse("admin:planejamento_planejamentoservico_imprimir", args=[obj.pk]),
        )

    botao_impressao.short_description = "Impressao"

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

        planejamentos = (
            PlanejamentoServico.objects.filter(
                data_inicio__lte=ultimo_dia,
                data_fim__gte=primeiro_dia,
            )
            .select_related("cliente", "responsavel")
            .prefetch_related("padroes", "tecnicos")
            .order_by("data_inicio", "hora_inicio", "cliente__razao_social")
        )

        status = request.GET.get("status", "").strip()
        tipo = request.GET.get("tipo", "").strip()
        responsavel = request.GET.get("responsavel", "").strip()
        cliente = request.GET.get("cliente", "").strip()

        if status:
            planejamentos = planejamentos.filter(status=status)
        if tipo:
            planejamentos = planejamentos.filter(tipo_agendamento=tipo)
        if responsavel:
            planejamentos = planejamentos.filter(responsavel_id=responsavel)
        if cliente:
            planejamentos = planejamentos.filter(cliente_id=cliente)

        planejamentos = list(planejamentos)

        cal = calendar.Calendar(firstweekday=6)
        semanas = []
        for semana in cal.monthdatescalendar(ano, mes):
            dias = []
            for dia in semana:
                eventos = []
                for item in planejamentos:
                    data_fim = item.data_fim or item.data_inicio
                    if item.data_inicio <= dia <= data_fim:
                        horarios = "Dia inteiro" if item.dia_inteiro else self._horario_curto(item)
                        eventos.append(
                            {
                                "cliente": item.cliente.razao_social,
                                "tipo": item.get_tipo_agendamento_display(),
                                "status": item.get_status_display(),
                                "status_key": item.status,
                                "horarios": horarios,
                                "situacao_padroes": item.situacao_padroes_label(),
                                "situacao_padroes_key": item.situacao_padroes_codigo(),
                                "veiculo": item.veiculo_descricao if item.necessita_veiculo else "",
                                "padroes": ", ".join(item.padroes.values_list("codigo", flat=True)[:3]),
                                "exige_padroes": item.exige_padroes(),
                                "url": reverse("admin:planejamento_planejamentoservico_change", args=[item.pk]),
                            }
                        )
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
            "title": "Calendario de planejamento",
            "subtitulo": primeiro_dia.strftime("%B de %Y").capitalize(),
            "semanas": semanas,
            "mes": mes,
            "ano": ano,
            "status_choices": self.model.STATUS_CHOICES,
            "tipo_choices": self.model.TIPO_CHOICES,
            "clientes": Cliente.objects.order_by("razao_social"),
            "usuarios": User.objects.filter(is_active=True).order_by("first_name", "username"),
            "filtros": {
                "status": status,
                "tipo": tipo,
                "responsavel": responsavel,
                "cliente": cliente,
            },
            "link_anterior": f"?mes={anterior_mes}&ano={anterior_ano}&status={status}&tipo={tipo}&responsavel={responsavel}&cliente={cliente}",
            "link_proximo": f"?mes={proximo_mes}&ano={proximo_ano}&status={status}&tipo={tipo}&responsavel={responsavel}&cliente={cliente}",
            "novo_url": reverse("admin:planejamento_planejamentoservico_add"),
            "lista_url": reverse("admin:planejamento_planejamentoservico_changelist"),
            "legenda_status": [
                ("confirmado", "Confirmado"),
                ("em_execucao", "Em execucao"),
                ("concluido", "Concluido"),
                ("agendado", "Agendado"),
                ("rascunho", "Rascunho"),
                ("cancelado", "Cancelado"),
            ],
        }
        return render(request, "admin/planejamento/planejamentoservico/calendar.html", context)

    def _horario_curto(self, item):
        inicio = item.hora_inicio.strftime("%H:%M") if item.hora_inicio else "--:--"
        fim = item.hora_fim.strftime("%H:%M") if item.hora_fim else "--:--"
        return f"{inicio} - {fim}"

    def impressao_view(self, request, pk):
        planejamento = get_object_or_404(
            PlanejamentoServico.objects.select_related(
                "cliente",
                "contato",
                "proposta",
                "ordem_servico",
                "responsavel",
            ).prefetch_related("instrumentos", "padroes", "tecnicos"),
            pk=pk,
        )
        context = {
            **self.admin_site.each_context(request),
            "title": f"Planejamento {planejamento.codigo}",
            "planejamento": planejamento,
        }
        return render(request, "admin/planejamento/planejamentoservico/print.html", context)
