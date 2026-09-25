from django.contrib import admin

from .models import Fornecedor, FornecedorUsuario


class FornecedorUsuarioInline(admin.TabularInline):
    model = FornecedorUsuario
    extra = 0


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("razao_social", "cnpj", "status", "qualificacao_atual", "pontuacao_atual", "validade_qualificacao")
    list_filter = ("status", "qualificacao_atual")
    search_fields = ("razao_social", "nome_fantasia", "cnpj", "codigo_externo")
    inlines = [FornecedorUsuarioInline]


@admin.register(FornecedorUsuario)
class FornecedorUsuarioAdmin(admin.ModelAdmin):
    list_display = ("fornecedor", "user", "principal", "ativo")
    list_filter = ("principal", "ativo")
    search_fields = ("fornecedor__razao_social", "user__username", "user__email")

# Register your models here.
