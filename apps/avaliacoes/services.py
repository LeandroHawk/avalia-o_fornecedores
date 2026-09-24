from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.utils import is_admin, is_compras, is_fornecedor
from apps.auditoria.services import registrar_auditoria
from apps.core.models import Configuracao
from apps.fornecedores.security import user_can_access_fornecedor
from apps.qualificacoes.models import Qualificacao

from .models import Avaliacao, Devolucao, Evidencia, HistoricoAvaliacao, Resposta


ALLOWED_TRANSITIONS = {
    Avaliacao.Status.RASCUNHO: {Avaliacao.Status.ENVIADA},
    Avaliacao.Status.ENVIADA: {Avaliacao.Status.EM_ANALISE, Avaliacao.Status.DEVOLVIDA},
    Avaliacao.Status.EM_ANALISE: {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.FINALIZADA},
    Avaliacao.Status.DEVOLVIDA: {Avaliacao.Status.EM_CORRECAO},
    Avaliacao.Status.EM_CORRECAO: {Avaliacao.Status.ENVIADA},
}


def user_can_access_avaliacao(user, avaliacao):
    return user_can_access_fornecedor(user, avaliacao.fornecedor)


def assert_can_access_avaliacao(user, avaliacao):
    if not user_can_access_avaliacao(user, avaliacao):
        raise PermissionDenied("Voce nao tem permissao para acessar esta avaliacao.")


def assert_transition(avaliacao, destino):
    permitidos = ALLOWED_TRANSITIONS.get(avaliacao.status, set())
    if destino not in permitidos:
        raise ValidationError(f"Transicao invalida: {avaliacao.status} para {destino}.")


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
            resposta = respostas.get(questao.id)
            if questao.obrigatoria and (not resposta or not resposta.resposta):
                erros.append(f"Responda a pergunta: {questao.enunciado[:90]}")
                continue
            if not resposta:
                continue
            if questao.exige_evidencia_se_sim and resposta.resposta == Resposta.Valor.SIM:
                if not resposta.evidencias.filter(ativo=True).exists():
                    erros.append(f"Anexe evidencia para: {questao.enunciado[:90]}")
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
        peso = questao.peso * questao.categoria.peso
        if resposta.resposta == Resposta.Valor.SIM:
            total += peso
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
        raise ValidationError("Regra de qualificacao para exatamente 60 pontos esta pendente de parametrizacao.")
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
    if avaliacao.status not in {Avaliacao.Status.RASCUNHO, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
        raise ValidationError("Esta avaliacao nao permite alteracao de respostas neste status.")
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
        raise ValidationError("Extensao de arquivo nao permitida.")
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
        raise ValidationError("Tipo MIME incompativel com a extensao enviada.")


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
        raise PermissionDenied("Somente fornecedor ou administrador pode enviar a avaliacao.")
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
        raise PermissionDenied("Somente Compras ou Administrador pode iniciar analise.")
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
        raise PermissionDenied("Somente Compras ou Administrador pode devolver avaliacao.")
    if not comentario.strip():
        raise ValidationError("Comentario de devolucao e obrigatorio.")
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
        raise PermissionDenied("Somente Compras ou Administrador pode finalizar avaliacao.")
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
