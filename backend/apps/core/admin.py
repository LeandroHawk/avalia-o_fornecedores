from django.contrib import admin

from .models import Configuracao


@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ("chave", "descricao", "atualizado_em")
    search_fields = ("chave", "descricao")

# Register your models here.
