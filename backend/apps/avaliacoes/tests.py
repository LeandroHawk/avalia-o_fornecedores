import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from backend.apps.accounts.models import UserProfile
from backend.apps.avaliacoes.models import Avaliacao, Evidencia, Resposta
from backend.apps.avaliacoes.services import calcular_pontuacao, enviar_avaliacao, finalizar_avaliacao, salvar_resposta
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.models import Fornecedor, FornecedorUsuario
from backend.apps.questionarios.models import Categoria, Questao, Questionario, QuestionarioVersao


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


class AvaliacaoRouteAuthTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root.name)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(self.media_root.cleanup)

        User = get_user_model()
        self.compras = User.objects.create_user("compras_rota", password="x")
        self.compras.profile.role = UserProfile.Role.COMPRAS
        self.compras.profile.save()
        self.admin = User.objects.create_user("admin_rota", password="x")
        self.admin.profile.role = UserProfile.Role.ADMINISTRADOR
        self.admin.profile.save()
        self.user_a = User.objects.create_user("fornecedor_rota_a", password="x")
        self.user_b = User.objects.create_user("fornecedor_rota_b", password="x")
        self.fornecedor_a = Fornecedor.objects.create(razao_social="A", cnpj="00.000.000/0001-11", email="a@x.com")
        self.fornecedor_b = Fornecedor.objects.create(razao_social="B", cnpj="00.000.000/0001-12", email="b@x.com")
        FornecedorUsuario.objects.create(fornecedor=self.fornecedor_a, user=self.user_a)
        FornecedorUsuario.objects.create(fornecedor=self.fornecedor_b, user=self.user_b)
        questionario = Questionario.objects.create(nome="Q Rotas")
        versao = QuestionarioVersao.objects.create(questionario=questionario, numero=1, titulo="V1", publicado=True)
        categoria = Categoria.objects.create(versao=versao, nome="Geral", peso=1)
        self.questao = Questao.objects.create(categoria=categoria, enunciado="Possui arquivo?", peso=1)
        self.questao_critica = Questao.objects.create(categoria=categoria, enunciado="Pergunta crítica?", peso=1, critica=True)
        categoria_interna = Categoria.objects.create(versao=versao, nome="Uso interno (Compras)", peso=1)
        self.questao_interna = Questao.objects.create(
            categoria=categoria_interna,
            enunciado="Prazo de entrega",
            tipo=Questao.Tipo.ESCALA_0_5,
            peso=1,
            uso_interno_compras=True,
        )
        self.avaliacao = Avaliacao.objects.create(
            fornecedor=self.fornecedor_a,
            questionario_versao=versao,
            periodo="2026",
            responsavel=self.user_a,
        )
        self.resposta = Resposta.objects.create(
            avaliacao=self.avaliacao,
            questao=self.questao,
            resposta=Resposta.Valor.SIM,
            usuario=self.user_a,
        )
        self.evidencia = Evidencia.objects.create(
            resposta=self.resposta,
            arquivo=SimpleUploadedFile("evidencia.pdf", b"%PDF-1.4", content_type="application/pdf"),
            nome_original="evidencia.pdf",
            extensao="pdf",
            mime_type="application/pdf",
            tamanho=8,
            enviado_por=self.user_a,
        )

    def test_home_e_login_sao_publicos(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)

    def test_rotas_privadas_redirecionam_anonimo_para_login(self):
        for url_name in ["dashboard", "pendencias", "avaliacao_list"]:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response["Location"])

    def test_api_retorna_401_para_anonimo(self):
        response = self.client.get("/api/v1/fornecedores/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Authentication credentials were not provided.")

    def test_usuario_autenticado_acessa_telas_e_api_visiveis(self):
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("avaliacao_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk])).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/fornecedores/").status_code, 200)

    def test_usuarios_autenticados_nao_acessam_home_ou_login_publicos(self):
        for user in [self.user_a, self.compras, self.admin]:
            self.client.force_login(user)
            self.assertRedirects(self.client.get(reverse("home")), reverse("avaliacao_list"))
            self.assertRedirects(self.client.get(reverse("login")), reverse("avaliacao_list"))

    def test_login_padrao_redireciona_para_lista_de_avaliacoes(self):
        response = self.client.post(reverse("login"), {"username": self.user_a.username, "password": "x"})
        self.assertRedirects(response, reverse("avaliacao_list"))

    def test_login_preserva_next_para_rota_privada(self):
        target = reverse("avaliacao_detail", args=[self.avaliacao.pk])
        response = self.client.post(
            f"{reverse('login')}?next={target}",
            {"username": self.user_a.username, "password": "x", "next": target},
        )
        self.assertRedirects(response, target)

    def test_fornecedor_nao_ve_rotulo_critico_nem_secao_interna(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertContains(response, "Pergunta crítica?")
        self.assertNotContains(response, "Crítico")
        self.assertNotContains(response, "Uso interno (Compras)")
        self.assertNotContains(response, "Prazo de entrega")

    def test_compras_ve_rotulo_critico_e_secao_interna(self):
        self.client.force_login(self.compras)
        response = self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertContains(response, "Crítico")
        self.assertContains(response, "Uso interno (Compras)")
        self.assertContains(response, "Prazo de entrega")

    def test_fornecedor_nao_acessa_avaliacao_ou_evidencia_de_outro_fornecedor(self):
        self.client.force_login(self.user_b)
        self.assertEqual(self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("evidencia_download", args=[self.evidencia.pk])).status_code, 403)
