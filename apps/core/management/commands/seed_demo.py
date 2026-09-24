from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import UserProfile
from apps.avaliacoes.models import Avaliacao
from apps.core.models import Configuracao
from apps.fornecedores.models import Fornecedor, FornecedorUsuario
from apps.questionarios.models import Categoria, Questao, Questionario, QuestionarioVersao


class Command(BaseCommand):
    help = "Cria dados iniciais para demonstrar o fluxo de avaliacao."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        admin, _ = User.objects.get_or_create(username="admin", defaults={"email": "admin@cesari.local", "is_staff": True, "is_superuser": True})
        compras, _ = User.objects.get_or_create(username="compras", defaults={"email": "compras@cesari.local", "is_staff": True})
        fornecedor_user, _ = User.objects.get_or_create(username="fornecedor", defaults={"email": "fornecedor@cesari.local"})
        for user in [admin, compras, fornecedor_user]:
            user.set_password("Cesari@12345")
            user.save()
        admin.profile.role = UserProfile.Role.ADMINISTRADOR
        admin.profile.save(update_fields=["role", "atualizado_em"])
        compras.profile.role = UserProfile.Role.COMPRAS
        compras.profile.save(update_fields=["role", "atualizado_em"])
        fornecedor_user.profile.role = UserProfile.Role.FORNECEDOR
        fornecedor_user.profile.save(update_fields=["role", "atualizado_em"])

        fornecedor, _ = Fornecedor.objects.get_or_create(
            cnpj="00.000.000/0001-00",
            defaults={
                "razao_social": "Fornecedor Demonstracao Ltda",
                "nome_fantasia": "Fornecedor Demo",
                "email": "contato@fornecedor.local",
                "responsavel": "Responsavel Demo",
            },
        )
        FornecedorUsuario.objects.get_or_create(fornecedor=fornecedor, user=fornecedor_user, defaults={"principal": True})

        questionario, _ = Questionario.objects.get_or_create(nome="Questionario de Qualificacao CESARI")
        versao, _ = QuestionarioVersao.objects.get_or_create(questionario=questionario, numero=1, defaults={"titulo": "Versao inicial 2026", "publicado": True})
        qualidade, _ = Categoria.objects.get_or_create(versao=versao, nome="Qualidade", defaults={"ordem": 1, "peso": 1})
        seguranca, _ = Categoria.objects.get_or_create(versao=versao, nome="Seguranca", defaults={"ordem": 2, "peso": 1})
        Questao.objects.get_or_create(categoria=qualidade, ordem=1, defaults={"enunciado": "A empresa possui certificacao de qualidade valida?", "peso": 2})
        Questao.objects.get_or_create(categoria=qualidade, ordem=2, defaults={"enunciado": "A empresa possui procedimento documentado para controle de qualidade?", "peso": 1})
        Questao.objects.get_or_create(categoria=seguranca, ordem=1, defaults={"enunciado": "A empresa realiza treinamentos periodicos de seguranca?", "peso": 1})
        Questao.objects.get_or_create(categoria=seguranca, ordem=2, defaults={"enunciado": "A empresa possui documentos de seguranca atualizados?", "peso": 1})

        Avaliacao.objects.get_or_create(
            fornecedor=fornecedor,
            questionario_versao=versao,
            periodo="2026",
            defaults={"responsavel": fornecedor_user},
        )

        Configuracao.objects.get_or_create(chave="VIGENCIA_DIAS", defaults={"valor": {"dias": 365}, "descricao": "Duracao da vigencia da qualificacao em dias."})
        Configuracao.objects.get_or_create(chave="UPLOAD_EXTENSOES_PERMITIDAS", defaults={"valor": {"extensoes": ["pdf", "jpg", "jpeg", "png", "docx", "xlsx"]}})
        Configuracao.objects.get_or_create(chave="UPLOAD_MAX_BYTES", defaults={"valor": {"bytes": 10485760}})

        self.stdout.write(self.style.SUCCESS("Dados demo criados. Usuarios: admin/compras/fornecedor | senha: Cesari@12345"))
