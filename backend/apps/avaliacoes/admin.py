from django.contrib import admin

from .models import AjusteQuestao, Avaliacao, Devolucao, Evidencia, HistoricoAvaliacao, Resposta


class RespostaInline(admin.TabularInline):
    model = Resposta
    extra = 0


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("fornecedor", "periodo", "status", "pontuacao", "qualificacao", "fim_vigencia")
    list_filter = ("status", "qualificacao")
    search_fields = ("fornecedor__razao_social", "periodo")
    inlines = [RespostaInline]


@admin.register(Resposta)
class RespostaAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "questao", "resposta", "usuario", "versao")
    list_filter = ("resposta",)


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ("nome_original", "resposta", "mime_type", "tamanho", "ativo")
    list_filter = ("ativo", "mime_type")


@admin.register(Devolucao)
class DevolucaoAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "motivo", "usuario", "criado_em")
    list_filter = ("motivo",)


@admin.register(AjusteQuestao)
class AjusteQuestaoAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "questao", "status", "solicitado_por", "criado_em")
    list_filter = ("status",)
    search_fields = ("avaliacao__fornecedor__razao_social", "questao__enunciado", "motivo")


@admin.register(HistoricoAvaliacao)
class HistoricoAvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("avaliacao", "acao", "status_origem", "status_destino", "usuario", "criado_em")
    list_filter = ("acao", "status_destino")
