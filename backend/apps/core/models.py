from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Configuracao(TimeStampedModel):
    chave = models.CharField(max_length=120, unique=True)
    valor = models.JSONField(default=dict, blank=True)
    descricao = models.TextField(blank=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="configuracoes_atualizadas",
    )

    class Meta:
        verbose_name = "configuracao"
        verbose_name_plural = "configuracoes"

    def __str__(self):
        return self.chave

    @classmethod
    def get_value(cls, chave, default=None):
        obj = cls.objects.filter(chave=chave).only("valor").first()
        return obj.valor if obj else default
