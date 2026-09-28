from rest_framework import routers

from .controllers import AvaliacaoViewSet, FornecedorViewSet, NotificacaoViewSet, QualificacaoViewSet, QuestionarioViewSet


router = routers.DefaultRouter()
router.register("fornecedores", FornecedorViewSet, basename="fornecedor")
router.register("questionarios", QuestionarioViewSet, basename="questionario")
router.register("avaliacoes", AvaliacaoViewSet, basename="avaliacao")
router.register("qualificacoes", QualificacaoViewSet, basename="qualificacao")
router.register("notificacoes", NotificacaoViewSet, basename="notificacao")

urlpatterns = router.urls
