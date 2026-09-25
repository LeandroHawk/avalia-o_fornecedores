from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from backend.apps.accounts.utils import is_admin, is_compras, is_fornecedor
from backend.apps.fornecedores.security import fornecedores_for_user
from backend.apps.questionarios.models import Questao

from .forms import DevolucaoForm, FornecedorCadastroForm, RespostaForm
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


STATUS_LABELS = {
    Avaliacao.Status.RASCUNHO: "Rascunho",
    Avaliacao.Status.ENVIADA: "Em analise",
    Avaliacao.Status.EM_ANALISE: "Em analise",
    Avaliacao.Status.DEVOLVIDA: "Ajustes solicitados",
    Avaliacao.Status.EM_CORRECAO: "Ajustes solicitados",
    Avaliacao.Status.FINALIZADA: "Homologado",
}


def _slug_status(label):
    return label.lower().replace(" ", "-")


def _resposta_valida(questao, valor):
    if not valor:
        return ""
    if questao.tipo == Questao.Tipo.ESCALA_0_5:
        return valor if valor in {"0", "1", "2", "3", "4", "5"} else ""
    if questao.tipo == Questao.Tipo.MULTIPLA_ESCOLHA:
        permitidos = {opcao.valor for opcao in questao.opcoes.filter(ativa=True)}
        return valor if valor in permitidos else ""
    if questao.tipo == Questao.Tipo.ARQUIVO:
        return Resposta.Valor.SIM if valor == Resposta.Valor.SIM else ""
    return valor if valor in {Resposta.Valor.SIM, Resposta.Valor.NAO, Resposta.Valor.NA} else ""


def _build_avaliacao_context(request, avaliacao, cadastro_form=None):
    categorias = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes__opcoes")
    respostas = {r.questao_id: r for r in avaliacao.respostas.prefetch_related("evidencias")}
    categorias_data = []
    total_fornecedor = respondidas_fornecedor = 0
    anexos_pendentes = criticos = 0

    for categoria in categorias:
        questoes = []
        cat_total = cat_respondidas = 0
        for questao in categoria.questoes.filter(ativa=True):
            resposta = respostas.get(questao.id)
            evidencia_ok = bool(resposta and resposta.evidencias.filter(ativo=True).exists())
            respondida = bool(resposta and resposta.resposta)
            if questao.tipo == Questao.Tipo.ARQUIVO:
                respondida = evidencia_ok
            missing_file = bool(
                questao.obrigatoria
                and (
                    questao.tipo == Questao.Tipo.ARQUIVO
                    or (questao.exige_evidencia_se_sim and resposta and resposta.resposta == Resposta.Valor.SIM)
                )
                and not evidencia_ok
            )
            if questao.uso_interno_compras:
                editable = is_compras(request.user) or is_admin(request.user)
            else:
                editable = is_fornecedor(request.user) or is_admin(request.user)
                total_fornecedor += 1
                if respondida:
                    respondidas_fornecedor += 1
            cat_total += 1
            if respondida:
                cat_respondidas += 1
            if missing_file:
                anexos_pendentes += 1
            if questao.critica and resposta and resposta.resposta == Resposta.Valor.NAO:
                criticos += 1
            questoes.append(
                {
                    "questao": questao,
                    "resposta": resposta,
                    "respondida": respondida,
                    "missing_file": missing_file,
                    "editable": editable,
                    "opcoes": questao.opcoes.filter(ativa=True),
                }
            )
        categorias_data.append(
            {
                "categoria": categoria,
                "questoes": questoes,
                "total": cat_total,
                "respondidas": cat_respondidas,
                "percentual": round((cat_respondidas / cat_total) * 100) if cat_total else 0,
            }
        )

    dados_fields = [
        "razao_social",
        "nome_fantasia",
        "cnpj",
        "inscricao_municipal",
        "inscricao_estadual",
        "endereco",
        "cidade",
        "estado",
        "telefone",
        "site",
        "quantidade_funcionarios",
        "responsavel",
        "cargo_responsavel",
    ]
    dados_total = len(dados_fields)
    dados_preenchidos = sum(1 for field in dados_fields if getattr(avaliacao.fornecedor, field))
    progress_total = total_fornecedor + dados_total
    progress_done = respondidas_fornecedor + dados_preenchidos
    progresso = round((progress_done / progress_total) * 100) if progress_total else 0
    form = cadastro_form or FornecedorCadastroForm(instance=avaliacao.fornecedor)
    if is_compras(request.user) and not is_admin(request.user):
        for field in form.fields.values():
            field.disabled = True
    status_label = STATUS_LABELS.get(avaliacao.status, avaliacao.get_status_display())
    return {
        "avaliacao": avaliacao,
        "cadastro_form": form,
        "categorias_data": categorias_data,
        "can_review": is_compras(request.user) or is_admin(request.user),
        "can_fill": is_fornecedor(request.user) or is_admin(request.user),
        "status_label": status_label,
        "status_class": _slug_status(status_label),
        "dados_total": dados_total,
        "dados_preenchidos": dados_preenchidos,
        "progress_total": progress_total,
        "progress_done": progress_done,
        "progresso": progresso,
        "apto": progresso >= 85 and criticos == 0,
        "pendencias": max(progress_total - progress_done, 0),
        "anexos_pendentes": anexos_pendentes,
        "criticos": criticos,
    }


@login_required
def avaliacao_list(request):
    qs = (
        Avaliacao.objects.filter(fornecedor__in=fornecedores_for_user(request.user))
        .select_related("fornecedor", "questionario_versao", "questionario_versao__questionario")
        .order_by("-criado_em")
    )
    avaliacoes = list(qs)
    for avaliacao in avaliacoes:
        avaliacao.criticos = avaliacao.respostas.filter(questao__critica=True, resposta=Resposta.Valor.NAO).count()
        internas = avaliacao.respostas.filter(questao__uso_interno_compras=True, resposta__in=["0", "1", "2", "3", "4", "5"])
        notas = [int(r.resposta) for r in internas]
        avaliacao.nota_interna = round(sum(notas) / len(notas), 1) if notas else ""
        if avaliacao.status == Avaliacao.Status.RASCUNHO:
            avaliacao.display_status = "Convidado"
            avaliacao.status_class = "convidado"
        elif avaliacao.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}:
            avaliacao.display_status = "Em analise"
            avaliacao.status_class = "em-analise"
        elif avaliacao.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
            avaliacao.display_status = "Ajustes solicitados"
            avaliacao.status_class = "ajustes"
        elif avaliacao.qualificacao == "NAO_QUALIFICADO" or (avaliacao.pontuacao and avaliacao.pontuacao < 95):
            avaliacao.display_status = "Reprovado"
            avaliacao.status_class = "reprovado"
        else:
            avaliacao.display_status = "Homologado"
            avaliacao.status_class = "homologado"
    contexto = {
        "avaliacoes": avaliacoes,
        "em_analise": sum(1 for a in avaliacoes if a.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}),
        "ajustes": sum(1 for a in avaliacoes if a.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}),
        "homologados": sum(1 for a in avaliacoes if getattr(a, "display_status", "") == "Homologado"),
        "reprovados": sum(1 for a in avaliacoes if getattr(a, "display_status", "") == "Reprovado"),
    }
    return render(request, "avaliacoes/list.html", contexto)


@login_required
def avaliacao_detail(request, pk):
    avaliacao = get_object_or_404(
        Avaliacao.objects.select_related("fornecedor", "questionario_versao"),
        pk=pk,
        fornecedor__in=fornecedores_for_user(request.user),
    )
    if request.method == "POST":
        cadastro_form = FornecedorCadastroForm(request.POST, instance=avaliacao.fornecedor)
        try:
            if (is_fornecedor(request.user) or is_admin(request.user)) and cadastro_form.is_valid():
                cadastro_form.save()
            elif is_fornecedor(request.user) or is_admin(request.user):
                messages.error(request, "Revise os dados cadastrais informados.")
                return render(request, "avaliacoes/detail.html", _build_avaliacao_context(request, avaliacao, cadastro_form))

            questoes = Questao.objects.filter(categoria__versao=avaliacao.questionario_versao, ativa=True).prefetch_related("opcoes")
            for questao in questoes:
                if questao.uso_interno_compras and not (is_compras(request.user) or is_admin(request.user)):
                    continue
                if not questao.uso_interno_compras and not (is_fornecedor(request.user) or is_admin(request.user)):
                    continue
                valor = _resposta_valida(questao, request.POST.get(f"q_{questao.id}", ""))
                file_obj = request.FILES.get(f"q_{questao.id}_file")
                if not valor and file_obj and questao.tipo == Questao.Tipo.ARQUIVO:
                    valor = Resposta.Valor.SIM
                if not valor and not file_obj:
                    continue
                resposta = salvar_resposta(
                    avaliacao=avaliacao,
                    questao=questao,
                    usuario=request.user,
                    resposta=valor,
                    observacao=request.POST.get(f"q_{questao.id}_obs", "")[:1000],
                    justificativa="",
                )
                if file_obj:
                    anexar_evidencia(resposta=resposta, file_obj=file_obj, usuario=request.user, request=request)

            action = request.POST.get("action")
            if action == "enviar":
                enviar_avaliacao(avaliacao, request.user, request=request)
                messages.success(request, "Avaliacao enviada para analise.")
            elif action == "iniciar_analise":
                iniciar_analise(avaliacao, request.user, request=request)
                messages.success(request, "Analise iniciada.")
            elif action == "homologar":
                if avaliacao.status == Avaliacao.Status.ENVIADA:
                    iniciar_analise(avaliacao, request.user, request=request)
                    avaliacao.refresh_from_db()
                finalizar_avaliacao(avaliacao, request.user, request=request)
                messages.success(request, "Fornecedor homologado.")
            elif action == "reprovar":
                devolver_avaliacao(avaliacao, request.user, Devolucao.Motivo.RESPOSTA_INCORRETA, request.POST.get("parecer", "Reprovado por Compras."), request=request)
                messages.success(request, "Avaliacao reprovada/devolvida ao fornecedor.")
            else:
                messages.success(request, "Alteracoes salvas.")
            return redirect("avaliacao_detail", pk=avaliacao.pk)
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
            return render(request, "avaliacoes/detail.html", _build_avaliacao_context(request, avaliacao, cadastro_form))

    return render(request, "avaliacoes/detail.html", _build_avaliacao_context(request, avaliacao))


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
