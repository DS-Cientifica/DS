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
    readonly_fields = ("ver_arquivo",)

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

    list_display = (
        "codigo",
        "razao_social",
        "cnpj",
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
        "uf",
    )

    fieldsets = (
        ("Dados Gerais", {
            "fields": (
                "codigo",
                "razao_social",
                "nome_empresa",
                "cnpj",
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

        # 🔥 AGORA CORRETO
        ("Anexo", {
            "fields": (
                "nome_anexo",
                "anexo",
            )
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
    )

    search_fields = (
        "nome",
        "email",
        "cliente__razao_social",
    )

    list_filter = (
        "principal",
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
