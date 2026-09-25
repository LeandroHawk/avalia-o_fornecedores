from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from backend.apps.core.models import TimeStampedModel


class Questionario(TimeStampedModel):
    nome = models.CharField(max_length=140)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class QuestionarioVersao(TimeStampedModel):
    questionario = models.ForeignKey(Questionario, on_delete=models.PROTECT, related_name="versoes")
    numero = models.PositiveIntegerField()
    titulo = models.CharField(max_length=160)
    publicado = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["questionario", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["questionario", "numero"], name="uniq_questionario_versao"),
        ]

    def __str__(self):
        return f"{self.questionario} - v{self.numero}"


class Categoria(TimeStampedModel):
    versao = models.ForeignKey(QuestionarioVersao, on_delete=models.PROTECT, related_name="categorias")
    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True)
    ordem = models.PositiveIntegerField(default=1)
    peso = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(0)])
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "nome"]
        constraints = [
            models.UniqueConstraint(fields=["versao", "nome"], name="uniq_categoria_por_versao"),
        ]

    def __str__(self):
        return self.nome


class Questao(TimeStampedModel):
    class Tipo(models.TextChoices):
        SIM_NAO = "SIM_NAO", "Sim ou Nao"
        TEXTO = "TEXTO", "Texto"
        MULTIPLA_ESCOLHA = "MULTIPLA_ESCOLHA", "Multipla escolha"
        ESCALA_0_5 = "ESCALA_0_5", "Escala de 0 a 5"
        ARQUIVO = "ARQUIVO", "Arquivo"

    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="questoes")
    enunciado = models.TextField()
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.SIM_NAO)
    ordem = models.PositiveIntegerField(default=1)
    peso = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(0)])
    obrigatoria = models.BooleanField(default=True)
    critica = models.BooleanField(default=False)
    uso_interno_compras = models.BooleanField(default=False)
    ajuda = models.CharField(max_length=180, blank=True)
    exige_evidencia_se_sim = models.BooleanField(default=True)
    exige_justificativa_se_nao = models.BooleanField(default=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["categoria__ordem", "ordem"]
        indexes = [models.Index(fields=["ativa"])]

    def __str__(self):
        return self.enunciado[:80]


class OpcaoResposta(TimeStampedModel):
    questao = models.ForeignKey(Questao, on_delete=models.PROTECT, related_name="opcoes")
    rotulo = models.CharField(max_length=80)
    valor = models.CharField(max_length=80)
    pontuacao = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    ordem = models.PositiveIntegerField(default=1)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "rotulo"]
        constraints = [
            models.UniqueConstraint(fields=["questao", "valor"], name="uniq_opcao_por_questao"),
        ]

    def __str__(self):
        return self.rotulo

# Create your models here.
