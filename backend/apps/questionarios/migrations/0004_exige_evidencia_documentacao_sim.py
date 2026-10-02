import unicodedata

from django.db import migrations


QUESTOES_COM_EVIDENCIA_SE_SIM = {
    "inscricao municipal",
    "inscricao estadual",
    "certidoes negativas (inss, fgts, receita federal)",
    "possui alvara de funcionamento vigente?",
    "possui avcb?",
    "licencas ambientais obrigatorias (ex.: operacao, emissao)",
    "outras certificacoes?",
}


def _normalizar_texto(texto):
    sem_acentos = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acentos.casefold().split())


def exigir_evidencia_documentacao(apps, schema_editor):
    Questao = apps.get_model("questionarios", "Questao")
    for questao in Questao.objects.filter(tipo="SIM_NAO"):
        if _normalizar_texto(questao.enunciado) in QUESTOES_COM_EVIDENCIA_SE_SIM:
            questao.exige_evidencia_se_sim = True
            questao.save(update_fields=["exige_evidencia_se_sim"])


def reverter_evidencia_documentacao(apps, schema_editor):
    Questao = apps.get_model("questionarios", "Questao")
    for questao in Questao.objects.filter(tipo="SIM_NAO"):
        if _normalizar_texto(questao.enunciado) in QUESTOES_COM_EVIDENCIA_SE_SIM:
            questao.exige_evidencia_se_sim = False
            questao.save(update_fields=["exige_evidencia_se_sim"])


class Migration(migrations.Migration):

    dependencies = [
        ("questionarios", "0003_alter_questao_tipo"),
    ]

    operations = [
        migrations.RunPython(exigir_evidencia_documentacao, reverter_evidencia_documentacao),
    ]
