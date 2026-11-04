from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import Cliente, ContatoCliente, PerfilUsuario, ClienteAnexo


# =========================
# ANEXOS DO CLIENTE
# =========================

class ClienteAnexoInline(admin.TabularInline):
    model = ClienteAnexo
    extra = 1
    fields = ("nome", "arquivo", "ver_arquivo", "data_upload")
    readonly_fields = ("ver_arquivo", "data_upload")
    verbose_name = "anexo adicional"
    verbose_name_plural = "Anexos adicionais"

    def ver_arquivo(self, obj):
        if obj.arquivo:
            return format_html(
                "<a href='{}' target='_blank'>Abrir</a>",
                obj.arquivo.url
            )
        return "-"

    ver_arquivo.short_description = "Arquivo"


# =========================
# CLIENTES
# =========================
@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):

    readonly_fields = ("codigo",)
    inlines = (ClienteAnexoInline,)

    list_display = (
        "codigo",
        "razao_social",
        "cnpj",
        "cnpj_provisorio",
        "cidade",
        "uf",
        "ativo",
    )

    search_fields = (
        "codigo",
        "razao_social",
        "cnpj",
    )

    list_filter = (
        "ativo",
        "cnpj_provisorio",
        "uf",
    )

    fieldsets = (
        ("Dados Gerais", {
            "fields": (
                "codigo",
                "razao_social",
                "nome_empresa",
                "cnpj",
                "cnpj_provisorio",
                "ie",
            )
        }),

        ("Endereço", {
            "fields": (
                "endereco",
                "numero",
                "bairro",
                "cidade",
                "uf",
                "cep",
            )
        }),

        ("Contato", {
            "fields": (
                "telefone",
                "telefone2",
                "email",
            )
        }),

        ("Anexo principal (legado)", {
            "fields": (
                "nome_anexo",
                "anexo",
            ),
            "description": (
                "Arquivo mantido para compatibilidade com cadastros antigos. "
                "Para incluir mais documentos, use a seção Anexos adicionais abaixo."
            ),
        }),

        ("Controle", {
            "fields": (
                "ativo",
            )
        }),
    )

    class Media:
        js = ("js/cliente_autofill.js",)

        
# =========================
# CONTATOS
# =========================

@admin.register(ContatoCliente)
class ContatoClienteAdmin(admin.ModelAdmin):

    list_display = (
        "nome",
        "cliente",
        "email",
        "telefone",
        "principal",
        "marketing_email_autorizado",
        "marketing_whatsapp_autorizado",
    )

    search_fields = (
        "nome",
        "email",
        "cliente__razao_social",
    )

    list_filter = (
        "principal",
        "marketing_email_autorizado",
        "marketing_whatsapp_autorizado",
        "marketing_base_legal",
    )

    fieldsets = (
        ("Contato", {"fields": ("cliente", "nome", "cargo", "email", "telefone", "principal")}),
        (
            "Privacidade e marketing",
            {
                "fields": (
                    ("marketing_email_autorizado", "marketing_whatsapp_autorizado"),
                    "marketing_base_legal",
                    "marketing_autorizado_em",
                    "marketing_origem",
                    "marketing_revogado_em",
                    "marketing_observacoes",
                ),
                "description": (
                    "Registre a base legal e a evidência antes de autorizar campanhas. "
                    "Ao revogar, desmarque os canais autorizados."
                ),
            },
        ),
    )


# =========================
# USUÁRIOS COM PERFIL
# =========================

class PerfilInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    extra = 0


class CustomUserAdmin(UserAdmin):
    inlines = (PerfilInline,)


# evita erro se já estiver registrado
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, CustomUserAdmin)
