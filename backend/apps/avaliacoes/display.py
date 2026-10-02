from .models import Avaliacao


def get_decisao_compras(avaliacao):
    if avaliacao.decisao_compras:
        return avaliacao.decisao_compras
    if avaliacao.status != Avaliacao.Status.FINALIZADA:
        return ""

    historico = getattr(avaliacao, "historico", None)
    if historico is not None:
        if historico.filter(acao="REPROVACAO").exists():
            return Avaliacao.DecisaoCompras.REPROVADA
        if historico.filter(acao="FINALIZACAO").exists():
            return Avaliacao.DecisaoCompras.APROVADA

    if avaliacao.qualificacao == "NAO_QUALIFICADO":
        return Avaliacao.DecisaoCompras.REPROVADA
    return Avaliacao.DecisaoCompras.APROVADA


def get_status_label(avaliacao):
    if avaliacao.status == Avaliacao.Status.FINALIZADA:
        return "Reprovado" if get_decisao_compras(avaliacao) == Avaliacao.DecisaoCompras.REPROVADA else "Aprovado"
    return {
        Avaliacao.Status.RASCUNHO: "Rascunho",
        Avaliacao.Status.ENVIADA: "Em análise",
        Avaliacao.Status.EM_ANALISE: "Em análise",
        Avaliacao.Status.DEVOLVIDA: "Ajustes solicitados",
        Avaliacao.Status.EM_CORRECAO: "Ajustes solicitados",
    }.get(avaliacao.status, avaliacao.get_status_display())


def get_status_class(avaliacao):
    if avaliacao.status == Avaliacao.Status.RASCUNHO:
        return "convidado"
    if avaliacao.status in {Avaliacao.Status.ENVIADA, Avaliacao.Status.EM_ANALISE}:
        return "em-analise"
    if avaliacao.status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
        return "ajustes"
    if get_decisao_compras(avaliacao) == Avaliacao.DecisaoCompras.REPROVADA:
        return "reprovado"
    return "aprovado"
