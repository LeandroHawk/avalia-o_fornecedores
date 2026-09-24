from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Auditoria(TimeStampedModel):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    acao = models.CharField(max_length=80, db_index=True)
    objeto = models.CharField(max_length=120, db_index=True)
    objeto_id = models.CharField(max_length=80, blank=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    valor_anterior = models.JSONField(null=True, blank=True)
    valor_posterior = models.JSONField(null=True, blank=True)
    resultado = models.CharField(max_length=40, default="SUCESSO")

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.acao} {self.objeto} {self.objeto_id}"

# Create your models here.
