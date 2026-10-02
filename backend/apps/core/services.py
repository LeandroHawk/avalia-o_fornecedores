from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q
from django.utils import timezone

from backend.apps.accounts.utils import is_admin, is_compras
from backend.apps.avaliacoes.display import get_status_class
from backend.apps.avaliacoes.models import Avaliacao
from backend.apps.fornecedores.models import Fornecedor
from backend.apps.qualificacoes.models import Qualificacao


STATUS_CHART_ORDER = [
    ("convidado", "Convidado", "#edf3ff"),
    ("em-analise", "Em análise", "#243f88"),
    ("ajustes", "Ajustes solicitados", "#f7c948"),
    ("aprovado", "Aprovado", "#12a05c"),
    ("reprovado", "Reprovado", "#d92d20"),
]

SCORE_BUCKETS = [
    ("Sem pontuação", None, None),
    ("0 a 59", Decimal("0"), Decimal("59.99")),
    ("60 a 84", Decimal("60"), Decimal("84.99")),
    ("85 a 94", Decimal("85"), Decimal("94.99")),
    ("95 a 100", Decimal("95"), Decimal("100")),
]


def _display_status_class(avaliacao):
    return get_status_class(avaliacao)


def _build_chart_context(avaliacoes):
    total_status = len(avaliacoes)
    status_counts = {key: 0 for key, _label, _color in STATUS_CHART_ORDER}
    for avaliacao in avaliacoes:
        key = _display_status_class(avaliacao)
        status_counts[key] = status_counts.get(key, 0) + 1

    pie_start = 0
    pie_segments = []
    status_chart = []
    for key, label, color in STATUS_CHART_ORDER:
        count = status_counts.get(key, 0)
        percent = round((count / total_status) * 100) if total_status else 0
        degrees = round((count / total_status) * 360, 2) if total_status else 0
        if degrees:
            pie_segments.append(f"{color} {pie_start}deg {pie_start + degrees}deg")
            pie_start += degrees
        status_chart.append({"key": key, "label": label, "count": count, "percent": percent, "color": color})

    score_counts = []
    for label, start, end in SCORE_BUCKETS:
        if start is None:
            count = sum(1 for avaliacao in avaliacoes if avaliacao.pontuacao is None)
        else:
            count = sum(1 for avaliacao in avaliacoes if avaliacao.pontuacao is not None and start <= Decimal(avaliacao.pontuacao) <= end)
        score_counts.append({"label": label, "count": count})
    max_score_count = max((item["count"] for item in score_counts), default=0)
    axis_max = max(max_score_count, 3)
    return {
        "status_chart": status_chart,
        "status_pie_style": f"conic-gradient({', '.join(pie_segments)})" if pie_segments else "conic-gradient(#e3e8f0 0deg 360deg)",
        "score_axis_ticks": [axis_max, round(axis_max * Decimal("0.67"), 1), round(axis_max * Decimal("0.33"), 1), 0],
        "score_histogram": [
            {
                **item,
                "height": round((item["count"] / max_score_count) * 100) if max_score_count else 0,
            }
            for item in score_counts
        ],
    }


def build_dashboard_context(user):
    fornecedores = Fornecedor.objects.visible_to_user(user)
    avaliacoes = Avaliacao.objects.visible_to_user(user)
    avaliacoes_list = list(avaliacoes)
    display_counts = {key: 0 for key, _label, _color in STATUS_CHART_ORDER}
    for avaliacao in avaliacoes_list:
        key = _display_status_class(avaliacao)
        display_counts[key] = display_counts.get(key, 0) + 1
    hoje = timezone.localdate()
    vencendo = hoje + timedelta(days=30)
    total_avaliacoes = len(avaliacoes_list)
    homologados = display_counts.get("aprovado", 0)
    reprovados = display_counts.get("reprovado", 0)
    taxa_homologacao = round((homologados / total_avaliacoes) * 100) if total_avaliacoes else 0
    taxa_pendencia = round(((display_counts.get("convidado", 0) + display_counts.get("em-analise", 0)) / total_avaliacoes) * 100) if total_avaliacoes else 0
    context = {
        "total_fornecedores": fornecedores.count(),
        "pendentes": avaliacoes.filter(status__in=[Avaliacao.Status.RASCUNHO, Avaliacao.Status.ENVIADA]).count(),
        "em_analise": avaliacoes.filter(status=Avaliacao.Status.EM_ANALISE).count(),
        "devolvidas": avaliacoes.filter(status__in=[Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO]).count(),
        "homologados": homologados,
        "reprovados": reprovados,
        "vencendo": avaliacoes.filter(fim_vigencia__range=[hoje, vencendo]).count(),
        "vencidas": avaliacoes.filter(fim_vigencia__lt=hoje).count(),
        "media": avaliacoes.aggregate(media=Avg("pontuacao"))["media"],
        "qualificacoes": Qualificacao.objects.visible_to_user(user).values("status").annotate(total=Count("id")),
        "can_show_compras_dashboard": is_compras(user) or is_admin(user),
        "total_avaliacoes": total_avaliacoes,
        "taxa_homologacao": taxa_homologacao,
        "taxa_pendencia": taxa_pendencia,
    }
    context.update(_build_chart_context(avaliacoes_list))
    return context


def list_pendencias(user):
    hoje = timezone.localdate()
    vencendo = hoje + timedelta(days=30)
    avaliacoes = list(
        Avaliacao.objects.visible_to_user(user)
        .filter(
            Q(status__in=[Avaliacao.Status.ENVIADA, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO])
            | Q(fim_vigencia__lte=vencendo)
        )
        .with_detail_relations()
    )
    for avaliacao in avaliacoes:
        if avaliacao.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
            avaliacao.pending_status_class = "ajustes"
            avaliacao.pending_status_label = "Ajustes solicitados"
        elif avaliacao.fim_vigencia and avaliacao.fim_vigencia < hoje:
            avaliacao.pending_status_class = "vencida"
            avaliacao.pending_status_label = "Vencida"
        elif avaliacao.fim_vigencia and avaliacao.fim_vigencia <= vencendo:
            avaliacao.pending_status_class = "vencendo"
            avaliacao.pending_status_label = "Vencendo"
        else:
            avaliacao.pending_status_class = "em-analise"
            avaliacao.pending_status_label = "Em análise"
    return avaliacoes
