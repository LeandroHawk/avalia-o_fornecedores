from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render
from django.utils import timezone

from backend.apps.accounts.utils import is_compras, is_fornecedor
from backend.apps.avaliacoes.models import Avaliacao
from backend.apps.fornecedores.security import fornecedores_for_user
from backend.apps.qualificacoes.models import Qualificacao


def home(request):
    return render(request, "core/home.html")


@login_required
def dashboard(request):
    fornecedores = fornecedores_for_user(request.user)
    avaliacoes = Avaliacao.objects.filter(fornecedor__in=fornecedores)
    hoje = timezone.localdate()
    vencendo = hoje + timedelta(days=30)
    contexto = {
        "total_fornecedores": fornecedores.count(),
        "pendentes": avaliacoes.filter(status__in=[Avaliacao.Status.RASCUNHO, Avaliacao.Status.ENVIADA]).count(),
        "em_analise": avaliacoes.filter(status=Avaliacao.Status.EM_ANALISE).count(),
        "devolvidas": avaliacoes.filter(status__in=[Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO]).count(),
        "vencendo": avaliacoes.filter(fim_vigencia__range=[hoje, vencendo]).count(),
        "vencidas": avaliacoes.filter(fim_vigencia__lt=hoje).count(),
        "media": avaliacoes.aggregate(media=Avg("pontuacao"))["media"],
        "qualificacoes": Qualificacao.objects.filter(fornecedor__in=fornecedores).values("status").annotate(total=Count("id")),
        "is_fornecedor": is_fornecedor(request.user),
        "is_compras": is_compras(request.user),
    }
    return render(request, "core/dashboard.html", contexto)


@login_required
def central_pendencias(request):
    fornecedores = fornecedores_for_user(request.user)
    hoje = timezone.localdate()
    vencendo = hoje + timedelta(days=30)
    avaliacoes = (
        Avaliacao.objects.filter(fornecedor__in=fornecedores)
        .filter(
            Q(status__in=[Avaliacao.Status.ENVIADA, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO])
            | Q(fim_vigencia__lte=vencendo)
        )
        .select_related("fornecedor", "questionario_versao")
    )
    return render(request, "core/pendencias.html", {"avaliacoes": avaliacoes})
