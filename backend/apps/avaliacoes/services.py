from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import shlex
import subprocess
import tempfile
import unicodedata

from django.core.exceptions import PermissionDenied, ValidationError
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts.utils import is_admin, is_compras, is_fornecedor
from backend.apps.auditoria.models import Auditoria
from backend.apps.auditoria.services import registrar_auditoria
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.models import Fornecedor, FornecedorUsuario
from backend.apps.fornecedores.security import user_can_access_fornecedor
from backend.apps.notificacoes.models import Notificacao
from backend.apps.questionarios.models import Categoria, OpcaoResposta, Questao, Questionario, QuestionarioVersao
from backend.apps.qualificacoes.models import Qualificacao

from .display import get_status_class, get_status_label
from .forms import FornecedorCadastroForm
from .models import AjusteQuestao, Avaliacao, Devolucao, Evidencia, HistoricoAvaliacao, Resposta


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


QUESTOES_COM_EVIDENCIA_SE_SIM = {
    "inscricao municipal",
    "inscricao estadual",
    "certidoes negativas (inss, fgts, receita federal)",
    "possui alvara de funcionamento vigente?",
    "possui avcb?",
    "licencas ambientais obrigatorias (ex.: operacao, emissao)",
    "outras certificacoes?",
}

QUESTAO_OUTRAS_CERTIFICACOES = "outras certificacoes?"
MAX_ARQUIVOS_OUTRAS_CERTIFICACOES = 5


def _normalizar_texto(texto):
    sem_acentos = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acentos.casefold().split())


def questao_exige_evidencia_se_sim(tipo, enunciado):
    return tipo == Questao.Tipo.ARQUIVO or _normalizar_texto(enunciado) in QUESTOES_COM_EVIDENCIA_SE_SIM


def max_arquivos_questao(questao):
    if _normalizar_texto(questao.enunciado) == QUESTAO_OUTRAS_CERTIFICACOES:
        return MAX_ARQUIVOS_OUTRAS_CERTIFICACOES
    return 1


def questao_dispensa_subsequentes(questao):
    ajuda = (questao.ajuda or "").lower()
    if "dispensa as questões subsequentes" in ajuda:
        return True

    enunciado = (questao.enunciado or "").lower()
    enunciado_compacto = "".join(char for char in enunciado if char.isalnum())
    certificacoes_dispensa = {"iso9001", "iso14001", "iso45001"}
    return (
        "certifica" in enunciado
        and "vigente" in enunciado
        and any(certificacao in enunciado_compacto for certificacao in certificacoes_dispensa)
    )


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


def _arquivos_enviados(files, field_name):
    if hasattr(files, "getlist"):
        return [file_obj for file_obj in files.getlist(field_name) if file_obj]
    file_obj = files.get(field_name)
    return [file_obj] if file_obj else []


def get_evidencia_for_download(user, pk):
    evidencia = Evidencia.objects.select_related("resposta__avaliacao", "resposta__avaliacao__fornecedor").get(pk=pk, ativo=True)
    assert_can_access_avaliacao(user, evidencia.resposta.avaliacao)
    return evidencia


def _placeholder_cnpj(user):
    base = getattr(user, "id", 0) or 0
    for offset in range(100):
        cnpj = f"99.{base:03d}.{(base * 137 + offset) % 1000:03d}/0001-{(base + offset) % 100:02d}"
        if not Fornecedor.objects.filter(cnpj=cnpj).exists():
            return cnpj
    return f"99.999.{base % 1000:03d}/0001-{base % 100:02d}"


def _get_or_create_fornecedor_vinculo(user):
    vinculo = getattr(user, "fornecedor_vinculo", None)
    if vinculo and vinculo.ativo:
        return vinculo

    email = (getattr(user, "email", "") or "").strip()
    fornecedor = Fornecedor.objects.filter(email__iexact=email).first() if email else None
    if not fornecedor:
        nome = (getattr(user, "first_name", "") or getattr(user, "username", "") or "Fornecedor").strip()
        fornecedor = Fornecedor.objects.create(
            razao_social=nome,
            nome_fantasia=nome,
            cnpj=_placeholder_cnpj(user),
            email=email or f"{getattr(user, 'username', 'fornecedor')}@fornecedor.local",
            responsavel=nome,
            status=Fornecedor.Status.ATIVO,
        )
    vinculo, _created = FornecedorUsuario.objects.update_or_create(
        user=user,
        defaults={"fornecedor": fornecedor, "principal": True, "ativo": True},
    )
    return vinculo


def _get_or_create_default_questionario_versao():
    versoes = list(
        QuestionarioVersao.objects.filter(publicado=True, ativo=True, questionario__ativo=True)
        .select_related("questionario")
        .prefetch_related("categorias__questoes")
        .order_by("-questionario__criado_em", "-numero")
    )
    if versoes:
        def active_question_count(versao):
            return sum(categoria.questoes.filter(ativa=True).count() for categoria in versao.categorias.all())

        cesari_versions = [
            versao
            for versao in versoes
            if "cesari" in _normalizar_texto(versao.questionario.nome) and active_question_count(versao) > 1
        ]
        return max(cesari_versions or versoes, key=lambda versao: (active_question_count(versao), versao.numero, versao.criado_em))

    from backend.apps.core.management.commands.seed_demo import SECTIONS

    questionario, _created = Questionario.objects.update_or_create(
        nome="Avaliação de fornecedores CESARI",
        defaults={
            "descricao": "Questionário baseado no layout Rev1.",
            "ativo": True,
        },
    )
    versao, _created = QuestionarioVersao.objects.update_or_create(
        questionario=questionario,
        numero=1,
        defaults={"titulo": "Layout Rev1", "publicado": True, "ativo": True},
    )
    if versao.categorias.exists():
        return versao

    for ordem_cat, (nome, perguntas) in enumerate(SECTIONS, start=1):
        categoria = Categoria.objects.create(versao=versao, nome=nome, ordem=ordem_cat, peso=Decimal("1.00"), ativa=True)
        uso_interno = nome == "Uso interno (Compras)"
        for ordem, (texto, tipo, peso, critica, ajuda) in enumerate(perguntas, start=1):
            questao = Questao.objects.create(
                categoria=categoria,
                ordem=ordem,
                enunciado=texto,
                tipo=tipo,
                peso=Decimal(peso),
                critica=critica,
                uso_interno_compras=uso_interno,
                ajuda=ajuda,
                obrigatoria=True,
                exige_evidencia_se_sim=questao_exige_evidencia_se_sim(tipo, texto),
                exige_justificativa_se_nao=False,
                ativa=True,
            )
            if texto == "Volume de faturamento anual":
                for idx, option in enumerate(["Até R$ 1M", "R$ 1M a R$ 5M", "R$ 5M a R$ 20M", "Acima de R$ 20M"], start=1):
                    OpcaoResposta.objects.create(
                        questao=questao,
                        valor=option,
                        rotulo=option,
                        pontuacao=Decimal(idx),
                        ordem=idx,
                        ativa=True,
                    )
    return versao


@transaction.atomic
def get_or_create_fornecedor_avaliacao(user):
    if not is_fornecedor(user):
        return None
    vinculo = _get_or_create_fornecedor_vinculo(user)
    versao = _get_or_create_default_questionario_versao()

    avaliacao = Avaliacao.objects.visible_to_user(user).with_detail_relations().order_by("-criado_em").first()
    if avaliacao:
        if avaliacao.status == Avaliacao.Status.RASCUNHO and avaliacao.questionario_versao_id != versao.id and not avaliacao.respostas.exists():
            avaliacao.questionario_versao = versao
            avaliacao.save(update_fields=["questionario_versao", "atualizado_em"])
        return avaliacao

    return Avaliacao.objects.create(
        fornecedor=vinculo.fornecedor,
        questionario_versao=versao,
        periodo=str(timezone.localdate().year),
        responsavel=user,
        status=Avaliacao.Status.RASCUNHO,
    )


def build_avaliacao_context(user, avaliacao, cadastro_form=None):
    can_review = is_compras(user) or is_admin(user)
    status_fornecedor_editavel = {Avaliacao.Status.RASCUNHO, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}
    status_compras_editavel = {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}
    categorias = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes__opcoes")
    respostas = {r.questao_id: r for r in avaliacao.respostas.prefetch_related("evidencias")}
    ajustes_pendentes = {
        ajuste.questao_id: ajuste
        for ajuste in avaliacao.ajustes_questoes.select_related("questao").filter(status=AjusteQuestao.Status.PENDENTE)
    }
    ajustes_respondidos = {}
    if can_review and avaliacao.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}:
        ajustes_respondidos = {
            ajuste.questao_id: ajuste
            for ajuste in avaliacao.ajustes_questoes.select_related("questao").filter(status=AjusteQuestao.Status.RESPONDIDO)
        }
    show_only_adjustments_to_supplier = (
        is_fornecedor(user)
        and not can_review
        and avaliacao.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}
        and bool(ajustes_pendentes)
    )
    categorias_data = []
    total_fornecedor = respondidas_fornecedor = 0
    anexos_pendentes = criticos = 0

    for categoria in categorias:
        questoes = []
        cat_total = cat_respondidas = 0
        dispensa_ativa = False
        for questao in categoria.questoes.filter(ativa=True):
            if questao.uso_interno_compras and not can_review:
                continue
            ajuste_pendente = ajustes_pendentes.get(questao.id)
            ajuste_respondido = ajustes_respondidos.get(questao.id)
            ajuste_em_destaque = ajuste_pendente or ajuste_respondido
            if show_only_adjustments_to_supplier and not ajuste_pendente:
                continue
            resposta = respostas.get(questao.id)
            dispensada = bool(dispensa_ativa and not questao.uso_interno_compras)
            evidencia_ok = bool(resposta and resposta.evidencias.filter(ativo=True).exists())
            respondida = bool(resposta and resposta.resposta)
            if questao.tipo == Questao.Tipo.ARQUIVO:
                respondida = evidencia_ok
            missing_file = False
            if not dispensada:
                missing_file = bool(
                    questao.obrigatoria
                    and (
                        questao.tipo == Questao.Tipo.ARQUIVO
                        or (questao.exige_evidencia_se_sim and resposta and resposta.resposta == Resposta.Valor.SIM)
                    )
                    and not evidencia_ok
                )
            if questao.uso_interno_compras:
                base_editable = (is_compras(user) or is_admin(user)) and avaliacao.status in status_compras_editavel
            else:
                base_editable = (is_fornecedor(user) or is_admin(user)) and avaliacao.status in status_fornecedor_editavel
                if not dispensada:
                    total_fornecedor += 1
                    if respondida:
                        respondidas_fornecedor += 1
            if not dispensada:
                cat_total += 1
                if respondida:
                    cat_respondidas += 1
            if missing_file:
                anexos_pendentes += 1
            if not dispensada and questao.critica and resposta and resposta.resposta == Resposta.Valor.NAO:
                criticos += 1
            is_dispensa_trigger = questao_dispensa_subsequentes(questao)
            questoes.append(
                {
                    "questao": questao,
                    "resposta": resposta,
                    "ajuste_pendente": ajuste_pendente,
                    "ajuste_respondido": ajuste_respondido,
                    "ajuste_em_destaque": ajuste_em_destaque,
                    "respondida": respondida,
                    "missing_file": missing_file,
                    "editable": base_editable and not dispensada,
                    "base_editable": base_editable,
                    "opcoes": questao.opcoes.filter(ativa=True),
                    "dispensada": dispensada,
                    "dispensa_trigger": is_dispensa_trigger,
                    "max_arquivos": max_arquivos_questao(questao),
                }
            )
            if is_dispensa_trigger and resposta and resposta.resposta == Resposta.Valor.SIM:
                dispensa_ativa = True
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
    pontuacao_fornecedor = avaliacao.pontuacao
    if pontuacao_fornecedor is None and respondidas_fornecedor:
        pontuacao_fornecedor = calcular_pontuacao(avaliacao)
    respostas_internas_status = get_respostas_internas_status(avaliacao) if can_review else {"total": 0, "respondidas": 0, "pendentes": 0}
    form = cadastro_form or FornecedorCadastroForm(instance=avaliacao.fornecedor)
    can_edit_supplier_answers = (is_fornecedor(user) or is_admin(user)) and avaliacao.status in status_fornecedor_editavel
    can_send_adjustments = can_review and avaliacao.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}
    if (is_compras(user) and not is_admin(user)) or (is_fornecedor(user) and not can_edit_supplier_answers):
        for field in form.fields.values():
            field.disabled = True
    status_label = get_status_label(avaliacao)
    return {
        "avaliacao": avaliacao,
        "cadastro_form": form,
        "categorias_data": categorias_data,
        "can_review": can_review,
        "can_edit_supplier_answers": can_edit_supplier_answers,
        "can_send_adjustments": can_send_adjustments,
        "show_only_adjustments_to_supplier": show_only_adjustments_to_supplier,
        "status_label": status_label,
        "dados_total": dados_total,
        "dados_preenchidos": dados_preenchidos,
        "progress_total": progress_total,
        "progress_done": progress_done,
        "progresso": progresso,
        "pontuacao_fornecedor": pontuacao_fornecedor,
        "tem_pontuacao_fornecedor": pontuacao_fornecedor is not None,
        "apto": progresso >= 85 and criticos == 0,
        "pendencias": max(progress_total - progress_done, 0),
        "anexos_pendentes": anexos_pendentes,
        "criticos": criticos,
        "respostas_internas_total": respostas_internas_status["total"],
        "respostas_internas_respondidas": respostas_internas_status["respondidas"],
        "respostas_internas_pendentes": respostas_internas_status["pendentes"],
        "compras_pode_decidir": respostas_internas_status["pendentes"] == 0,
        "timeline_items": build_timeline_context(avaliacao) if can_review else [],
        "auditoria_logs": build_auditoria_context(avaliacao) if can_review else [],
    }


def get_avaliacao_list_context(user):
    avaliacoes = list(Avaliacao.objects.visible_to_user(user).with_list_relations().order_by("-criado_em"))
    for avaliacao in avaliacoes:
        avaliacao.criticos = avaliacao.respostas.filter(questao__critica=True, resposta=Resposta.Valor.NAO).count()
        internas = avaliacao.respostas.filter(questao__uso_interno_compras=True, resposta__in=["0", "1", "2", "3", "4", "5"])
        notas = [int(r.resposta) for r in internas]
        avaliacao.nota_interna = round(sum(notas) / len(notas), 1) if notas else ""
        avaliacao.pontuacao_exibida = avaliacao.pontuacao
        if avaliacao.pontuacao_exibida is None and avaliacao.respostas.filter(questao__uso_interno_compras=False).exclude(resposta="").exists():
            avaliacao.pontuacao_exibida = calcular_pontuacao(avaliacao)
        avaliacao.tem_pontuacao_exibida = avaliacao.pontuacao_exibida is not None
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
        avaliacao.display_status = "Convidado" if avaliacao.status == Avaliacao.Status.RASCUNHO else get_status_label(avaliacao)
        avaliacao.status_class = get_status_class(avaliacao)
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
            count = sum(1 for avaliacao in avaliacoes if not avaliacao.tem_pontuacao_exibida)
        else:
            count = sum(
                1
                for avaliacao in avaliacoes
                if avaliacao.tem_pontuacao_exibida and start <= Decimal(avaliacao.pontuacao_exibida) <= end
            )
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

    respostas_existentes = {r.questao_id: r for r in avaliacao.respostas.select_related("questao")}
    questoes = (
        Questao.objects.filter(categoria__versao=avaliacao.questionario_versao, ativa=True)
        .select_related("categoria")
        .prefetch_related("opcoes")
    )
    categorias_dispensadas = set()
    for questao in questoes:
        if questao.uso_interno_compras and not (is_compras(user) or is_admin(user)):
            continue
        if not questao.uso_interno_compras and not (is_fornecedor(user) or is_admin(user)):
            continue
        if not questao.uso_interno_compras and questao.categoria_id in categorias_dispensadas:
            continue
        valor = resposta_valida(questao, post_data.get(f"q_{questao.id}", ""))
        if not valor:
            resposta_existente = respostas_existentes.get(questao.id)
            valor_para_regra = resposta_existente.resposta if resposta_existente else ""
        else:
            valor_para_regra = valor
        arquivos = _arquivos_enviados(files, f"q_{questao.id}_file")
        if not valor and arquivos and questao.tipo == Questao.Tipo.ARQUIVO:
            valor = Resposta.Valor.SIM
        if questao.tipo != Questao.Tipo.ARQUIVO and valor != Resposta.Valor.SIM:
            arquivos = []
        if not valor and not arquivos:
            if questao_dispensa_subsequentes(questao) and valor_para_regra == Resposta.Valor.SIM:
                categorias_dispensadas.add(questao.categoria_id)
            continue
        max_arquivos = max_arquivos_questao(questao)
        resposta_existente = respostas_existentes.get(questao.id)
        evidencias_existentes = resposta_existente.evidencias.filter(ativo=True).count() if resposta_existente else 0
        if len(arquivos) > max_arquivos or (max_arquivos > 1 and evidencias_existentes + len(arquivos) > max_arquivos):
            raise ValidationError(f"Anexe no máximo {max_arquivos} arquivo(s) para: {questao.enunciado[:90]}")
        resposta = salvar_resposta(
            avaliacao=avaliacao,
            questao=questao,
            usuario=user,
            resposta=valor,
            observacao=post_data.get(f"q_{questao.id}_obs", "")[:1000],
            justificativa="",
        )
        for file_obj in arquivos:
            anexar_evidencia(resposta=resposta, file_obj=file_obj, usuario=user, request=request)
        if questao_dispensa_subsequentes(questao) and resposta.resposta == Resposta.Valor.SIM:
            categorias_dispensadas.add(questao.categoria_id)

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


TIMELINE_LABELS = {
    "ENVIO": "Avaliação enviada",
    "INICIO_ANALISE": "Análise iniciada",
    "DEVOLUCAO": "Ajustes enviados ao fornecedor",
    "INICIO_CORRECAO": "Correção iniciada pelo fornecedor",
    "FINALIZACAO": "Avaliação aprovada",
    "REPROVACAO": "Avaliação reprovada",
}


def _format_user(user):
    if not user:
        return "Sistema"
    full_name = user.get_full_name()
    return full_name or user.get_username()


def build_timeline_context(avaliacao):
    historicos = avaliacao.historico.select_related("usuario").order_by("criado_em")
    return [
        {
            "titulo": TIMELINE_LABELS.get(item.acao, item.acao.replace("_", " ").title()),
            "acao": item.acao,
            "usuario": _format_user(item.usuario),
            "quando": item.criado_em,
            "comentario": item.comentario,
        }
        for item in historicos
    ]


def build_auditoria_context(avaliacao):
    logs = Auditoria.objects.filter(objeto="Avaliacao", objeto_id=str(avaliacao.id)).select_related("usuario").order_by("-criado_em")[:12]
    return [
        {
            "acao": log.acao,
            "usuario": _format_user(log.usuario),
            "quando": log.criado_em,
            "resultado": log.resultado,
        }
        for log in logs
    ]


def validate_respostas_completas(avaliacao):
    erros = []
    questoes = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes")
    respostas = {r.questao_id: r for r in avaliacao.respostas.select_related("questao").prefetch_related("evidencias")}
    for categoria in questoes:
        dispensa_ativa = False
        for questao in categoria.questoes.filter(ativa=True):
            if questao.uso_interno_compras:
                continue
            resposta = respostas.get(questao.id)
            if dispensa_ativa:
                continue
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
            if questao_dispensa_subsequentes(questao) and resposta.resposta == Resposta.Valor.SIM:
                dispensa_ativa = True
    if erros:
        raise ValidationError(erros)


def get_respostas_internas_status(avaliacao):
    questoes = Questao.objects.filter(
        categoria__versao=avaliacao.questionario_versao,
        ativa=True,
        uso_interno_compras=True,
    )
    total = questoes.count()
    respondidas = avaliacao.respostas.filter(
        questao__in=questoes,
        resposta__in={"0", "1", "2", "3", "4", "5"},
    ).count()
    return {"total": total, "respondidas": respondidas, "pendentes": max(total - respondidas, 0)}


def validate_respostas_internas_completas(avaliacao):
    status = get_respostas_internas_status(avaliacao)
    if status["pendentes"]:
        raise ValidationError(
            f"Preencha a seção Uso interno (Compras) antes de aprovar ou reprovar. "
            f"Faltam {status['pendentes']} de {status['total']} resposta(s)."
        )


def calcular_pontuacao(avaliacao):
    total = Decimal("0.00")
    maximo = Decimal("0.00")
    respostas = {r.questao_id: r for r in avaliacao.respostas.select_related("questao", "questao__categoria")}
    categorias = avaliacao.questionario_versao.categorias.filter(ativa=True).prefetch_related("questoes")
    for categoria in categorias:
        dispensa_ativa = False
        for questao in categoria.questoes.filter(ativa=True):
            if questao.uso_interno_compras or dispensa_ativa:
                continue
            resposta = respostas.get(questao.id)
            if not resposta:
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
            if questao_dispensa_subsequentes(questao) and resposta.resposta == Resposta.Valor.SIM:
                dispensa_ativa = True
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
    max_bytes = Configuracao.get_value("UPLOAD_MAX_BYTES", default={"bytes": 10 * 1024 * 1024})
    ext = Path(file_obj.name).suffix.lower().lstrip(".")
    if ext != "pdf":
        raise ValidationError("Apenas arquivos PDF são permitidos.")
    if file_obj.size > int(max_bytes.get("bytes", 10 * 1024 * 1024)):
        raise ValidationError("Arquivo acima do tamanho permitido.")
    content_type = getattr(file_obj, "content_type", "") or ""
    if content_type and content_type != "application/pdf":
        raise ValidationError("Apenas arquivos PDF são permitidos.")
    position = file_obj.tell() if hasattr(file_obj, "tell") else 0
    head = file_obj.read(16)
    if hasattr(file_obj, "seek"):
        file_obj.seek(position)
    if not head.startswith(b"%PDF"):
        raise ValidationError("O arquivo enviado não parece ser um PDF válido.")
    varrer_antivirus(file_obj)


def _antivirus_command():
    if settings.ANTIVIRUS_COMMAND:
        return shlex.split(settings.ANTIVIRUS_COMMAND)
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
    if origem in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
        avaliacao.ajustes_questoes.filter(status=AjusteQuestao.Status.PENDENTE).update(status=AjusteQuestao.Status.RESPONDIDO)
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
        AjusteQuestao.objects.update_or_create(
            avaliacao=avaliacao,
            questao=questao,
            defaults={
                "motivo": motivo,
                "status": AjusteQuestao.Status.PENDENTE,
                "solicitado_por": usuario,
            },
        )
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
    validate_respostas_internas_completas(avaliacao)
    pontuacao = calcular_pontuacao(avaliacao)
    status_qualificacao = definir_status_qualificacao(pontuacao)
    hoje = timezone.localdate()
    fim = hoje + timedelta(days=vigencia_dias())
    origem = avaliacao.status
    avaliacao.status = destino
    avaliacao.decisao_compras = Avaliacao.DecisaoCompras.APROVADA
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
    validate_respostas_internas_completas(avaliacao)
    if not comentario.strip():
        raise ValidationError("Parecer de reprovação é obrigatório.")

    origem = avaliacao.status
    avaliacao.status = Avaliacao.Status.FINALIZADA
    avaliacao.decisao_compras = Avaliacao.DecisaoCompras.REPROVADA
    avaliacao.qualificacao = Qualificacao.Status.NAO_QUALIFICADO
    avaliacao.finalizada_em = timezone.now()
    avaliacao.save(update_fields=["status", "decisao_compras", "qualificacao", "finalizada_em", "atualizado_em"])
    Devolucao.objects.create(
        avaliacao=avaliacao,
        motivo=Devolucao.Motivo.RESPOSTA_INCORRETA,
        comentario=comentario,
        usuario=usuario,
    )
    registrar_historico(avaliacao, origem, Avaliacao.Status.FINALIZADA, "REPROVACAO", usuario, comentario)
    registrar_auditoria(usuario=usuario, acao="REPROVACAO", objeto="Avaliacao", objeto_id=avaliacao.id, request=request)
    return avaliacao
