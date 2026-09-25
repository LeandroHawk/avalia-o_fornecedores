from django.contrib import admin

from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo", "titulo", "lida_em", "criado_em")
    list_filter = ("tipo", "lida_em")
    search_fields = ("titulo", "mensagem", "usuario__username")
