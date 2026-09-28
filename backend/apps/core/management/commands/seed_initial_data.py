import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from backend.apps.accounts.models import UserProfile
from backend.apps.avaliacoes.models import Avaliacao
from backend.apps.core.management.commands.seed_demo import SECTIONS
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.models import Fornecedor, FornecedorUsuario
from backend.apps.questionarios.models import Categoria, OpcaoResposta, Questao, Questionario, QuestionarioVersao


DEFAULT_PASSWORD = "Cesari@12345"


class Command(BaseCommand):
    help = "Cria a base inicial limpa com Admin, Comprador Leandro e Fornecedor Cellula Matter."

    def _user(self, *, username, email, first_name, role, is_staff=False, is_superuser=False):
        User = get_user_model()
        password = os.environ.get("SEED_DEFAULT_PASSWORD", DEFAULT_PASSWORD)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
        user.profile.role = role
        user.profile.save(update_fields=["role", "atualizado_em"])
        return user

    @transaction.atomic
    def handle(self, *args, **options):
        admin = self._user(
            username="admin",
            email="admin@cesari.local",
            first_name="Admin",
            role=UserProfile.Role.ADMINISTRADOR,
            is_staff=True,
            is_superuser=True,
        )
        comprador = self._user(
            username="leandro",
            email="leandro@cesari.local",
            first_name="Leandro",
            role=UserProfile.Role.COMPRAS,
            is_staff=True,
        )
        fornecedor_user = self._user(
            username="cellula.matter",
            email="cellula.matter@cellulamatter.local",
            first_name="Cellula Matter",
            role=UserProfile.Role.FORNECEDOR,
        )

        questionario = Questionario.objects.create(
            nome="Avaliação de fornecedores CESARI",
            descricao="Questionário baseado no layout Rev1 informado em planilha.",
            ativo=True,
        )
        versao = QuestionarioVersao.objects.create(questionario=questionario, numero=1, titulo="Layout Rev1", publicado=True, ativo=True)

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
                    exige_evidencia_se_sim=tipo == Questao.Tipo.ARQUIVO,
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

        fornecedor = Fornecedor.objects.create(
            razao_social="Cellula Matter",
            nome_fantasia="Cellula Matter",
            cnpj="00.000.000/0001-00",
            email=fornecedor_user.email,
            status=Fornecedor.Status.ATIVO,
        )
        FornecedorUsuario.objects.create(fornecedor=fornecedor, user=fornecedor_user, principal=True, ativo=True)
        Avaliacao.objects.create(
            fornecedor=fornecedor,
            questionario_versao=versao,
            periodo="2026",
            responsavel=fornecedor_user,
            status=Avaliacao.Status.RASCUNHO,
        )

        Configuracao.objects.create(
            chave="VIGENCIA_DIAS",
            valor={"dias": 365},
            descricao="Duração da vigência da qualificação em dias.",
            atualizado_por=admin,
        )
        Configuracao.objects.create(chave="UPLOAD_EXTENSOES_PERMITIDAS", valor={"extensoes": ["pdf", "jpg", "jpeg", "png", "docx", "xlsx"]})
        Configuracao.objects.create(chave="UPLOAD_MAX_BYTES", valor={"bytes": 10485760})

        self.stdout.write(self.style.SUCCESS("Base inicial criada."))
        self.stdout.write("Usuários:")
        self.stdout.write(f"- admin / {os.environ.get('SEED_DEFAULT_PASSWORD', DEFAULT_PASSWORD)}")
        self.stdout.write(f"- leandro / {os.environ.get('SEED_DEFAULT_PASSWORD', DEFAULT_PASSWORD)}")
        self.stdout.write(f"- cellula.matter / {os.environ.get('SEED_DEFAULT_PASSWORD', DEFAULT_PASSWORD)}")
        self.stdout.write(f"Fornecedor: {fornecedor.razao_social}")
        self.stdout.write(f"Comprador: {comprador.first_name}")
