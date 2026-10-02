import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts.models import UserProfile
from backend.apps.avaliacoes.models import Avaliacao, Devolucao, Resposta
from backend.apps.avaliacoes.services import questao_exige_evidencia_se_sim
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.models import Fornecedor, FornecedorUsuario
from backend.apps.qualificacoes.models import Qualificacao
from backend.apps.questionarios.models import Categoria, OpcaoResposta, Questao, Questionario, QuestionarioVersao


SECTIONS = [
    ("Documentação geral", [
        ("CNPJ", "ARQUIVO", "0", False, ""),
        ("Inscrição municipal", "SIM_NAO", "0", False, ""),
        ("Inscrição estadual", "SIM_NAO", "0", False, ""),
        ("Contrato social e última alteração, incluindo parte societária", "ARQUIVO", "4", True, ""),
        ("Certidões negativas (INSS, FGTS, Receita Federal)", "SIM_NAO", "5", True, ""),
        ("Possui alvará de funcionamento vigente?", "SIM_NAO", "3", True, ""),
        ("Possui AVCB?", "SIM_NAO", "4", True, ""),
        ("Licenças ambientais obrigatórias (ex.: operação, emissão)", "SIM_NAO", "4", True, ""),
        ("Outras certificações?", "SIM_NAO", "2", False, ""),
    ]),
    ("Gestão da qualidade", [
        ("Possui certificação ISO 9001 ou similar vigente?", "SIM_NAO", "5", False, "Resposta 'Sim' dispensa as questões seguintes desta seção."),
        ("Manual ou política de qualidade?", "SIM_NAO", "2", False, ""),
        ("Possui avaliação de satisfação dos clientes?", "ESCALA_0_5", "2", False, "Informe a nota, de 0 a 5."),
        ("Sua empresa possui algum canal ou meio para receber e tratar reclamações de clientes ou parceiros?", "SIM_NAO", "3", False, ""),
        ("Existe um sistema que assegure a rastreabilidade de processos e produtos?", "SIM_NAO", "3", False, ""),
    ]),
    ("Gestão ambiental", [
        ("Possui certificação ISO 14001 ou similar vigente?", "SIM_NAO", "5", False, "Resposta 'Sim' dispensa as questões seguintes desta seção."),
        ("A empresa possui Plano de Atendimento a Emergência Ambiental?", "SIM_NAO", "4", True, ""),
        ("Existe algum programa de reciclagem de resíduos, como 3Rs e coleta seletiva?", "SIM_NAO", "3", False, ""),
        ("Sua empresa monitora os aspectos e impactos de suas atividades?", "SIM_NAO", "2", False, ""),
        ("A empresa atende aos requisitos da legislação ambiental aplicável à sua atividade e se mantém atualizada em relação a mudanças?", "SIM_NAO", "5", True, ""),
    ]),
    ("Gestão de saúde e segurança", [
        ("Possui certificação ISO 45001 ou similar vigente?", "SIM_NAO", "5", False, "Resposta 'Sim' dispensa as questões seguintes desta seção."),
        ("Possui PGR e PCMSO atualizados?", "SIM_NAO", "4", True, ""),
        ("Possui CIPA?", "SIM_NAO", "2", False, ""),
        ("A empresa disponibiliza os equipamentos de segurança necessários para que as atividades sejam realizadas adequadamente?", "SIM_NAO", "3", True, ""),
        ("A empresa disponibiliza procedimentos e instruções de saúde e segurança a serem atendidos durante a realização do serviço?", "SIM_NAO", "3", False, ""),
        ("A empresa atende aos requisitos de legislação de saúde e segurança ocupacional aplicável e se mantém atualizada?", "SIM_NAO", "2", False, ""),
    ]),
    ("Compliance e governança", [
        ("Há política de anticorrupção implementada?", "SIM_NAO", "5", False, "Anexe o manual ou a cláusula contratual."),
        ("Sua empresa disponibiliza canais de denúncia de irregularidades, abertos e amplamente divulgados a todos os empregados próprios e terceirizados?", "SIM_NAO", "3", False, ""),
        ("Sua empresa está em conformidade com a legislação que proíbe o trabalho de menores de 16 anos (exceto aprendizes a partir de 14 anos)?", "SIM_NAO", "5", True, ""),
        ("Sua empresa está em conformidade com a legislação que proíbe trabalho análogo ao escravo ou forçado, sem autuações nos últimos 3 anos?", "SIM_NAO", "5", True, ""),
        ("Sua empresa cumpre a legislação trabalhista vigente, incluindo controle de jornada e remuneração dos colaboradores?", "SIM_NAO", "5", True, ""),
        ("Volume de faturamento anual", "MULTIPLA_ESCOLHA", "3", False, ""),
        ("Há histórico de inadimplência ou falências?", "SIM_NAO", "2", True, ""),
    ]),
    ("LGPD e proteção de dados", [
        ("Possui políticas de proteção de dados?", "SIM_NAO", "3", False, ""),
        ("Houve vazamento de dados reportado?", "SIM_NAO", "2", False, ""),
    ]),
    ("Uso interno (Compras)", [
        ("Prazo de entrega", "ESCALA_0_5", "1", False, ""),
        ("Qualidade do produto ou serviço", "ESCALA_0_5", "1", False, ""),
        ("Atendimento pós-vendas", "ESCALA_0_5", "1", False, ""),
        ("Competitividade de preços", "ESCALA_0_5", "1", False, ""),
        ("Flexibilidade", "ESCALA_0_5", "1", False, ""),
        ("SLA", "ESCALA_0_5", "1", False, ""),
    ]),
]


DEMO_SUPPLIER_NAMES = [
    "Metalurgica Horizonte Ltda",
    "TransLog Solucoes em Transporte",
    "Embalagens Sul Brasil Ltda",
    "Quimica Aurora S.A.",
    "Alfa Manutencao Industrial",
    "Bravo Equipamentos Portuarios",
    "Ciclo Ambiental Servicos",
    "Delta Pecas Tecnicas",
    "Eixo Forte Transportes",
    "Fluxo Logistica Integrada",
    "Gama Automacao Industrial",
    "HidroVale Saneamento",
    "Inova EPIs e Uniformes",
    "Jato Limpeza Tecnica",
    "Kappa Engenharia",
    "Litoral Soldas Especiais",
    "Matriz Componentes",
    "Navega Sistemas",
    "Omega Paletes e Embalagens",
    "Polo Energia",
    "Quartz Manutencao Predial",
    "Rota Fria Refrigeracao",
    "Sigma Ferramentas",
    "Terra Verde Residuos",
    "Uniao Locacoes",
    "Vetor Caldeiraria",
    "W3 Telecom",
    "Xisto Minerais",
    "Yara Alimentacao Corporativa",
    "Zeta Pintura Industrial",
    "Acesso Controle e Portaria",
    "Base Forte Concretos",
    "Carga Certa Armazens",
    "Domo Seguranca Eletronica",
    "Estrela Usinagem",
    "Fenix Transportes Pesados",
    "Granito Obras Civis",
    "Horus Consultoria Ambiental",
    "Icaro Tecnologia",
    "Jund Log Armazens Gerais",
    "Kairos Treinamentos",
    "Lume Energia Solar",
    "Mobi Fleet Gestao",
    "Norte Sul Borrachas",
    "Orion Software",
    "Prisma Laboratorios",
    "Quality Service Facilities",
    "Raio Suprimentos",
    "Saturno Guindastes",
    "Trilha Comercio Atacadista",
]

STATUS_BY_SLOT = {
    0: Avaliacao.Status.RASCUNHO,
    1: Avaliacao.Status.FINALIZADA,
    2: Avaliacao.Status.FINALIZADA,
    3: Avaliacao.Status.ENVIADA,
    4: Avaliacao.Status.EM_ANALISE,
    5: Avaliacao.Status.DEVOLVIDA,
    6: Avaliacao.Status.EM_CORRECAO,
    7: Avaliacao.Status.FINALIZADA,
    8: Avaliacao.Status.ENVIADA,
    9: Avaliacao.Status.FINALIZADA,
}

FINALIZED_SCORES = [
    Decimal("99.00"),
    Decimal("97.50"),
    Decimal("95.00"),
    Decimal("92.00"),
    Decimal("88.00"),
    Decimal("83.00"),
    Decimal("74.00"),
    Decimal("58.00"),
]

CITIES = [
    ("Cubatao", "SP"),
    ("Santos", "SP"),
    ("Sao Paulo", "SP"),
    ("Curitiba", "PR"),
    ("Campinas", "SP"),
    ("Joinville", "SC"),
    ("Rio de Janeiro", "RJ"),
    ("Belo Horizonte", "MG"),
]


class Command(BaseCommand):
    help = "Cria dados iniciais conforme a planilha de avaliação de fornecedores."

    def _user(self, username, email, role, is_staff=False, is_superuser=False):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": is_staff, "is_superuser": is_superuser},
        )
        user.email = email
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        password = os.environ.get("SEED_DEFAULT_PASSWORD")
        if password:
            user.set_password(password)
        elif created:
            user.set_unusable_password()
        user.save()
        user.profile.role = role
        user.profile.save(update_fields=["role", "atualizado_em"])
        return user

    def _demo_cnpj(self, idx):
        legacy = {
            1: "12.345.678/0001-90",
            2: "45.221.908/0001-33",
            3: "08.774.120/0001-57",
            4: "98.765.432/0001-10",
        }
        if idx in legacy:
            return legacy[idx]
        return f"10.{idx:03d}.{(idx * 137) % 1000:03d}/0001-{idx % 100:02d}"

    def _qualificacao_for_score(self, score):
        if score is None:
            return ""
        if score >= Decimal("95.00"):
            return Qualificacao.Status.QUALIFICADO
        if score < Decimal("60.00"):
            return Qualificacao.Status.NAO_QUALIFICADO
        return Qualificacao.Status.RESSALVAS

    def _validity_window(self, idx, today):
        start = today - timedelta(days=30 + (idx * 9) % 240)
        if idx % 6 == 0:
            end = today - timedelta(days=idx % 20 + 1)
        elif idx % 5 == 0:
            end = today + timedelta(days=idx % 25 + 1)
        else:
            end = today + timedelta(days=45 + (idx * 11) % 220)
        return start, end

    def _answer_for_question(self, questao, idx, score):
        if questao.tipo == Questao.Tipo.ESCALA_0_5:
            if score is None:
                return str((idx % 5) + 1)
            if score >= Decimal("95.00"):
                return "5"
            if score >= Decimal("85.00"):
                return "4"
            if score >= Decimal("60.00"):
                return "3"
            return "2"
        if questao.tipo == Questao.Tipo.MULTIPLA_ESCOLHA:
            options = ["Ate R$ 1M", "R$ 1M a R$ 5M", "R$ 5M a R$ 20M", "Acima de R$ 20M"]
            stored = list(questao.opcoes.filter(ativa=True).order_by("ordem").values_list("valor", flat=True))
            return stored[(idx - 1) % len(stored)] if stored else options[(idx - 1) % len(options)]
        if questao.tipo == Questao.Tipo.ARQUIVO:
            return Resposta.Valor.SIM
        if questao.critica and score is not None and score < Decimal("70.00"):
            return Resposta.Valor.NAO
        if idx % 13 == 0 and not questao.critica:
            return Resposta.Valor.NA
        return Resposta.Valor.SIM

    @transaction.atomic
    def handle(self, *args, **options):
        self._user("admin", "admin@cesari.local", UserProfile.Role.ADMINISTRADOR, True, True)
        compras = self._user("compras", "compras@cesari.local", UserProfile.Role.COMPRAS, True, False)
        fornecedor_user = self._user("fornecedor", "fornecedor@cesari.local", UserProfile.Role.FORNECEDOR)

        questionario = (
            Questionario.objects.filter(nome__in=["Avaliação de fornecedores CESARI", "Avaliacao de fornecedores CESARI"])
            .order_by("-id")
            .first()
        )
        if questionario:
            questionario.nome = "Avaliação de fornecedores CESARI"
            questionario.descricao = "Questionário baseado no layout Rev1."
            questionario.ativo = True
            questionario.save(update_fields=["nome", "descricao", "ativo", "atualizado_em"])
        else:
            questionario = Questionario.objects.create(
                nome="Avaliação de fornecedores CESARI",
                descricao="Questionário baseado no layout Rev1.",
                ativo=True,
            )
        versao, _ = QuestionarioVersao.objects.update_or_create(
            questionario=questionario,
            numero=1,
            defaults={"titulo": "Layout Rev1", "publicado": True, "ativo": True},
        )

        Devolucao.objects.filter(avaliacao__questionario_versao=versao).delete()
        Qualificacao.objects.filter(avaliacao__questionario_versao=versao).delete()
        Resposta.objects.filter(avaliacao__questionario_versao=versao).delete()
        OpcaoResposta.objects.filter(questao__categoria__versao=versao).delete()
        Questao.objects.filter(categoria__versao=versao).delete()
        Categoria.objects.filter(versao=versao).delete()

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
                        OpcaoResposta.objects.create(questao=questao, valor=option, rotulo=option, pontuacao=Decimal(idx), ordem=idx, ativa=True)

        today = timezone.localdate()
        for idx, razao in enumerate(DEMO_SUPPLIER_NAMES, start=1):
            status = STATUS_BY_SLOT[idx % 10]
            score = FINALIZED_SCORES[(idx - 1) % len(FINALIZED_SCORES)] if status == Avaliacao.Status.FINALIZADA else None
            qualificacao = self._qualificacao_for_score(score)
            inicio_vigencia, fim_vigencia = (
                self._validity_window(idx, today) if status == Avaliacao.Status.FINALIZADA else (None, None)
            )
            nota_interna = "5"
            if score is not None:
                nota_interna = str(max(1, min(5, round(score / Decimal("20.00")))))
            elif status in {Avaliacao.Status.EM_ANALISE, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
                nota_interna = str((idx % 5) + 1)
            cidade, estado = CITIES[(idx - 1) % len(CITIES)]
            fornecedor, _ = Fornecedor.objects.update_or_create(
                cnpj=self._demo_cnpj(idx),
                defaults={
                    "razao_social": razao,
                    "nome_fantasia": razao.split()[0],
                    "email": f"fornecedor{idx}@cesari.local",
                    "inscricao_municipal": f"IM-{idx:04d}",
                    "inscricao_estadual": f"IE-{idx:04d}",
                    "endereco": f"Rua Corporativa, {100 + idx}",
                    "cidade": cidade,
                    "estado": estado,
                    "telefone": f"(13) 3000-00{idx:02d}",
                    "site": f"https://fornecedor{idx}.example.com",
                    "quantidade_funcionarios": 80 + idx * 25,
                    "responsavel": "Responsavel Comercial",
                    "cargo_responsavel": "Gerente",
                    "pontuacao_atual": score,
                    "qualificacao_atual": qualificacao,
                    "validade_qualificacao": fim_vigencia,
                },
            )
            avaliacao, _ = Avaliacao.objects.update_or_create(
                fornecedor=fornecedor,
                questionario_versao=versao,
                periodo="2026",
                defaults={
                    "responsavel": fornecedor_user if idx == 2 else compras,
                    "status": status,
                    "pontuacao": score,
                    "qualificacao": qualificacao,
                    "inicio_vigencia": inicio_vigencia,
                    "fim_vigencia": fim_vigencia,
                    "enviada_em": timezone.now() - timedelta(days=idx % 20) if status != Avaliacao.Status.RASCUNHO else None,
                    "finalizada_em": timezone.now() - timedelta(days=idx % 15) if status == Avaliacao.Status.FINALIZADA else None,
                },
            )
            if idx == 2:
                FornecedorUsuario.objects.update_or_create(
                    user=fornecedor_user,
                    defaults={"fornecedor": fornecedor, "principal": True, "ativo": True},
                )
            if status != Avaliacao.Status.RASCUNHO:
                for questao in Questao.objects.filter(categoria__versao=versao, ativa=True, uso_interno_compras=False):
                    valor = self._answer_for_question(questao, idx, score)
                    observacao = "Resposta criada para simulacao de telas e graficos."
                    if valor == Resposta.Valor.NAO:
                        observacao = "Ponto de atencao criado para validar analise critica."
                    Resposta.objects.update_or_create(
                        avaliacao=avaliacao,
                        questao=questao,
                        defaults={"resposta": valor, "observacao": observacao, "usuario": compras},
                    )
                if status in {Avaliacao.Status.EM_ANALISE, Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO, Avaliacao.Status.FINALIZADA}:
                    for questao in Questao.objects.filter(categoria__versao=versao, ativa=True, uso_interno_compras=True):
                        Resposta.objects.update_or_create(avaliacao=avaliacao, questao=questao, defaults={"resposta": nota_interna, "usuario": compras})
                if status in {Avaliacao.Status.DEVOLVIDA, Avaliacao.Status.EM_CORRECAO}:
                    Devolucao.objects.create(
                        avaliacao=avaliacao,
                        motivo=Devolucao.Motivo.INFORMACAO_INCOMPLETA,
                        comentario="Dados de simulacao: revisar evidencias e informacoes cadastrais.",
                        usuario=compras,
                    )
                if status == Avaliacao.Status.FINALIZADA:
                    Qualificacao.objects.update_or_create(
                        avaliacao=avaliacao,
                        defaults={
                            "fornecedor": fornecedor,
                            "status": qualificacao,
                            "pontuacao": score,
                            "inicio_vigencia": inicio_vigencia,
                            "fim_vigencia": fim_vigencia,
                            "definida_por": compras,
                        },
                    )
                    if score < Decimal("95.00"):
                        Devolucao.objects.create(
                            avaliacao=avaliacao,
                            motivo=Devolucao.Motivo.RESPOSTA_INCORRETA,
                            comentario="Parecer de simulacao: fornecedor finalizado abaixo do corte de homologacao.",
                            usuario=compras,
                        )

        Configuracao.objects.update_or_create(chave="VIGENCIA_DIAS", defaults={"valor": {"dias": 365}, "descricao": "Duração da vigência da qualificação em dias."})
        Configuracao.objects.update_or_create(chave="UPLOAD_EXTENSOES_PERMITIDAS", defaults={"valor": {"extensoes": ["pdf"]}})
        Configuracao.objects.update_or_create(chave="UPLOAD_MAX_BYTES", defaults={"valor": {"bytes": 10485760}})

        msg = f"Seed concluido com {len(DEMO_SUPPLIER_NAMES)} fornecedores de demonstracao. Usuarios: admin, compras, fornecedor."
        if not os.environ.get("SEED_DEFAULT_PASSWORD"):
            msg += " Defina SEED_DEFAULT_PASSWORD antes do seed para criar senha inicial."
        self.stdout.write(self.style.SUCCESS(msg))
