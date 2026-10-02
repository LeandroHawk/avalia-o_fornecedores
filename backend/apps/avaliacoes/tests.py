import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from backend.apps.accounts.models import UserProfile
from backend.apps.avaliacoes.models import Avaliacao, Evidencia, Resposta
from backend.apps.avaliacoes.services import (
    build_avaliacao_context,
    calcular_pontuacao,
    enviar_avaliacao,
    finalizar_avaliacao,
    reprovar_avaliacao,
    salvar_resposta,
    validar_upload,
)
from backend.apps.core.models import Configuracao
from backend.apps.fornecedores.models import Fornecedor, FornecedorUsuario
from backend.apps.questionarios.models import Categoria, OpcaoResposta, Questao, Questionario, QuestionarioVersao


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

    def test_certificacao_sim_dispensa_questoes_subsequentes_no_envio(self):
        self.questao_1.enunciado = "Possui certificação ISO 9001 ou similar vigente?"
        self.questao_1.ajuda = "Resposta 'Sim' dispensa as questões subsequentes desta seção."
        self.questao_1.exige_evidencia_se_sim = False
        self.questao_1.ordem = 1
        self.questao_1.save()
        self.questao_2.ordem = 2
        self.questao_2.save()

        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)

        enviar_avaliacao(self.avaliacao, self.user_a)
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, Avaliacao.Status.ENVIADA)

    def test_certificacao_sim_remove_subsequentes_do_progresso_e_pontuacao(self):
        self.questao_1.enunciado = "Possui certificação ISO 14001 ou similar vigente?"
        self.questao_1.ajuda = "Resposta 'Sim' dispensa as questões subsequentes desta seção."
        self.questao_1.exige_evidencia_se_sim = False
        self.questao_1.peso = 5
        self.questao_1.ordem = 1
        self.questao_1.save()
        self.questao_2.peso = 5
        self.questao_2.ordem = 2
        self.questao_2.save()

        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_2, usuario=self.user_a, resposta=Resposta.Valor.NAO, justificativa="Nao possui.")
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)

        contexto = build_avaliacao_context(self.user_a, self.avaliacao)
        grupo = contexto["categorias_data"][0]
        self.assertEqual(grupo["total"], 1)
        self.assertEqual(grupo["respondidas"], 1)
        self.assertTrue(grupo["questoes"][1]["dispensada"])
        self.assertEqual(calcular_pontuacao(self.avaliacao), 100)

    def test_certificacoes_iso_da_planilha_dispensam_subsequentes_mesmo_sem_ajuda(self):
        textos = [
            "Possui certificação ISO9001 ou similar vigente?",
            "Possui certificação ISO14001 ou similar vigente?",
            "Possui certificação ISO 45001 ou similar vigente?",
        ]

        for texto in textos:
            with self.subTest(texto=texto):
                self.questao_1.enunciado = texto
                self.questao_1.ajuda = ""
                self.questao_1.exige_evidencia_se_sim = False
                self.questao_1.ordem = 1
                self.questao_1.save()
                self.questao_2.ordem = 2
                self.questao_2.save()
                self.avaliacao.respostas.all().delete()

                salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)

                contexto = build_avaliacao_context(self.user_a, self.avaliacao)
                grupo = contexto["categorias_data"][0]
                self.assertEqual(grupo["total"], 1)
                self.assertTrue(grupo["questoes"][1]["dispensada"])

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

    def test_finalizacao_bloqueia_uso_interno_incompleto(self):
        categoria_interna = Categoria.objects.create(versao=self.avaliacao.questionario_versao, nome="Uso interno (Compras)", peso=1)
        Questao.objects.create(
            categoria=categoria_interna,
            enunciado="Prazo de entrega",
            tipo=Questao.Tipo.ESCALA_0_5,
            uso_interno_compras=True,
        )
        self.questao_1.exige_evidencia_se_sim = False
        self.questao_1.save()
        self.questao_2.exige_evidencia_se_sim = False
        self.questao_2.save()
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_1, usuario=self.user_a, resposta=Resposta.Valor.SIM)
        salvar_resposta(avaliacao=self.avaliacao, questao=self.questao_2, usuario=self.user_a, resposta=Resposta.Valor.SIM)
        self.avaliacao.status = Avaliacao.Status.EM_ANALISE
        self.avaliacao.save()

        with self.assertRaisesMessage(ValidationError, "Uso interno"):
            finalizar_avaliacao(self.avaliacao, self.compras)

    def test_reprovacao_bloqueia_uso_interno_incompleto(self):
        categoria_interna = Categoria.objects.create(versao=self.avaliacao.questionario_versao, nome="Uso interno (Compras)", peso=1)
        Questao.objects.create(
            categoria=categoria_interna,
            enunciado="Prazo de entrega",
            tipo=Questao.Tipo.ESCALA_0_5,
            uso_interno_compras=True,
        )
        self.avaliacao.status = Avaliacao.Status.EM_ANALISE
        self.avaliacao.save()

        with self.assertRaisesMessage(ValidationError, "Uso interno"):
            reprovar_avaliacao(self.avaliacao, self.compras, "Parecer de reprovação.")

    @override_settings(ANTIVIRUS_COMMAND="", ANTIVIRUS_REQUIRED=False)
    def test_upload_pdf_valido_nao_depende_de_antivirus_local(self):
        arquivo = SimpleUploadedFile("evidencia.pdf", b"%PDF-1.4\nconteudo", content_type="application/pdf")

        validar_upload(arquivo)

    @override_settings(ANTIVIRUS_COMMAND="", ANTIVIRUS_REQUIRED=False)
    def test_upload_rejeita_qualquer_formato_diferente_de_pdf(self):
        arquivos = [
            SimpleUploadedFile("evidencia.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"),
            SimpleUploadedFile("evidencia.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
            SimpleUploadedFile("evidencia.docx", b"PK\x03\x04", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ]

        for arquivo in arquivos:
            with self.subTest(nome=arquivo.name):
                with self.assertRaisesMessage(ValidationError, "Apenas arquivos PDF"):
                    validar_upload(arquivo)


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
        self.questao_outras_certificacoes = Questao.objects.create(
            categoria=categoria,
            enunciado="Outras certificações?",
            peso=1,
            exige_evidencia_se_sim=True,
        )
        self.questao_volume_faturamento = Questao.objects.create(
            categoria=categoria,
            enunciado="Volume de faturamento anual",
            tipo=Questao.Tipo.MULTIPLA_ESCOLHA,
            peso=1,
            exige_evidencia_se_sim=False,
        )
        OpcaoResposta.objects.create(
            questao=self.questao_volume_faturamento,
            valor="Até R$ 1M",
            rotulo="Até R$ 1M",
            ordem=1,
            ativa=True,
        )
        self.questao_inadimplencia = Questao.objects.create(
            categoria=categoria,
            enunciado="Há histórico de inadimplência ou falências?",
            peso=1,
            exige_evidencia_se_sim=False,
            exige_justificativa_se_nao=False,
        )
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
        self.assertRedirects(
            self.client.get(reverse("dashboard")),
            reverse("avaliacao_list"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get(reverse("avaliacao_list")),
            reverse("avaliacao_detail", args=[self.avaliacao.pk]),
        )
        self.assertEqual(self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk])).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/fornecedores/").status_code, 200)

    def test_fornecedor_nao_ve_dashboard_no_sidebar(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertContains(response, "Minhas avaliações")
        self.assertNotContains(response, "Dashboard")

    def test_compras_continua_acessando_dashboard(self):
        self.client.force_login(self.compras)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Indicadores")
        self.assertContains(response, "Dashboard")

    def test_fornecedor_abre_formulario_unico_em_minhas_avaliacoes(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_list"), follow=True)
        self.assertRedirects(response, reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertContains(response, "Dados cadastrais")
        self.assertContains(response, "Possui arquivo?")
        self.assertNotContains(response, "Regras do campo")
        self.assertNotContains(response, "Obrigatório")
        self.assertNotContains(response, "Peso 0")
        self.assertNotContains(response, "AvaliaÃ§Ãµes de fornecedores")

    def test_pergunta_sim_nao_com_evidencia_exibe_upload_condicional(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk]))

        self.assertContains(response, "data-evidence-when-sim")
        self.assertContains(response, f'name="q_{self.questao.id}_file"')

    @override_settings(ANTIVIRUS_COMMAND="", ANTIVIRUS_REQUIRED=False)
    def test_upload_condicional_salva_evidencia_em_pergunta_sim_nao(self):
        self.client.force_login(self.user_a)
        Evidencia.objects.filter(resposta=self.resposta).delete()
        payload = {
            "action": "salvar",
            "razao_social": self.fornecedor_a.razao_social,
            "nome_fantasia": self.fornecedor_a.nome_fantasia,
            "cnpj": self.fornecedor_a.cnpj,
            "inscricao_municipal": self.fornecedor_a.inscricao_municipal,
            "inscricao_estadual": self.fornecedor_a.inscricao_estadual,
            "endereco": self.fornecedor_a.endereco,
            "cidade": self.fornecedor_a.cidade,
            "estado": self.fornecedor_a.estado,
            "telefone": self.fornecedor_a.telefone,
            "site": self.fornecedor_a.site,
            "quantidade_funcionarios": self.fornecedor_a.quantidade_funcionarios or "",
            "responsavel": self.fornecedor_a.responsavel,
            "cargo_responsavel": self.fornecedor_a.cargo_responsavel,
            f"q_{self.questao.id}": Resposta.Valor.SIM,
            f"q_{self.questao.id}_file": SimpleUploadedFile("evidencia.pdf", b"%PDF-1.4", content_type="application/pdf"),
        }

        with patch("backend.apps.avaliacoes.services._antivirus_command", return_value=[]):
            response = self.client.post(reverse("avaliacao_detail", args=[self.avaliacao.pk]), payload)

        self.assertRedirects(response, reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertTrue(Evidencia.objects.filter(resposta__avaliacao=self.avaliacao, resposta__questao=self.questao).exists())

    def test_outras_certificacoes_renderiza_upload_multiplo_limitado_a_5(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk]))

        self.assertContains(response, f'name="q_{self.questao_outras_certificacoes.id}_file"')
        self.assertContains(response, 'data-max-files="5"')
        self.assertContains(response, "multiple")

    @override_settings(ANTIVIRUS_COMMAND="", ANTIVIRUS_REQUIRED=False)
    def test_outras_certificacoes_aceita_ate_5_arquivos(self):
        self.client.force_login(self.user_a)
        arquivos = [
            SimpleUploadedFile(f"certificacao-{idx}.pdf", b"%PDF-1.4", content_type="application/pdf")
            for idx in range(5)
        ]
        payload = {
            "action": "salvar",
            "razao_social": self.fornecedor_a.razao_social,
            "nome_fantasia": self.fornecedor_a.nome_fantasia,
            "cnpj": self.fornecedor_a.cnpj,
            "inscricao_municipal": self.fornecedor_a.inscricao_municipal,
            "inscricao_estadual": self.fornecedor_a.inscricao_estadual,
            "endereco": self.fornecedor_a.endereco,
            "cidade": self.fornecedor_a.cidade,
            "estado": self.fornecedor_a.estado,
            "telefone": self.fornecedor_a.telefone,
            "site": self.fornecedor_a.site,
            "quantidade_funcionarios": self.fornecedor_a.quantidade_funcionarios or "",
            "responsavel": self.fornecedor_a.responsavel,
            "cargo_responsavel": self.fornecedor_a.cargo_responsavel,
            f"q_{self.questao_outras_certificacoes.id}": Resposta.Valor.SIM,
            f"q_{self.questao_outras_certificacoes.id}_file": arquivos,
        }

        with patch("backend.apps.avaliacoes.services._antivirus_command", return_value=[]):
            response = self.client.post(reverse("avaliacao_detail", args=[self.avaliacao.pk]), payload)

        self.assertRedirects(response, reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertEqual(
            Evidencia.objects.filter(
                resposta__avaliacao=self.avaliacao,
                resposta__questao=self.questao_outras_certificacoes,
            ).count(),
            5,
        )

    @override_settings(ANTIVIRUS_COMMAND="", ANTIVIRUS_REQUIRED=False)
    def test_outras_certificacoes_bloqueia_mais_de_5_arquivos(self):
        self.client.force_login(self.user_a)
        arquivos = [
            SimpleUploadedFile(f"certificacao-{idx}.pdf", b"%PDF-1.4", content_type="application/pdf")
            for idx in range(6)
        ]
        payload = {
            "action": "salvar",
            "razao_social": self.fornecedor_a.razao_social,
            "nome_fantasia": self.fornecedor_a.nome_fantasia,
            "cnpj": self.fornecedor_a.cnpj,
            "inscricao_municipal": self.fornecedor_a.inscricao_municipal,
            "inscricao_estadual": self.fornecedor_a.inscricao_estadual,
            "endereco": self.fornecedor_a.endereco,
            "cidade": self.fornecedor_a.cidade,
            "estado": self.fornecedor_a.estado,
            "telefone": self.fornecedor_a.telefone,
            "site": self.fornecedor_a.site,
            "quantidade_funcionarios": self.fornecedor_a.quantidade_funcionarios or "",
            "responsavel": self.fornecedor_a.responsavel,
            "cargo_responsavel": self.fornecedor_a.cargo_responsavel,
            f"q_{self.questao_outras_certificacoes.id}": Resposta.Valor.SIM,
            f"q_{self.questao_outras_certificacoes.id}_file": arquivos,
        }

        with patch("backend.apps.avaliacoes.services._antivirus_command", return_value=[]):
            response = self.client.post(reverse("avaliacao_detail", args=[self.avaliacao.pk]), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no máximo 5")
        self.assertFalse(
            Evidencia.objects.filter(
                resposta__avaliacao=self.avaliacao,
                resposta__questao=self.questao_outras_certificacoes,
            ).exists()
        )

    def test_salvar_rascunho_persiste_volume_faturamento_e_inadimplencia(self):
        self.client.force_login(self.user_a)
        payload = {
            "action": "salvar",
            "razao_social": self.fornecedor_a.razao_social,
            "nome_fantasia": self.fornecedor_a.nome_fantasia,
            "cnpj": self.fornecedor_a.cnpj,
            "inscricao_municipal": self.fornecedor_a.inscricao_municipal,
            "inscricao_estadual": self.fornecedor_a.inscricao_estadual,
            "endereco": self.fornecedor_a.endereco,
            "cidade": self.fornecedor_a.cidade,
            "estado": self.fornecedor_a.estado,
            "telefone": self.fornecedor_a.telefone,
            "site": self.fornecedor_a.site,
            "quantidade_funcionarios": self.fornecedor_a.quantidade_funcionarios or "",
            "responsavel": self.fornecedor_a.responsavel,
            "cargo_responsavel": self.fornecedor_a.cargo_responsavel,
            f"q_{self.questao_volume_faturamento.id}": "Até R$ 1M",
            f"q_{self.questao_inadimplencia.id}": Resposta.Valor.NAO,
        }

        response = self.client.post(reverse("avaliacao_detail", args=[self.avaliacao.pk]), payload)

        self.assertRedirects(response, reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertEqual(
            Resposta.objects.get(avaliacao=self.avaliacao, questao=self.questao_volume_faturamento).resposta,
            "Até R$ 1M",
        )
        self.assertEqual(
            Resposta.objects.get(avaliacao=self.avaliacao, questao=self.questao_inadimplencia).resposta,
            Resposta.Valor.NAO,
        )

    def test_fornecedor_sem_avaliacao_recebe_rascunho_unico(self):
        self.avaliacao.delete()
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_list"), follow=True)
        nova_avaliacao = Avaliacao.objects.get(fornecedor=self.fornecedor_a)

        self.assertRedirects(response, reverse("avaliacao_detail", args=[nova_avaliacao.pk]))
        self.assertEqual(nova_avaliacao.status, Avaliacao.Status.RASCUNHO)
        self.assertContains(response, "Dados cadastrais")
        self.assertContains(response, "Possui arquivo?")
        self.assertEqual(Avaliacao.objects.filter(fornecedor=self.fornecedor_a).count(), 1)

    def test_fornecedor_sem_questionario_publicado_recebe_formulario_padrao(self):
        self.avaliacao.delete()
        OpcaoResposta.objects.all().delete()
        Questao.objects.all().delete()
        Categoria.objects.all().delete()
        QuestionarioVersao.objects.all().delete()
        Questionario.objects.all().delete()
        self.client.force_login(self.user_a)
        response = self.client.get(reverse("avaliacao_list"), follow=True)
        nova_avaliacao = Avaliacao.objects.get(fornecedor=self.fornecedor_a)

        self.assertRedirects(response, reverse("avaliacao_detail", args=[nova_avaliacao.pk]))
        self.assertContains(response, "Dados cadastrais")
        self.assertContains(response, "Contrato social")
        self.assertContains(response, "Volume de faturamento anual")
        self.assertNotContains(response, "Não há um fornecedor vinculado")

    def test_fornecedor_sem_vinculo_recebe_fornecedor_e_formulario(self):
        FornecedorUsuario.objects.filter(user=self.user_b).delete()
        self.client.force_login(self.user_b)
        response = self.client.get(reverse("avaliacao_list"), follow=True)
        vinculo = FornecedorUsuario.objects.get(user=self.user_b)
        nova_avaliacao = Avaliacao.objects.get(fornecedor=vinculo.fornecedor)

        self.assertRedirects(response, reverse("avaliacao_detail", args=[nova_avaliacao.pk]))
        self.assertTrue(vinculo.ativo)
        self.assertContains(response, "Dados cadastrais")
        self.assertContains(response, "Possui arquivo?")

    def test_usuarios_autenticados_nao_acessam_home_ou_login_publicos(self):
        for user in [self.user_a, self.compras, self.admin]:
            self.client.force_login(user)
            self.assertRedirects(
                self.client.get(reverse("home")),
                reverse("avaliacao_list"),
                fetch_redirect_response=False,
            )
            self.assertRedirects(
                self.client.get(reverse("login")),
                reverse("avaliacao_list"),
                fetch_redirect_response=False,
            )

    def test_login_padrao_redireciona_para_lista_de_avaliacoes(self):
        response = self.client.post(reverse("login"), {"username": self.user_a.username, "password": "x"})
        self.assertRedirects(response, reverse("avaliacao_list"), fetch_redirect_response=False)

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
        self.assertNotContains(response, "Regra crítica")
        self.assertNotContains(response, "Uso interno (Compras)")
        self.assertNotContains(response, "Prazo de entrega")

    def test_compras_ve_rotulo_critico_e_secao_interna(self):
        self.client.force_login(self.compras)
        response = self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk]))
        self.assertContains(response, "Crítico")
        self.assertContains(response, "Uso interno (Compras)")
        self.assertContains(response, "Prazo de entrega")
        self.assertContains(response, "Complete Uso interno (Compras)")
        self.assertContains(response, 'value="homologar" disabled')
        self.assertContains(response, 'value="reprovar" disabled')

    def test_fornecedor_nao_acessa_avaliacao_ou_evidencia_de_outro_fornecedor(self):
        self.client.force_login(self.user_b)
        self.assertEqual(self.client.get(reverse("avaliacao_detail", args=[self.avaliacao.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("evidencia_download", args=[self.evidencia.pk])).status_code, 403)
