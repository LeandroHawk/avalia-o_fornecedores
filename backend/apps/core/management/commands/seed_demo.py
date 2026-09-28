import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from backend.apps.accounts.models import UserProfile
from backend.apps.avaliacoes.models import Avaliacao, Resposta
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.models import Fornecedor, FornecedorUsuario
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


SUPPLIERS = [
    ("Metalúrgica Horizonte Ltda", "12.345.678/0001-90", "FINALIZADA", "100.00", "4.2"),
    ("TransLog Soluções em Transporte", "45.221.908/0001-33", "ENVIADA", "100.00", ""),
    ("Embalagens Sul Brasil Ltda", "08.774.120/0001-57", "FINALIZADA", "92.00", "2.3"),
    ("Química Aurora S.A.", "98.765.432/0001-10", "RASCUNHO", None, ""),
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
                    exige_evidencia_se_sim=tipo == "ARQUIVO",
                    exige_justificativa_se_nao=False,
                    ativa=True,
                )
                if texto == "Volume de faturamento anual":
                    for idx, option in enumerate(["Até R$ 1M", "R$ 1M a R$ 5M", "R$ 5M a R$ 20M", "Acima de R$ 20M"], start=1):
                        OpcaoResposta.objects.create(questao=questao, valor=option, rotulo=option, pontuacao=Decimal(idx), ordem=idx, ativa=True)

        for idx, (razao, cnpj, status, score, nota) in enumerate(SUPPLIERS, start=1):
            fornecedor, _ = Fornecedor.objects.update_or_create(
                cnpj=cnpj,
                defaults={
                    "razao_social": razao,
                    "nome_fantasia": razao.split()[0],
                    "email": f"fornecedor{idx}@cesari.local",
                    "inscricao_municipal": f"IM-{idx:04d}",
                    "inscricao_estadual": f"IE-{idx:04d}",
                    "endereco": f"Rua Corporativa, {100 + idx}",
                    "cidade": "Curitiba" if idx == 2 else "Cubatão",
                    "estado": "PR" if idx == 2 else "SP",
                    "telefone": f"(13) 3000-00{idx:02d}",
                    "site": f"https://fornecedor{idx}.example.com",
                    "quantidade_funcionarios": 80 + idx * 25,
                    "responsavel": "Responsável Comercial",
                    "cargo_responsavel": "Gerente",
                    "pontuacao_atual": score,
                },
            )
            avaliacao, _ = Avaliacao.objects.update_or_create(
                fornecedor=fornecedor,
                questionario_versao=versao,
                periodo="2026",
                defaults={
                    "responsavel": fornecedor_user if idx == 2 else compras,
                    "status": getattr(Avaliacao.Status, status),
                    "pontuacao": score,
                    "qualificacao": "QUALIFICADO" if score and Decimal(score) >= 95 else ("NAO_QUALIFICADO" if score else ""),
                    "enviada_em": timezone.now() if status != "RASCUNHO" else None,
                },
            )
            if idx == 2:
                FornecedorUsuario.objects.update_or_create(
                    user=fornecedor_user,
                    defaults={"fornecedor": fornecedor, "principal": True, "ativo": True},
                )
            if status != "RASCUNHO":
                for questao in Questao.objects.filter(categoria__versao=versao, ativa=True, uso_interno_compras=False):
                    valor = "5" if questao.tipo == Questao.Tipo.ESCALA_0_5 else Resposta.Valor.SIM
                    if questao.tipo == Questao.Tipo.MULTIPLA_ESCOLHA:
                        valor = "R$ 5M a R$ 20M"
                    Resposta.objects.update_or_create(avaliacao=avaliacao, questao=questao, defaults={"resposta": valor, "usuario": compras})
                if nota:
                    for questao in Questao.objects.filter(categoria__versao=versao, ativa=True, uso_interno_compras=True):
                        Resposta.objects.update_or_create(avaliacao=avaliacao, questao=questao, defaults={"resposta": str(round(float(nota))), "usuario": compras})

        Configuracao.objects.update_or_create(chave="VIGENCIA_DIAS", defaults={"valor": {"dias": 365}, "descricao": "Duração da vigência da qualificação em dias."})
        Configuracao.objects.update_or_create(chave="UPLOAD_EXTENSOES_PERMITIDAS", defaults={"valor": {"extensoes": ["pdf", "jpg", "jpeg", "png", "docx", "xlsx"]}})
        Configuracao.objects.update_or_create(chave="UPLOAD_MAX_BYTES", defaults={"valor": {"bytes": 10485760}})

        msg = "Seed concluído. Usuários: admin, compras, fornecedor."
        if not os.environ.get("SEED_DEFAULT_PASSWORD"):
            msg += " Defina SEED_DEFAULT_PASSWORD antes do seed para criar senha inicial."
        self.stdout.write(self.style.SUCCESS(msg))
