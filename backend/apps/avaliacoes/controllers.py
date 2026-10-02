from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import redirect, render

from backend.apps.accounts.utils import is_fornecedor

from .models import Avaliacao, Evidencia
from .services import (
    build_avaliacao_context,
    get_avaliacao_for_user,
    get_avaliacao_list_context,
    get_evidencia_for_download,
    get_or_create_fornecedor_avaliacao,
    process_avaliacao_submission,
)


def _detail_topbar_context(user, avaliacao):
    if is_fornecedor(user):
        return {
            "app_topbar_title": "Minha avaliação",
            "app_topbar_subtitle": "Dados, campos e evidências para preenchimento",
        }
    return {
        "app_topbar_title": avaliacao.fornecedor.razao_social,
        "app_topbar_subtitle": "Checklist, evidências e decisão da avaliação",
    }


def _render_avaliacao_detail(request, avaliacao, context):
    context.update(_detail_topbar_context(request.user, avaliacao))
    return render(request, "detail.html", context)


def avaliacao_list(request):
    if is_fornecedor(request.user):
        avaliacao = get_or_create_fornecedor_avaliacao(request.user)
        if avaliacao:
            return redirect("avaliacao_detail", pk=avaliacao.pk)
        return render(
            request,
            "supplier_unavailable.html",
            {
                "app_topbar_title": "Minha avaliação",
                "app_topbar_subtitle": "Campos e regras para preenchimento",
            },
        )

    return render(request, "list.html", get_avaliacao_list_context(request.user))


def avaliacao_detail(request, pk):
    try:
        avaliacao = get_avaliacao_for_user(request.user, pk)
    except Avaliacao.DoesNotExist as exc:
        raise Http404 from exc

    if request.method == "POST":
        try:
            result = process_avaliacao_submission(
                avaliacao=avaliacao,
                user=request.user,
                post_data=request.POST,
                files=request.FILES,
                request=request,
            )
            if not result["success"]:
                messages.error(request, result["message"])
                context = build_avaliacao_context(request.user, avaliacao, result["cadastro_form"])
                context.update(
                    {
                        "app_topbar_title": avaliacao.fornecedor.razao_social,
                        "app_topbar_subtitle": "Checklist, evidências e decisão da avaliação",
                    }
                )
                return _render_avaliacao_detail(request, avaliacao, context)
            messages.success(request, result["message"])
            return redirect("avaliacao_detail", pk=avaliacao.pk)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            context = build_avaliacao_context(request.user, avaliacao)
            context.update(
                {
                    "app_topbar_title": avaliacao.fornecedor.razao_social,
                    "app_topbar_subtitle": "Checklist, evidências e decisão da avaliação",
                }
            )
            return _render_avaliacao_detail(request, avaliacao, context)

    context = build_avaliacao_context(request.user, avaliacao)
    context.update(
        {
            "app_topbar_title": avaliacao.fornecedor.razao_social,
            "app_topbar_subtitle": "Checklist, evidências e decisão da avaliação",
        }
    )
    return _render_avaliacao_detail(request, avaliacao, context)


def evidencia_download(request, pk):
    try:
        evidencia = get_evidencia_for_download(request.user, pk)
    except Evidencia.DoesNotExist as exc:
        raise Http404 from exc
    except PermissionDenied:
        return HttpResponseForbidden("Sem permissão para acessar este arquivo.")
    if not evidencia.arquivo:
        raise Http404
    return FileResponse(evidencia.arquivo.open("rb"), as_attachment=True, filename=evidencia.nome_original)
