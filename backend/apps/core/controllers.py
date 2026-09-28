from django.shortcuts import redirect, render

from .services import build_dashboard_context, list_pendencias


def home(request):
    if getattr(request.user, "is_authenticated", False):
        return redirect("avaliacao_list")
    return render(request, "core/home.html")


def dashboard(request):
    return render(request, "core/dashboard.html", build_dashboard_context(request.user))


def central_pendencias(request):
    return render(request, "core/pendencias.html", {"avaliacoes": list_pendencias(request.user)})
