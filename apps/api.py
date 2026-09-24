from rest_framework import permissions, routers, serializers, viewsets

from apps.avaliacoes.models import Avaliacao
from apps.fornecedores.models import Fornecedor
from apps.fornecedores.security import fornecedores_for_user
from apps.notificacoes.models import Notificacao
from apps.qualificacoes.models import Qualificacao
from apps.questionarios.models import Questionario, QuestionarioVersao


class FornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fornecedor
        fields = ["id", "razao_social", "nome_fantasia", "cnpj", "codigo_externo", "status", "qualificacao_atual", "pontuacao_atual", "validade_qualificacao"]


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
        fields = ["id", "fornecedor", "questionario_versao", "periodo", "status", "pontuacao", "qualificacao", "inicio_vigencia", "fim_vigencia"]


class QualificacaoSerializer(serializers.ModelSerializer):
    fornecedor = FornecedorSerializer(read_only=True)

    class Meta:
        model = Qualificacao
        fields = ["id", "fornecedor", "status", "pontuacao", "inicio_vigencia", "fim_vigencia"]


class NotificacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacao
        fields = ["id", "tipo", "titulo", "mensagem", "lida_em", "url", "criado_em"]


class ScopedModelViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]


class FornecedorViewSet(ScopedModelViewSet):
    serializer_class = FornecedorSerializer

    def get_queryset(self):
        return fornecedores_for_user(self.request.user)


class QuestionarioViewSet(ScopedModelViewSet):
    queryset = Questionario.objects.filter(ativo=True).prefetch_related("versoes")
    serializer_class = QuestionarioSerializer


class AvaliacaoViewSet(ScopedModelViewSet):
    serializer_class = AvaliacaoSerializer

    def get_queryset(self):
        return Avaliacao.objects.filter(fornecedor__in=fornecedores_for_user(self.request.user)).select_related("fornecedor", "questionario_versao")


class QualificacaoViewSet(ScopedModelViewSet):
    serializer_class = QualificacaoSerializer

    def get_queryset(self):
        return Qualificacao.objects.filter(fornecedor__in=fornecedores_for_user(self.request.user)).select_related("fornecedor")


class NotificacaoViewSet(ScopedModelViewSet):
    serializer_class = NotificacaoSerializer

    def get_queryset(self):
        return Notificacao.objects.filter(usuario=self.request.user)


router = routers.DefaultRouter()
router.register("fornecedores", FornecedorViewSet, basename="fornecedor")
router.register("questionarios", QuestionarioViewSet, basename="questionario")
router.register("avaliacoes", AvaliacaoViewSet, basename="avaliacao")
router.register("qualificacoes", QualificacaoViewSet, basename="qualificacao")
router.register("notificacoes", NotificacaoViewSet, basename="notificacao")
