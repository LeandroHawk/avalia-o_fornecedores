from rest_framework import permissions, viewsets

from backend.apps.avaliacoes.models import Avaliacao
from backend.apps.fornecedores.models import Fornecedor
from backend.apps.notificacoes.models import Notificacao
from backend.apps.qualificacoes.models import Qualificacao
from backend.apps.questionarios.models import Questionario

from .serializers import (
    AvaliacaoSerializer,
    FornecedorSerializer,
    NotificacaoSerializer,
    QualificacaoSerializer,
    QuestionarioSerializer,
)


class ScopedModelViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]


class FornecedorViewSet(ScopedModelViewSet):
    serializer_class = FornecedorSerializer

    def get_queryset(self):
        return Fornecedor.objects.visible_to_user(self.request.user)


class QuestionarioViewSet(ScopedModelViewSet):
    serializer_class = QuestionarioSerializer

    def get_queryset(self):
        return Questionario.objects.active_with_versions()


class AvaliacaoViewSet(ScopedModelViewSet):
    serializer_class = AvaliacaoSerializer

    def get_queryset(self):
        return Avaliacao.objects.visible_to_user(self.request.user).with_detail_relations()


class QualificacaoViewSet(ScopedModelViewSet):
    serializer_class = QualificacaoSerializer

    def get_queryset(self):
        return Qualificacao.objects.visible_to_user(self.request.user).select_related("fornecedor")


class NotificacaoViewSet(ScopedModelViewSet):
    serializer_class = NotificacaoSerializer

    def get_queryset(self):
        return Notificacao.objects.for_user(self.request.user)
