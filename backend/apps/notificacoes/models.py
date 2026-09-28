from django.conf import settings
from django.db import models

from backend.apps.core.models import TimeStampedModel


class NotificacaoQuerySet(models.QuerySet):
    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(usuario=user)


class Notificacao(TimeStampedModel):
    class Tipo(models.TextChoices):
        AVALIACAO_DISPONIVEL = "AVALIACAO_DISPONIVEL", "Avaliação disponível"
        AVALIACAO_DEVOLVIDA = "AVALIACAO_DEVOLVIDA", "Avaliação devolvida"
        AVALIACAO_APROVADA = "AVALIACAO_APROVADA", "Avaliação aprovada"
        VENCIMENTO = "VENCIMENTO", "Vencimento"

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificacoes")
    tipo = models.CharField(max_length=40, choices=Tipo.choices)
    titulo = models.CharField(max_length=160)
    mensagem = models.TextField()
    lida_em = models.DateTimeField(null=True, blank=True)
    url = models.CharField(max_length=255, blank=True)

    objects = NotificacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["tipo", "lida_em"])]

    def __str__(self):
        return self.titulo
