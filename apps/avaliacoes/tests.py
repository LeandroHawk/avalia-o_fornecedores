from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.accounts.models import UserProfile
from apps.avaliacoes.models import Avaliacao, Resposta
from apps.avaliacoes.services import calcular_pontuacao, enviar_avaliacao, finalizar_avaliacao, salvar_resposta
from apps.core.models import Configuracao
from apps.fornecedores.models import Fornecedor, FornecedorUsuario
from apps.questionarios.models import Categoria, Questao, Questionario, QuestionarioVersao


class AvaliacaoServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.compras = User.objects.create_user("compras", password="x")
        self.compras.profile.role = UserProfile.Role.COMPRAS
        self.compras.profile.save()
        self.user_a = User.objects.create_user("fornecedor_a", password="x")
        self.user_b = User.objects.create_user("fornecedor_b", password="x")
        self.fornecedor_a = Fornecedor.objects.create(razao_social="A", cnpj="00.000.000/0001-01", email="a@x.com")
        self.fornecedor_b = Fornecedor.objects.create(razao_social="B", cnpj="00.000.000/0001-02", email="b@x.com")
        FornecedorUsuario.objects.create(fornecedor=self.fornecedor_a, user=self.user_a)
        FornecedorUsuario.objects.create(fornecedor=self.fornecedor_b, user=self.user_b)
        q = Questionario.objects.create(nome="Q")
        v = QuestionarioVersao.objects.create(questionario=q, numero=1, titulo="V1", publicado=True)
        cat = Categoria.objects.create(versao=v, nome="Geral", peso=1)
        self.questao_1 = Questao.objects.create(categoria=cat, enunciado="Possui certificado?", peso=1)
        self.questao_2 = Questao.objects.create(categoria=cat, enunciado="Possui procedimento?", peso=1)
        self.avaliacao = Avaliacao.objects.create(fornecedor=self.fornecedor_a, questionario_versao=v, periodo="2026", responsavel=self.user_a)

    def test_fornecedor_nao_acessa_avaliacao_de_outro_fornecedor(self):
        with self.assertRaises(PermissionDenied):
            salvar_resposta(
                avaliacao=self.avaliacao,
                questao=self.questao_1,
                usuario=self.user_b,
                resposta=Resposta.Valor.NAO,
                justificativa="Nao atende.",
            )

    def test_nao_exige_justificativa(self):
        with self.assertRaises(ValidationError):
            salvar_resposta(
                avaliacao=self.avaliacao,
                questao=self.questao_1,
                usuario=self.user_a,
                resposta=Resposta.Valor.NAO,
                justificativa="",
            )

    def test_envio_bloqueia_sim_sem_evidencia(self):
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_2, usuario=self.user_a, resposta=Resposta.Valor.NAO, justificativa="Ainda nao possui.")
        with self.assertRaises(ValidationError):
            enviar_avaliacao(self.avaliacao, self.user_a)

    def test_calculo_pontuacao(self):
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_2, usuario=self.user_a, resposta=Resposta.Valor.NAO, justificativa="Nao possui.")
        self.assertEqual(calcular_pontuacao(self.avaliacao), 50)

    def test_finalizacao_bloqueia_pontuacao_60_sem_parametro(self):
        self.questao_1.peso = 3
        self.questao_1.exige_evidencia_se_sim = False
        self.questao_1.save()
        self.questao_2.peso = 2
        self.questao_2.save()
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_2, usuario=self.user_a, resposta=Resposta.Valor.NAO, justificativa="Nao possui.")
        self.avaliacao.status = Avaliacao.Status.EM_ANALISE
        self.avaliacao.save()
        with self.assertRaises(ValidationError):
            finalizar_avaliacao(self.avaliacao, self.compras)

    def test_finalizacao_com_parametro_de_60(self):
        Configuracao.objects.create(chave="QUALIFICACAO_SCORE_60", valor={"status": "RESSALVAS"})
        self.questao_1.peso = 3
        self.questao_1.exige_evidencia_se_sim = False
        self.questao_1.save()
        self.questao_2.peso = 2
        self.questao_2.save()
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_2, usuario=self.user_a, resposta=Resposta.Valor.NAO, justificativa="Nao possui.")
        self.avaliacao.status = Avaliacao.Status.EM_ANALISE
        self.avaliacao.save()
        finalizar_avaliacao(self.avaliacao, self.compras)
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.qualificacao, "RESSALVAS")
