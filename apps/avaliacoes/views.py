from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.utils import is_admin, is_compras
from apps.fornecedores.security import fornecedores_for_user
from apps.questionarios.models import Questao

from .forms import DevolucaoForm, RespostaForm
from .models import Avaliacao, Devolucao, Evidencia, Resposta
from .services import (
    anexar_evidencia,
    assert_can_access_avaliacao,
    devolver_avaliacao,
    enviar_avaliacao,
    finalizar_avaliacao,
    iniciar_analise,
    iniciar_correcao,
    salvar_resposta,
)


@login_required
def avaliacao_list(request):
    qs = (
        Avaliacao.objects.filter(fornecedor__in=fornecedores_for_user(request.user))
        .select_related("fornecedor", "questionario_versao", "questionario_versao__questionario")
        .order_by("-criado_em")
    )
    return render(request, "avaliacoes/list.html", {"avaliacoes": qs})


@login_required
def avaliacao_detail(request, pk):
    avaliacao = get_object_or_404(
        Avaliacao.objects.select_related("fornecedor", "questionario_versao"),
        pk=pk,
        fornecedor__in=fornecedores_for_user(request.user),
    )
    categorias = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes")
    respostas = {r.questao_id: r for r in avaliacao.respostas.prefetch_related("evidencias")}
    categorias_data = []
    for categoria in categorias:
        questoes = []
        for questao in categoria.questoes.filter(ativa=True):
            questoes.append({"questao": questao, "resposta": respostas.get(questao.id)})
        categorias_data.append({"categoria": categoria, "questoes": questoes})
    return render(
        request,
        "avaliacoes/detail.html",
        {
            "avaliacao": avaliacao,
            "categorias_data": categorias_data,
            "can_review": is_compras(request.user) or is_admin(request.user),
        },
    )


@login_required
def responder_questao(request, pk, questao_id):
    avaliacao = get_object_or_404(Avaliacao, pk=pk, fornecedor__in=fornecedores_for_user(request.user))
    questao = get_object_or_404(Questao, pk=questao_id, categoria__versao=avaliacao.questionario_versao, ativa=True)
    assert_can_access_avaliacao(request.user, avaliacao)
    resposta_atual = Resposta.objects.filter(avaliacao=avaliacao, questao=questao).first()
    if request.method == "POST":
        form = RespostaForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                resposta = salvar_resposta(
                    avaliacao=avaliacao,
                    questao=questao,
                    usuario=request.user,
                    resposta=form.cleaned_data["resposta"],
                    observacao=form.cleaned_data["observacao"],
                    justificativa=form.cleaned_data["justificativa"],
                )
                if form.cleaned_data.get("evidencia"):
                    anexar_evidencia(resposta=resposta, file_obj=form.cleaned_data["evidencia"], usuario=request.user, request=request)
                messages.success(request, "Alteracoes salvas.")
                return redirect("avaliacao_detail", pk=avaliacao.pk)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        form = RespostaForm(
            initial={
                "resposta": resposta_atual.resposta if resposta_atual else "",
                "observacao": resposta_atual.observacao if resposta_atual else "",
                "justificativa": resposta_atual.justificativa if resposta_atual else "",
            }
        )
    return render(request, "avaliacoes/responder.html", {"avaliacao": avaliacao, "questao": questao, "form": form, "resposta_atual": resposta_atual})


@login_required
def enviar(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk, fornecedor__in=fornecedores_for_user(request.user))
    if request.method == "POST":
        try:
            enviar_avaliacao(avaliacao, request.user, request=request)
            messages.success(request, "Avaliacao enviada para Compras.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("avaliacao_detail", pk=pk)


@login_required
def iniciar_analise_view(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk)
    if request.method == "POST":
        try:
            iniciar_analise(avaliacao, request.user, request=request)
            messages.success(request, "Analise iniciada.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("avaliacao_detail", pk=pk)


@login_required
def devolver(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk)
    if request.method == "POST":
        form = DevolucaoForm(request.POST)
        if form.is_valid():
            try:
                devolver_avaliacao(
                    avaliacao,
                    request.user,
                    form.cleaned_data["motivo"],
                    form.cleaned_data["comentario"],
                    request=request,
                )
                messages.success(request, "Avaliacao devolvida ao fornecedor.")
                return redirect("avaliacao_detail", pk=pk)
            except (ValidationError, PermissionDenied) as exc:
                messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        form = DevolucaoForm()
    return render(request, "avaliacoes/devolver.html", {"avaliacao": avaliacao, "form": form})


@login_required
def iniciar_correcao_view(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk, fornecedor__in=fornecedores_for_user(request.user))
    if request.method == "POST":
        try:
            iniciar_correcao(avaliacao, request.user, request=request)
            messages.success(request, "Correcao liberada.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("avaliacao_detail", pk=pk)


@login_required
def finalizar(request, pk):
    avaliacao = get_object_or_404(Avaliacao, pk=pk)
    if request.method == "POST":
        try:
            finalizar_avaliacao(avaliacao, request.user, request=request)
            messages.success(request, "Avaliacao finalizada e qualificacao registrada.")
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    return redirect("avaliacao_detail", pk=pk)


@login_required
def evidencia_download(request, pk):
    evidencia = get_object_or_404(Evidencia.objects.select_related("resposta__avaliacao"), pk=pk, ativo=True)
    if not evidencia.arquivo:
        raise Http404
    if not fornecedores_for_user(request.user).filter(pk=evidencia.resposta.avaliacao.fornecedor_id).exists():
        return HttpResponseForbidden("Sem permissao para acessar este arquivo.")
    return FileResponse(evidencia.arquivo.open("rb"), as_attachment=True, filename=evidencia.nome_original)
