from django.conf import settings
from django.db import models

from backend.apps.core.models import TimeStampedModel


class Notificacao(TimeStampedModel):
    class Tipo(models.TextChoices):
        AVALIACAO_DISPONIVEL = "AVALIACAO_DISPONIVEL", "Avaliacao disponivel"
        AVALIACAO_DEVOLVIDA = "AVALIACAO_DEVOLVIDA", "Avaliacao devolvida"
        AVALIACAO_APROVADA = "AVALIACAO_APROVADA", "Avaliacao aprovada"
        VENCIMENTO = "VENCIMENTO", "Vencimento"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificacoes")
    tipo = models.CharField(max_length=40, choices=Tipo.choices)
    titulo = models.CharField(max_length=160)
    mensagem = models.TextField()
    lida_em = models.DateTimeField(null=True, blank=True)
    url = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["tipo", "lida_em"])]

    def __str__(self):
        return self.titulo

# Create your models here.
