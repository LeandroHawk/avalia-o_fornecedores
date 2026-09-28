from django.conf import settings
from django.db import models

from backend.apps.core.models import TimeStampedModel
from backend.apps.fornecedores.models import Fornecedor


class QualificacaoQuerySet(models.QuerySet):
    def visible_to_user(self, user):
        return self.filter(fornecedor__in=Fornecedor.objects.visible_to_user(user))


class Qualificacao(TimeStampedModel):
    class Status(models.TextChoices):
        QUALIFICADO = "QUALIFICADO", "Qualificado"
        RESSALVAS = "RESSALVAS", "Qualificado com Ressalvas"
        NAO_QUALIFICADO = "NAO_QUALIFICADO", "Não Qualificado"
        INDEFINIDO = "INDEFINIDO", "Indefinido"

    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="qualificacoes")
    avaliacao = models.OneToOneField("avaliacoes.Avaliacao", on_delete=models.CASCADE, related_name="qualificacao_registro")
    status = models.CharField(max_length=30, choices=Status.choices)
    pontuacao = models.DecimalField(max_digits=6, decimal_places=2)
    inicio_vigencia = models.DateField()
    fim_vigencia = models.DateField()
    definida_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    objects = QualificacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-fim_vigencia"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["fim_vigencia"]),
        ]

    def __str__(self):
        return f"{self.fornecedor} - {self.get_status_display()}"
