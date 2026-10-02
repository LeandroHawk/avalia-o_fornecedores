from django.shortcuts import redirect, render

from backend.apps.accounts.utils import is_fornecedor

from .services import build_dashboard_context, list_pendencias


def home(request):
    if getattr(request.user, "is_authenticated", False):
        return redirect("avaliacao_list")
    return render(request, "home.html")


def dashboard(request):
    if is_fornecedor(request.user):
        return redirect("avaliacao_list")
    return render(request, "dashboard.html", build_dashboard_context(request.user))


def central_pendencias(request):
    return render(request, "pendencias.html", {"avaliacoes": list_pendencias(request.user)})
