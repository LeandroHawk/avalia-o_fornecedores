from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import shlex
import subprocess
import tempfile

from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts.utils import is_admin, is_compras, is_fornecedor
from backend.apps.auditoria.services import registrar_auditoria
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.security import user_can_access_fornecedor
from backend.apps.notificacoes.models import Notificacao
from backend.apps.questionarios.models import Questao
from backend.apps.qualificacoes.models import Qualificacao

from .forms import FornecedorCadastroForm
from .models import Avaliacao, Devolucao, Evidencia, HistoricoAvaliacao, Resposta


ALLOWED_TRANSITIONS = {
    Avaliacao.Status.RASCUNHO: {Avaliacao.Status.ENVIADA},
    Avaliacao.Status.ENVIADA: {Avaliacao.Status.EM_ANALISE, Avaliacao.Status.DEVOLVIDA},
    Avaliacao.Status.EM_ANALISE: {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.FINALIZADA},
    Avaliacao.Status.DEVOLVIDA: {Avaliacao.Status.EM_CORRECAO, Avaliacao.Status.ENVIADA},
    Avaliacao.Status.EM_CORRECAO: {Avaliacao.Status.ENVIADA},
}

STATUS_LABELS = {
    Avaliacao.Status.RASCUNHO: "Rascunho",
    Avaliacao.Status.ENVIADA: "Em análise",
    Avaliacao.Status.EM_ANALISE: "Em análise",
    Avaliacao.Status.DEVOLVIDA: "Ajustes solicitados",
    Avaliacao.Status.EM_CORRECAO: "Ajustes solicitados",
    Avaliacao.Status.FINALIZADA: "Aprovado",
}

LIST_STATUS_ORDER = [
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


def resposta_valida(questao, valor):
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


def get_avaliacao_for_user(user, pk):
    return Avaliacao.objects.visible_to_user(user).with_detail_relations().get(pk=pk)


def get_evidencia_for_download(user, pk):
    evidencia = Evidencia.objects.select_related("resposta__avaliacao", "resposta__avaliacao__fornecedor").get(pk=pk, ativo=True)
    assert_can_access_avaliacao(user, evidencia.resposta.avaliacao)
    return evidencia


def build_avaliacao_context(user, avaliacao, cadastro_form=None):
    can_review = is_compras(user) or is_admin(user)
    categorias = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes__opcoes")
    respostas = {r.questao_id: r for r in avaliacao.respostas.prefetch_related("evidencias")}
    categorias_data = []
    total_fornecedor = respondidas_fornecedor = 0
    anexos_pendentes = criticos = 0

    for categoria in categorias:
        questoes = []
        cat_total = cat_respondidas = 0
        for questao in categoria.questoes.filter(ativa=True):
            if questao.uso_interno_compras and not can_review:
                continue
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
                editable = is_compras(user) or is_admin(user)
            else:
                editable = is_fornecedor(user) or is_admin(user)
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
        if not questoes:
            continue
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
    if is_compras(user) and not is_admin(user):
        for field in form.fields.values():
            field.disabled = True
    status_label = STATUS_LABELS.get(avaliacao.status, avaliacao.get_status_display())
    return {
        "avaliacao": avaliacao,
        "cadastro_form": form,
        "categorias_data": categorias_data,
        "can_review": can_review,
        "status_label": status_label,
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


def get_avaliacao_list_context(user):
    avaliacoes = list(Avaliacao.objects.visible_to_user(user).with_list_relations().order_by("-criado_em"))
    for avaliacao in avaliacoes:
        avaliacao.criticos = avaliacao.respostas.filter(questao__critica=True, resposta=Resposta.Valor.NAO).count()
        internas = avaliacao.respostas.filter(questao__uso_interno_compras=True, resposta__in=["0", "1", "2", "3", "4", "5"])
        notas = [int(r.resposta) for r in internas]
        avaliacao.nota_interna = round(sum(notas) / len(notas), 1) if notas else ""
        if avaliacao.status == Avaliacao.Status.RASCUNHO:
            avaliacao.display_status = "Convidado"
            avaliacao.status_class = "convidado"
        elif avaliacao.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}:
            avaliacao.display_status = "Em análise"
            avaliacao.status_class = "em-analise"
        elif avaliacao.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
            avaliacao.display_status = "Ajustes solicitados"
            avaliacao.status_class = "ajustes"
        elif avaliacao.qualificacao == "NAO_QUALIFICADO" or (avaliacao.pontuacao and avaliacao.pontuacao < 95):
            avaliacao.display_status = "Reprovado"
            avaliacao.status_class = "reprovado"
        else:
            avaliacao.display_status = "Aprovado"
            avaliacao.status_class = "aprovado"
    status_counts = {key: 0 for key, _label, _color in LIST_STATUS_ORDER}
    for avaliacao in avaliacoes:
        status_counts[avaliacao.status_class] = status_counts.get(avaliacao.status_class, 0) + 1
    total_status = len(avaliacoes)
    pie_start = 0
    pie_segments = []
    status_chart = []
    for key, label, color in LIST_STATUS_ORDER:
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
    score_histogram = [
        {
            **item,
            "height": round((item["count"] / max_score_count) * 100) if max_score_count else 0,
        }
        for item in score_counts
    ]
    return {
        "avaliacoes": avaliacoes,
        "total_fornecedores": len({avaliacao.fornecedor_id for avaliacao in avaliacoes}),
        "em_analise": sum(1 for a in avaliacoes if a.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}),
        "ajustes": sum(1 for a in avaliacoes if a.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}),
        "homologados": sum(1 for a in avaliacoes if getattr(a, "display_status", "") == "Aprovado"),
        "reprovados": sum(1 for a in avaliacoes if getattr(a, "display_status", "") == "Reprovado"),
        "can_show_compras_dashboard": is_compras(user) or is_admin(user),
        "status_chart": status_chart,
        "status_pie_style": f"conic-gradient({', '.join(pie_segments)})" if pie_segments else "conic-gradient(#e3e8f0 0deg 360deg)",
        "score_histogram": score_histogram,
    }


def process_avaliacao_submission(*, avaliacao, user, post_data, files, request=None):
    action = post_data.get("action")
    cadastro_form = FornecedorCadastroForm(post_data, instance=avaliacao.fornecedor, require_all=action != "salvar")
    if is_fornecedor(user) or is_admin(user):
        if cadastro_form.is_valid():
            cadastro_form.save()
        else:
            return {
                "success": False,
                "message": "Revise os dados cadastrais informados.",
                "cadastro_form": cadastro_form,
            }

    questoes = Questao.objects.filter(categoria__versao=avaliacao.questionario_versao, ativa=True).prefetch_related("opcoes")
    for questao in questoes:
        if questao.uso_interno_compras and not (is_compras(user) or is_admin(user)):
            continue
        if not questao.uso_interno_compras and not (is_fornecedor(user) or is_admin(user)):
            continue
        valor = resposta_valida(questao, post_data.get(f"q_{questao.id}", ""))
        file_obj = files.get(f"q_{questao.id}_file")
        if not valor and file_obj and questao.tipo == Questao.Tipo.ARQUIVO:
            valor = Resposta.Valor.SIM
        if not valor and not file_obj:
            continue
        resposta = salvar_resposta(
            avaliacao=avaliacao,
            questao=questao,
            usuario=user,
            resposta=valor,
            observacao=post_data.get(f"q_{questao.id}_obs", "")[:1000],
            justificativa="",
        )
        if file_obj:
            anexar_evidencia(resposta=resposta, file_obj=file_obj, usuario=user, request=request)

    if action == "enviar":
        enviar_avaliacao(avaliacao, user, request=request)
        message = "Avaliação enviada para análise."
    elif action == "iniciar_analise":
        iniciar_analise(avaliacao, user, request=request)
        message = "Análise iniciada."
    elif action == "homologar":
        if avaliacao.status == Avaliacao.Status.ENVIADA:
            iniciar_analise(avaliacao, user, request=request)
            avaliacao.refresh_from_db()
        finalizar_avaliacao(avaliacao, user, request=request)
        notificar_decisao_fornecedor(avaliacao, aprovado=True, usuario=user, request=request)
        message = "Fornecedor aprovado."
    elif action == "solicitar_ajustes":
        solicitar_ajustes(avaliacao, user, post_data, request=request)
        message = "Ajustes solicitados ao fornecedor."
    elif action == "reprovar":
        reprovar_avaliacao(avaliacao, user, post_data.get("parecer", "Fornecedor reprovado por Compras."), request=request)
        notificar_decisao_fornecedor(avaliacao, aprovado=False, usuario=user, request=request)
        message = "Fornecedor reprovado."
    else:
        message = "Alterações salvas."
    return {"success": True, "message": message, "cadastro_form": cadastro_form}


def notificar_decisao_fornecedor(avaliacao, *, aprovado, usuario, request=None):
    fornecedor = avaliacao.fornecedor
    assunto = f"Avaliação de fornecedor {'aprovada' if aprovado else 'reprovada'}"
    mensagem = (
        f"Olá, {fornecedor.razao_social}.\n\n"
        f"Sua avaliação de fornecedor foi {'aprovada' if aprovado else 'reprovada'} pela equipe de Compras.\n"
        "Acesse o portal para consultar os detalhes.\n"
    )
    tipo = Notificacao.Tipo.AVALIACAO_APROVADA if aprovado else Notificacao.Tipo.AVALIACAO_DEVOLVIDA
    for vinculo in fornecedor.usuarios.select_related("user").filter(ativo=True):
        Notificacao.objects.create(
            usuario=vinculo.user,
            tipo=tipo,
            titulo=assunto,
            mensagem=mensagem,
            url=f"/avaliacoes/{avaliacao.pk}/",
        )
    try:
        send_mail(
            subject=assunto,
            message=mensagem,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[fornecedor.email],
            fail_silently=False,
        )
        registrar_auditoria(usuario=usuario, acao="EMAIL_DECISAO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    except Exception as exc:
        registrar_auditoria(
            usuario=usuario,
            acao="EMAIL_DECISAO",
            objeto="Avaliacao",
            objeto_id=avaliacao.id,
            request=request,
            posterior={"erro": str(exc)[:500]},
            resultado="ERRO_EMAIL",
        )


def user_can_access_avaliacao(user, avaliacao):
    return user_can_access_fornecedor(user, avaliacao.fornecedor)


def assert_can_access_avaliacao(user, avaliacao):
    if not user_can_access_avaliacao(user, avaliacao):
        raise PermissionDenied("Você não tem permissão para acessar esta avaliação.")


def assert_transition(avaliacao, destino):
    permitidos = ALLOWED_TRANSITIONS.get(avaliacao.status, set())
    if destino not in permitidos:
        raise ValidationError(f"Transição inválida: {avaliacao.status} para {destino}.")


def registrar_historico(avaliacao, origem, destino, acao, usuario, comentario=""):
    HistoricoAvaliacao.objects.create(
        avaliacao=avaliacao,
        status_origem=origem,
        status_destino=destino,
        acao=acao,
        comentario=comentario,
        usuario=usuario,
    )


def validate_respostas_completas(avaliacao):
    erros = []
    questoes = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes")
    respostas = {r.questao_id: r for r in avaliacao.respostas.select_related("questao").prefetch_related("evidencias")}
    for categoria in questoes:
        for questao in categoria.questoes.filter(ativa=True):
            if questao.uso_interno_compras:
                continue
            resposta = respostas.get(questao.id)
            if questao.obrigatoria and (not resposta or not resposta.resposta):
                erros.append(f"Responda a pergunta: {questao.enunciado[:90]}")
                continue
            if not resposta:
                continue
            if questao.tipo == Questao.Tipo.ARQUIVO and not resposta.evidencias.filter(ativo=True).exists():
                erros.append(f"Anexe evidência para: {questao.enunciado[:90]}")
            if questao.exige_evidencia_se_sim and resposta.resposta == Resposta.Valor.SIM:
                if not resposta.evidencias.filter(ativo=True).exists():
                    erros.append(f"Anexe evidência para: {questao.enunciado[:90]}")
            if questao.exige_justificativa_se_nao and resposta.resposta == Resposta.Valor.NAO:
                if not resposta.justificativa.strip():
                    erros.append(f"Informe justificativa para: {questao.enunciado[:90]}")
    if erros:
        raise ValidationError(erros)


def calcular_pontuacao(avaliacao):
    total = Decimal("0.00")
    maximo = Decimal("0.00")
    respostas = avaliacao.respostas.select_related("questao", "questao__categoria")
    for resposta in respostas:
        questao = resposta.questao
        if questao.uso_interno_compras:
            continue
        peso = questao.peso * questao.categoria.peso
        if questao.tipo == Questao.Tipo.ESCALA_0_5:
            try:
                total += peso * (Decimal(resposta.resposta) / Decimal("5"))
            except Exception:
                pass
        elif resposta.resposta == Resposta.Valor.SIM:
            total += peso
        elif resposta.resposta == Resposta.Valor.NA:
            maximo -= peso
        maximo += peso
    if maximo == 0:
        return Decimal("0.00")
    return (total / maximo * Decimal("100.00")).quantize(Decimal("0.01"))


def definir_status_qualificacao(pontuacao):
    score = Decimal(pontuacao)
    regra_60 = Configuracao.get_value("QUALIFICACAO_SCORE_60", default=None)
    if score < 60:
        return Qualificacao.Status.NAO_QUALIFICADO
    if score == 60 and not regra_60:
        raise ValidationError("Regra de qualificação para exatamente 60 pontos está pendente de parametrização.")
    if score == 60:
        return regra_60.get("status", Qualificacao.Status.NAO_QUALIFICADO)
    if Decimal("61.00") <= score <= Decimal("84.00"):
        return Qualificacao.Status.RESSALVAS
    if score >= 85:
        return Qualificacao.Status.QUALIFICADO
    return Qualificacao.Status.INDEFINIDO


def vigencia_dias():
    valor = Configuracao.get_value("VIGENCIA_DIAS", default={"dias": 365})
    return int(valor.get("dias", 365))


@transaction.atomic
def salvar_resposta(*, avaliacao, questao, usuario, resposta, observacao="", justificativa=""):
    assert_can_access_avaliacao(usuario, avaliacao)
    status_fornecedor = {Avaliacao.Status.RASCUNHO, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}
    status_compras = {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}
    if questao.uso_interno_compras:
        if not (is_compras(usuario) or is_admin(usuario)) or avaliacao.status not in status_compras:
            raise ValidationError("Esta avaliação não permite alteração de respostas internas neste status.")
    elif avaliacao.status not in status_fornecedor:
        raise ValidationError("Esta avaliação não permite alteração de respostas neste status.")
    obj, created = Resposta.objects.get_or_create(
        avaliacao=avaliacao,
        questao=questao,
        defaults={"usuario": usuario},
    )
    obj.resposta = resposta
    obj.observacao = observacao
    obj.justificativa = justificativa
    obj.usuario = usuario
    obj.full_clean()
    if created:
        obj.save()
    else:
        obj.versao += 1
        obj.save(update_fields=["resposta", "observacao", "justificativa", "usuario", "versao", "atualizado_em"])
    return obj


def validar_upload(file_obj):
    allowed = Configuracao.get_value("UPLOAD_EXTENSOES_PERMITIDAS", default={"extensoes": ["pdf", "jpg", "jpeg", "png", "docx", "xlsx"]})
    max_bytes = Configuracao.get_value("UPLOAD_MAX_BYTES", default={"bytes": 10 * 1024 * 1024})
    extensoes = {e.lower().lstrip(".") for e in allowed.get("extensoes", [])}
    ext = Path(file_obj.name).suffix.lower().lstrip(".")
    if ext not in extensoes:
        raise ValidationError("Extensão de arquivo não permitida.")
    if file_obj.size > int(max_bytes.get("bytes", 10 * 1024 * 1024)):
        raise ValidationError("Arquivo acima do tamanho permitido.")
    content_type = getattr(file_obj, "content_type", "") or ""
    mime_ok = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    expected = mime_ok.get(ext)
    if expected and content_type and content_type != expected:
        raise ValidationError("Tipo MIME incompatível com a extensão enviada.")
    signatures = {
        "pdf": [b"%PDF"],
        "jpg": [b"\xff\xd8\xff"],
        "jpeg": [b"\xff\xd8\xff"],
        "png": [b"\x89PNG\r\n\x1a\n"],
        "docx": [b"PK\x03\x04"],
        "xlsx": [b"PK\x03\x04"],
    }
    position = file_obj.tell() if hasattr(file_obj, "tell") else 0
    head = file_obj.read(16)
    if hasattr(file_obj, "seek"):
        file_obj.seek(position)
    if ext in signatures and not any(head.startswith(sig) for sig in signatures[ext]):
        raise ValidationError("Assinatura real do arquivo incompatível com a extensão.")
    varrer_antivirus(file_obj)


def _antivirus_command():
    if settings.ANTIVIRUS_COMMAND:
        return shlex.split(settings.ANTIVIRUS_COMMAND)
    defender = Path("C:/ProgramData/Microsoft/Windows Defender/Platform")
    if defender.exists():
        candidates = sorted(defender.glob("*/MpCmdRun.exe"), reverse=True)
        if candidates:
            return [str(candidates[0]), "-Scan", "-ScanType", "3", "-File"]
    return []


def varrer_antivirus(file_obj):
    command = _antivirus_command()
    if not command:
        if settings.ANTIVIRUS_REQUIRED:
            raise ValidationError("Scanner antivírus não configurado para validar uploads.")
        return
    position = file_obj.tell() if hasattr(file_obj, "tell") else 0
    suffix = Path(file_obj.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in file_obj.chunks() if hasattr(file_obj, "chunks") else [file_obj.read()]:
            tmp.write(chunk)
        tmp_path = tmp.name
    if hasattr(file_obj, "seek"):
        file_obj.seek(position)
    try:
        result = subprocess.run([*command, tmp_path], capture_output=True, timeout=60, check=False)
        if result.returncode != 0:
            raise ValidationError("Arquivo reprovado ou não validado pelo antivírus.")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@transaction.atomic
def anexar_evidencia(*, resposta, file_obj, usuario, request=None):
    assert_can_access_avaliacao(usuario, resposta.avaliacao)
    validar_upload(file_obj)
    evidencia = Evidencia.objects.create(
        resposta=resposta,
        arquivo=file_obj,
        nome_original=Path(file_obj.name).name[:255],
        extensao=Path(file_obj.name).suffix.lower().lstrip("."),
        mime_type=getattr(file_obj, "content_type", "")[:120],
        tamanho=file_obj.size,
        enviado_por=usuario,
    )
    registrar_auditoria(usuario=usuario, acao="UPLOAD", objeto="Evidencia", objeto_id=evidencia.id, request=request)
    return evidencia


@transaction.atomic
def enviar_avaliacao(avaliacao, usuario, request=None):
    assert_can_access_avaliacao(usuario, avaliacao)
    if not is_fornecedor(usuario) and not is_admin(usuario):
        raise PermissionDenied("Somente fornecedor ou administrador pode enviar a avaliação.")
    destino = Avaliacao.Status.ENVIADA
    assert_transition(avaliacao, destino)
    validate_respostas_completas(avaliacao)
    origem = avaliacao.status
    avaliacao.status = destino
    avaliacao.enviada_em = timezone.now()
    avaliacao.save(update_fields=["status", "enviada_em", "atualizado_em"])
    registrar_historico(avaliacao, origem, destino, "ENVIO", usuario)
    registrar_auditoria(usuario=usuario, acao="ENVIO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao


@transaction.atomic
def iniciar_analise(avaliacao, usuario, request=None):
    if not (is_compras(usuario) or is_admin(usuario)):
        raise PermissionDenied("Somente Compras ou Administrador pode iniciar análise.")
    destino = Avaliacao.Status.EM_ANALISE
    assert_transition(avaliacao, destino)
    origem = avaliacao.status
    avaliacao.status = destino
    avaliacao.save(update_fields=["status", "atualizado_em"])
    registrar_historico(avaliacao, origem, destino, "INICIO_ANALISE", usuario)
    registrar_auditoria(usuario=usuario, acao="INICIO_ANALISE", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao


@transaction.atomic
def devolver_avaliacao(avaliacao, usuario, motivo, comentario, request=None):
    if not (is_compras(usuario) or is_admin(usuario)):
        raise PermissionDenied("Somente Compras ou Administrador pode devolver avaliação.")
    if not comentario.strip():
        raise ValidationError("Comentário de devolução é obrigatório.")
    destino = Avaliacao.Status.DEVOLVIDA
    assert_transition(avaliacao, destino)
    origem = avaliacao.status
    Devolucao.objects.create(avaliacao=avaliacao, motivo=motivo, comentario=comentario, usuario=usuario)
    avaliacao.status = destino
    avaliacao.save(update_fields=["status", "atualizado_em"])
    registrar_historico(avaliacao, origem, destino, "DEVOLUCAO", usuario, comentario)
    registrar_auditoria(usuario=usuario, acao="DEVOLUCAO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao


@transaction.atomic
def solicitar_ajustes(avaliacao, usuario, post_data, request=None):
    if not (is_compras(usuario) or is_admin(usuario)):
        raise PermissionDenied("Somente Compras ou Administrador pode solicitar ajustes.")
    if avaliacao.status not in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}:
        raise ValidationError("Esta avaliação não permite solicitação de ajustes neste status.")

    questoes = Questao.objects.filter(categoria__versao=avaliacao.questionario_versao, ativa=True, uso_interno_compras=False)
    ajustes = []
    for questao in questoes:
        if post_data.get(f"ajuste_q_{questao.id}") != "on":
            continue
        motivo = post_data.get(f"motivo_q_{questao.id}", "").strip()
        if not motivo:
            raise ValidationError(f"Informe o motivo do ajuste para: {questao.enunciado[:90]}")
        resposta, _created = Resposta.objects.get_or_create(
            avaliacao=avaliacao,
            questao=questao,
            defaults={"usuario": usuario},
        )
        resposta.observacao = f"Ajuste solicitado: {motivo}"
        resposta.usuario = usuario
        resposta.save(update_fields=["observacao", "usuario", "atualizado_em"])
        ajustes.append(f"{questao.enunciado[:120]}: {motivo}")

    if not ajustes:
        raise ValidationError("Selecione ao menos um campo para solicitar ajuste.")

    if avaliacao.status == Avaliacao.Status.ENVIADA:
        iniciar_analise(avaliacao, usuario, request=request)
        avaliacao.refresh_from_db()

    devolver_avaliacao(
        avaliacao,
        usuario,
        Devolucao.Motivo.INFORMACAO_INCOMPLETA,
        "\n".join(ajustes),
        request=request,
    )
    for vinculo in avaliacao.fornecedor.usuarios.select_related("user").filter(ativo=True):
        Notificacao.objects.create(
            usuario=vinculo.user,
            tipo=Notificacao.Tipo.AVALIACAO_DEVOLVIDA,
            titulo="Ajustes solicitados",
            mensagem="Compras solicitou ajustes em campos do checklist.",
            url=f"/avaliacoes/{avaliacao.pk}/",
        )
    return avaliacao


@transaction.atomic
def iniciar_correcao(avaliacao, usuario, request=None):
    assert_can_access_avaliacao(usuario, avaliacao)
    destino = Avaliacao.Status.EM_CORRECAO
    assert_transition(avaliacao, destino)
    origem = avaliacao.status
    avaliacao.status = destino
    avaliacao.save(update_fields=["status", "atualizado_em"])
    registrar_historico(avaliacao, origem, destino, "INICIO_CORRECAO", usuario)
    registrar_auditoria(usuario=usuario, acao="INICIO_CORRECAO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao


@transaction.atomic
def finalizar_avaliacao(avaliacao, usuario, request=None):
    if not (is_compras(usuario) or is_admin(usuario)):
        raise PermissionDenied("Somente Compras ou Administrador pode finalizar avaliação.")
    destino = Avaliacao.Status.FINALIZADA
    assert_transition(avaliacao, destino)
    validate_respostas_completas(avaliacao)
    pontuacao = calcular_pontuacao(avaliacao)
    status_qualificacao = definir_status_qualificacao(pontuacao)
    hoje = timezone.localdate()
    fim = hoje + timedelta(days=vigencia_dias())
    origem = avaliacao.status
    avaliacao.status = destino
    avaliacao.pontuacao = pontuacao
    avaliacao.qualificacao = status_qualificacao
    avaliacao.inicio_vigencia = hoje
    avaliacao.fim_vigencia = fim
    avaliacao.finalizada_em = timezone.now()
    avaliacao.save()
    Qualificacao.objects.update_or_create(
        avaliacao=avaliacao,
        defaults={
            "fornecedor": avaliacao.fornecedor,
            "status": status_qualificacao,
            "pontuacao": pontuacao,
            "inicio_vigencia": hoje,
            "fim_vigencia": fim,
            "definida_por": usuario,
        },
    )
    fornecedor = avaliacao.fornecedor
    fornecedor.qualificacao_atual = status_qualificacao
    fornecedor.pontuacao_atual = pontuacao
    fornecedor.validade_qualificacao = fim
    fornecedor.save(update_fields=["qualificacao_atual", "pontuacao_atual", "validade_qualificacao", "atualizado_em"])
    registrar_historico(avaliacao, origem, destino, "FINALIZACAO", usuario)
    registrar_auditoria(usuario=usuario, acao="FINALIZACAO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao


@transaction.atomic
def reprovar_avaliacao(avaliacao, usuario, comentario, request=None):
    if not (is_compras(usuario) or is_admin(usuario)):
        raise PermissionDenied("Somente Compras ou Administrador pode reprovar avaliação.")
    if avaliacao.status == Avaliacao.Status.ENVIADA:
        iniciar_analise(avaliacao, usuario, request=request)
        avaliacao.refresh_from_db()
    if avaliacao.status != Avaliacao.Status.EM_ANALISE:
        raise ValidationError("Esta avaliação não permite reprovação neste status.")
    if not comentario.strip():
        raise ValidationError("Parecer de reprovação é obrigatório.")

    origem = avaliacao.status
    avaliacao.status = Avaliacao.Status.FINALIZADA
    avaliacao.qualificacao = Qualificacao.Status.NAO_QUALIFICADO
    avaliacao.finalizada_em = timezone.now()
    avaliacao.save(update_fields=["status", "qualificacao", "finalizada_em", "atualizado_em"])
    Devolucao.objects.create(
        avaliacao=avaliacao,
        motivo=Devolucao.Motivo.RESPOSTA_INCORRETA,
        comentario=comentario,
        usuario=usuario,
    )
    registrar_historico(avaliacao, origem, Avaliacao.Status.FINALIZADA, "REPROVACAO", usuario, comentario)
    registrar_auditoria(usuario=usuario, acao="REPROVACAO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao
