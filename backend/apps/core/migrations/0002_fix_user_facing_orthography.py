from django.db import migrations


CATEGORY_NAMES = {
    "Seguranca": "Segurança",
    "Documentacao geral": "Documentação geral",
    "Gestao da qualidade": "Gestão da qualidade",
    "Gestao ambiental": "Gestão ambiental",
    "Gestao de saude e seguranca": "Gestão de saúde e segurança",
    "Compliance e governanca": "Compliance e governança",
    "LGPD e protecao de dados": "LGPD e proteção de dados",
}

QUESTIONNAIRE_NAMES = {
    "Questionario de Qualificacao CESARI": "Questionário de Qualificação CESARI",
    "Avaliacao de fornecedores CESARI": "Avaliação de fornecedores CESARI",
}

QUESTIONNAIRE_DESCRIPTIONS = {
    "Questionario baseado no layout Rev1.": "Questionário baseado no layout Rev1.",
}

VERSION_TITLES = {
    "Versao inicial 2026": "Versão inicial 2026",
}

QUESTION_TEXTS = {
    "A empresa possui certificacao de qualidade valida?": "A empresa possui certificação de qualidade válida?",
    "A empresa realiza treinamentos periodicos de seguranca?": "A empresa realiza treinamentos periódicos de segurança?",
    "A empresa possui documentos de seguranca atualizados?": "A empresa possui documentos de segurança atualizados?",
    "Inscricao municipal": "Inscrição municipal",
    "Inscricao estadual": "Inscrição estadual",
    "Contrato social e ultima alteracao, incluindo parte societaria": "Contrato social e última alteração, incluindo parte societária",
    "Certidoes negativas (INSS, FGTS, Receita Federal)": "Certidões negativas (INSS, FGTS, Receita Federal)",
    "Possui alvara de funcionamento vigente?": "Possui alvará de funcionamento vigente?",
    "Licencas ambientais obrigatorias (ex.: operacao, emissao)": "Licenças ambientais obrigatórias (ex.: operação, emissão)",
    "Outras certificacoes?": "Outras certificações?",
    "Possui certificacao ISO 9001 ou similar vigente?": "Possui certificação ISO 9001 ou similar vigente?",
    "Manual ou politica de qualidade?": "Manual ou política de qualidade?",
    "Possui avaliacao de satisfacao dos clientes?": "Possui avaliação de satisfação dos clientes?",
    "Sua empresa possui algum canal ou meio para receber e tratar reclamacoes de clientes ou parceiros?": "Sua empresa possui algum canal ou meio para receber e tratar reclamações de clientes ou parceiros?",
    "Possui certificacao ISO 14001 ou similar vigente?": "Possui certificação ISO 14001 ou similar vigente?",
    "A empresa possui Plano de Atendimento a Emergencia Ambiental?": "A empresa possui Plano de Atendimento a Emergência Ambiental?",
    "Existe algum programa de reciclagem de residuos, como 3Rs e coleta seletiva?": "Existe algum programa de reciclagem de resíduos, como 3Rs e coleta seletiva?",
    "A empresa atende aos requisitos da legislacao ambiental aplicavel a sua atividade e se mantem atualizada em relacao a mudancas?": "A empresa atende aos requisitos da legislação ambiental aplicável à sua atividade e se mantém atualizada em relação a mudanças?",
    "Possui certificacao ISO 45001 ou similar vigente?": "Possui certificação ISO 45001 ou similar vigente?",
    "A empresa disponibiliza os equipamentos de seguranca necessarios para que as atividades sejam realizadas adequadamente?": "A empresa disponibiliza os equipamentos de segurança necessários para que as atividades sejam realizadas adequadamente?",
    "A empresa disponibiliza procedimentos e instrucoes de saude e seguranca a serem atendidos durante a realizacao do servico?": "A empresa disponibiliza procedimentos e instruções de saúde e segurança a serem atendidos durante a realização do serviço?",
    "A empresa atende aos requisitos de legislacao de saude e seguranca ocupacional aplicavel e se mantem atualizada?": "A empresa atende aos requisitos de legislação de saúde e segurança ocupacional aplicável e se mantém atualizada?",
    "Ha politica de anticorrupcao implementada?": "Há política de anticorrupção implementada?",
    "Sua empresa disponibiliza canais de denuncia de irregularidades, abertos e amplamente divulgados a todos os empregados proprios e terceirizados?": "Sua empresa disponibiliza canais de denúncia de irregularidades, abertos e amplamente divulgados a todos os empregados próprios e terceirizados?",
    "Sua empresa esta em conformidade com a legislacao que proibe o trabalho de menores de 16 anos (exceto aprendizes a partir de 14 anos)?": "Sua empresa está em conformidade com a legislação que proíbe o trabalho de menores de 16 anos (exceto aprendizes a partir de 14 anos)?",
    "Sua empresa esta em conformidade com a legislacao que proibe trabalho analogo ao escravo ou forcado, sem autuacoes nos ultimos 3 anos?": "Sua empresa está em conformidade com a legislação que proíbe trabalho análogo ao escravo ou forçado, sem autuações nos últimos 3 anos?",
    "Sua empresa cumpre a legislacao trabalhista vigente, incluindo controle de jornada e remuneracao dos colaboradores?": "Sua empresa cumpre a legislação trabalhista vigente, incluindo controle de jornada e remuneração dos colaboradores?",
    "Ha historico de inadimplencia ou falencias?": "Há histórico de inadimplência ou falências?",
    "Possui politicas de protecao de dados?": "Possui políticas de proteção de dados?",
    "Qualidade do produto ou servico": "Qualidade do produto ou serviço",
    "Atendimento pos-vendas": "Atendimento pós-vendas",
    "Competitividade de precos": "Competitividade de preços",
}

QUESTION_HELP = {
    "Resposta 'Sim' dispensa as questoes seguintes desta secao.": "Resposta 'Sim' dispensa as questões seguintes desta seção.",
    "Anexe o manual ou a clausula contratual.": "Anexe o manual ou a cláusula contratual.",
}

OPTION_VALUES = {
    "Ate R$ 1M": "Até R$ 1M",
}

SUPPLIER_TEXTS = {
    "Fornecedor Demonstracao Ltda": "Fornecedor Demonstração Ltda",
    "Responsavel Demo": "Responsável Demo",
    "Metalurgica Horizonte Ltda": "Metalúrgica Horizonte Ltda",
    "Metalurgica": "Metalúrgica",
    "TransLog Solucoes em Transporte": "TransLog Soluções em Transporte",
    "Quimica Aurora S.A.": "Química Aurora S.A.",
    "Quimica": "Química",
    "Cubatao": "Cubatão",
    "Responsavel Comercial": "Responsável Comercial",
}

CONFIG_DESCRIPTIONS = {
    "Duracao da vigencia da qualificacao em dias.": "Duração da vigência da qualificação em dias.",
}


def replace_exact(model, field_name, replacements):
    for old, new in replacements.items():
        model.objects.filter(**{field_name: old}).update(**{field_name: new})


def fix_user_facing_orthography(apps, schema_editor):
    Categoria = apps.get_model("questionarios", "Categoria")
    Questao = apps.get_model("questionarios", "Questao")
    OpcaoResposta = apps.get_model("questionarios", "OpcaoResposta")
    Questionario = apps.get_model("questionarios", "Questionario")
    QuestionarioVersao = apps.get_model("questionarios", "QuestionarioVersao")
    Fornecedor = apps.get_model("fornecedores", "Fornecedor")
    Configuracao = apps.get_model("core", "Configuracao")

    replace_exact(Categoria, "nome", CATEGORY_NAMES)
    replace_exact(Questionario, "nome", QUESTIONNAIRE_NAMES)
    replace_exact(Questionario, "descricao", QUESTIONNAIRE_DESCRIPTIONS)
    replace_exact(QuestionarioVersao, "titulo", VERSION_TITLES)
    replace_exact(Questao, "enunciado", QUESTION_TEXTS)
    replace_exact(Questao, "ajuda", QUESTION_HELP)
    replace_exact(OpcaoResposta, "rotulo", OPTION_VALUES)
    replace_exact(OpcaoResposta, "valor", OPTION_VALUES)
    replace_exact(Configuracao, "descricao", CONFIG_DESCRIPTIONS)

    for field_name in ("razao_social", "nome_fantasia", "cidade", "responsavel"):
        replace_exact(Fornecedor, field_name, SUPPLIER_TEXTS)


class Migration(migrations.Migration):

    dependencies = [
        ("avaliacoes", "0002_alter_avaliacao_status_alter_devolucao_motivo_and_more"),
        ("fornecedores", "0002_fornecedor_cargo_responsavel_fornecedor_cidade_and_more"),
        ("notificacoes", "0002_alter_notificacao_tipo"),
        ("qualificacoes", "0002_alter_qualificacao_status"),
        ("questionarios", "0003_alter_questao_tipo"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fix_user_facing_orthography, migrations.RunPython.noop),
    ]
