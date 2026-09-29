from django.urls import reverse

from backend.apps.accounts.utils import is_admin, is_compras, is_fornecedor
from backend.apps.notificacoes.models import Notificacao


PAGE_TITLES = {
    "dashboard": ("Indicadores", "Visão analítica das avaliações de fornecedores"),
    "pendencias": ("Pendências", "Itens que exigem acompanhamento"),
    "avaliacao_list": ("Avaliações", "Consulta e análise de fornecedores"),
    "avaliacao_detail": ("Detalhe da avaliação", "Checklist, evidências e decisão"),
}


def _nav_item(request, *, label, icon, url_name, active_names=None):
    active_names = active_names or {url_name}
    return {
        "label": label,
        "icon": icon,
        "url": reverse(url_name),
        "active": getattr(request.resolver_match, "url_name", "") in active_names,
    }


def _navigation_items(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return []

    items = [_nav_item(request, label="Dashboard", icon="layout-dashboard", url_name="dashboard")]

    if is_fornecedor(user):
        items.append(_nav_item(request, label="Minhas avaliações", icon="list-check", url_name="avaliacao_list"))
    elif is_compras(user) or is_admin(user):
        items.append(_nav_item(request, label="Avaliações", icon="clipboard-check", url_name="avaliacao_list"))

    items.append(_nav_item(request, label="Pendências", icon="bell", url_name="pendencias"))

    if is_admin(user):
        items.append({"label": "Admin", "icon": "settings", "url": "/admin/", "active": request.path_info.startswith("/admin/")})

    return items


def app_shell(request):
    match_name = getattr(request.resolver_match, "url_name", "")
    default_title = "Grupo Cesari" if not getattr(request.user, "is_authenticated", False) else "Sistema BID"
    title, subtitle = PAGE_TITLES.get(match_name, (default_title, "Avaliação e qualificação de fornecedores"))
    unread_notifications = 0

    if getattr(request.user, "is_authenticated", False):
        unread_notifications = Notificacao.objects.for_user(request.user).filter(lida_em__isnull=True).count()

    return {
        "app_navigation_items": _navigation_items(request),
        "app_topbar_title": title,
        "app_topbar_subtitle": subtitle,
        "app_unread_notifications": unread_notifications,
    }
