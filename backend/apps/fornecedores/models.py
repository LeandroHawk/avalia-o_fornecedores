from django.conf import settings
from django.db import models

from backend.apps.core.models import TimeStampedModel


class Fornecedor(TimeStampedModel):
    class Status(models.TextChoices):
        ATIVO = "ATIVO", "Ativo"
        INATIVO = "INATIVO", "Inativo"
        BLOQUEADO = "BLOQUEADO", "Bloqueado"

    razao_social = models.CharField(max_length=180)
    nome_fantasia = models.CharField(max_length=180, blank=True)
    cnpj = models.CharField(max_length=18, unique=True)
    codigo_externo = models.CharField(max_length=60, blank=True, db_index=True)
    email = models.EmailField()
    inscricao_municipal = models.CharField(max_length=40, blank=True)
    inscricao_estadual = models.CharField(max_length=40, blank=True)
    endereco = models.CharField(max_length=220, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    site = models.URLField(blank=True)
    quantidade_funcionarios = models.PositiveIntegerField(null=True, blank=True)
    responsavel = models.CharField(max_length=120, blank=True)
    cargo_responsavel = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ATIVO)
    qualificacao_atual = models.CharField(max_length=40, blank=True)
    pontuacao_atual = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    validade_qualificacao = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["razao_social"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["validade_qualificacao"]),
        ]

    def __str__(self):
        return self.nome_fantasia or self.razao_social


class FornecedorUsuario(TimeStampedModel):
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name="usuarios")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fornecedor_vinculo")
    principal = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fornecedor", "user"], name="uniq_fornecedor_usuario"),
        ]

    def __str__(self):
        return f"{self.user.get_username()} - {self.fornecedor}"
