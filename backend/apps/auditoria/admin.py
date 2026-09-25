from django.contrib import admin

from .models import Auditoria


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("acao", "objeto", "objeto_id", "usuario", "ip", "resultado", "criado_em")
    list_filter = ("acao", "objeto", "resultado")
    search_fields = ("acao", "objeto", "objeto_id", "usuario__username")
    readonly_fields = ("usuario", "acao", "objeto", "objeto_id", "ip", "valor_anterior", "valor_posterior", "resultado", "criado_em", "atualizado_em")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

# Register your models here.
