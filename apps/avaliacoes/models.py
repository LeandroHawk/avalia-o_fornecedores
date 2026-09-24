import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel
from apps.fornecedores.models import Fornecedor
from apps.questionarios.models import Questao, QuestionarioVersao


def evidencia_upload_to(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"evidencias/{instance.resposta.avaliacao_id}/{uuid.uuid4().hex}{ext}"


class Avaliacao(TimeStampedModel):
    class Status(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        ENVIADA = "ENVIADA", "Enviada para Compras"
        EM_ANALISE = "EM_ANALISE", "Em Analise"
        DEVOLVIDA = "DEVOLVIDA", "Devolvida"
        EM_CORRECAO = "EM_CORRECAO", "Em Correcao"
        FINALIZADA = "FINALIZADA", "Finalizada"

    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.PROTECT, related_name="avaliacoes")
    questionario_versao = models.ForeignKey(QuestionarioVersao, on_delete=models.PROTECT, related_name="avaliacoes")
    periodo = models.CharField(max_length=60)
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="avaliacoes_responsavel")
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.RASCUNHO, db_index=True)
    pontuacao = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    qualificacao = models.CharField(max_length=40, blank=True)
    inicio_vigencia = models.DateField(null=True, blank=True)
    fim_vigencia = models.DateField(null=True, blank=True)
    enviada_em = models.DateTimeField(null=True, blank=True)
    finalizada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["fornecedor", "status"]),
            models.Index(fields=["fim_vigencia"]),
        ]

    def __str__(self):
        return f"{self.fornecedor} - {self.periodo}"


class Resposta(TimeStampedModel):
    class Valor(models.TextChoices):
        SIM = "SIM", "Sim"
        NAO = "NAO", "Nao"
        NA = "NA", "Nao se aplica"

    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name="respostas")
    questao = models.ForeignKey(Questao, on_delete=models.PROTECT, related_name="respostas")
    resposta = models.CharField(max_length=30, choices=Valor.choices, blank=True)
    observacao = models.TextField(blank=True)
    justificativa = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="respostas")
    versao = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["avaliacao", "questao"], name="uniq_resposta_avaliacao_questao"),
        ]

    def clean(self):
        if self.questao.exige_justificativa_se_nao and self.resposta == self.Valor.NAO and not self.justificativa.strip():
            raise ValidationError({"justificativa": "Informe a justificativa para respostas Nao."})

    def __str__(self):
        return f"{self.avaliacao} - {self.questao_id}"


class Evidencia(TimeStampedModel):
    resposta = models.ForeignKey(Resposta, on_delete=models.CASCADE, related_name="evidencias")
    arquivo = models.FileField(upload_to=evidencia_upload_to)
    nome_original = models.CharField(max_length=255)
    extensao = models.CharField(max_length=12)
    mime_type = models.CharField(max_length=120)
    tamanho = models.PositiveIntegerField()
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="evidencias")
    ativo = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["ativo"])]

    def __str__(self):
        return self.nome_original


class Devolucao(TimeStampedModel):
    class Motivo(models.TextChoices):
        EVIDENCIA_INSUFICIENTE = "EVIDENCIA_INSUFICIENTE", "Evidencia insuficiente"
        DOCUMENTO_INVALIDO = "DOCUMENTO_INVALIDO", "Documento invalido"
        JUSTIFICATIVA_INSUFICIENTE = "JUSTIFICATIVA_INSUFICIENTE", "Justificativa insuficiente"
        INFORMACAO_INCOMPLETA = "INFORMACAO_INCOMPLETA", "Informacao incompleta"
        RESPOSTA_INCORRETA = "RESPOSTA_INCORRETA", "Resposta incorreta"
        OUTRO = "OUTRO", "Outro"

    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name="devolucoes")
    motivo = models.CharField(max_length=40, choices=Motivo.choices)
    comentario = models.TextField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="devolucoes")

    def __str__(self):
        return f"{self.avaliacao} - {self.get_motivo_display()}"


class HistoricoAvaliacao(TimeStampedModel):
    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name="historico")
    status_origem = models.CharField(max_length=30, blank=True)
    status_destino = models.CharField(max_length=30)
    acao = models.CharField(max_length=80)
    comentario = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.acao} - {self.avaliacao}"

# Create your models here.
