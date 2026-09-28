from rest_framework import serializers

from backend.apps.avaliacoes.models import Avaliacao
from backend.apps.fornecedores.models import Fornecedor
from backend.apps.notificacoes.models import Notificacao
from backend.apps.qualificacoes.models import Qualificacao
from backend.apps.questionarios.models import Questionario, QuestionarioVersao


class FornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fornecedor
        fields = [
            "id",
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "codigo_externo",
            "status",
            "qualificacao_atual",
            "pontuacao_atual",
            "validade_qualificacao",
        ]


class QuestionarioVersaoSerializer(serializers.ModelSerializer):
    questionario = serializers.StringRelatedField()

    class Meta:
        model = QuestionarioVersao
        fields = ["id", "questionario", "numero", "titulo", "publicado", "ativo"]


class QuestionarioSerializer(serializers.ModelSerializer):
    versoes = QuestionarioVersaoSerializer(many=True, read_only=True)

    class Meta:
        model = Questionario
        fields = ["id", "nome", "descricao", "ativo", "versoes"]


class AvaliacaoSerializer(serializers.ModelSerializer):
    fornecedor = FornecedorSerializer(read_only=True)
    questionario_versao = QuestionarioVersaoSerializer(read_only=True)

    class Meta:
        model = Avaliacao
        fields = [
            "id",
            "fornecedor",
            "questionario_versao",
            "periodo",
            "status",
            "pontuacao",
            "qualificacao",
            "inicio_vigencia",
            "fim_vigencia",
        ]


class QualificacaoSerializer(serializers.ModelSerializer):
    fornecedor = FornecedorSerializer(read_only=True)

    class Meta:
        model = Qualificacao
        fields = ["id", "fornecedor", "status", "pontuacao", "inicio_vigencia", "fim_vigencia"]


class NotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacao
        fields = ["id", "tipo", "titulo", "mensagem", "lida_em", "url", "criado_em"]
