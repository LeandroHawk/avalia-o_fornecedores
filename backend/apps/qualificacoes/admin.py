from django.contrib import admin

from .models import Qualificacao


@admin.register(Qualificacao)
class QualificacaoAdmin(admin.ModelAdmin):
    list_display = ("fornecedor", "status", "pontuacao", "inicio_vigencia", "fim_vigencia")
    list_filter = ("status", "fim_vigencia")
    search_fields = ("fornecedor__razao_social",)
