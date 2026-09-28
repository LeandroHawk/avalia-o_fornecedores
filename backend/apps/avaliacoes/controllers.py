from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import redirect, render

from .models import Avaliacao, Evidencia
from .services import (
    build_avaliacao_context,
    get_avaliacao_for_user,
    get_avaliacao_list_context,
    get_evidencia_for_download,
    process_avaliacao_submission,
)


def avaliacao_list(request):
    return render(request, "avaliacoes/list.html", get_avaliacao_list_context(request.user))


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
                return render(
                    request,
                    "avaliacoes/detail.html",
                    build_avaliacao_context(request.user, avaliacao, result["cadastro_form"]),
                )
            messages.success(request, result["message"])
            return redirect("avaliacao_detail", pk=avaliacao.pk)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            return render(request, "avaliacoes/detail.html", build_avaliacao_context(request.user, avaliacao))

    return render(request, "avaliacoes/detail.html", build_avaliacao_context(request.user, avaliacao))


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
