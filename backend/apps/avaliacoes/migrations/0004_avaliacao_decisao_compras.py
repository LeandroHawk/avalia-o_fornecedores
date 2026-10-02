from django.db import migrations, models


def preencher_decisao_compras(apps, schema_editor):
    Avaliacao = apps.get_model("avaliacoes", "Avaliacao")
    HistoricoAvaliacao = apps.get_model("avaliacoes", "HistoricoAvaliacao")

    for avaliacao in Avaliacao.objects.filter(status="FINALIZADA", decisao_compras=""):
        if HistoricoAvaliacao.objects.filter(avaliacao_id=avaliacao.id, acao="REPROVACAO").exists():
            avaliacao.decisao_compras = "REPROVADA"
        elif HistoricoAvaliacao.objects.filter(avaliacao_id=avaliacao.id, acao="FINALIZACAO").exists():
            avaliacao.decisao_compras = "APROVADA"
        elif avaliacao.qualificacao == "NAO_QUALIFICADO":
            avaliacao.decisao_compras = "REPROVADA"
        else:
            avaliacao.decisao_compras = "APROVADA"
        avaliacao.save(update_fields=["decisao_compras"])


def limpar_decisao_compras(apps, schema_editor):
    Avaliacao = apps.get_model("avaliacoes", "Avaliacao")
    Avaliacao.objects.update(decisao_compras="")


class Migration(migrations.Migration):
    dependencies = [
        ("avaliacoes", "0003_alter_resposta_resposta"),
    ]

    operations = [
        migrations.AddField(
            model_name="avaliacao",
            name="decisao_compras",
            field=models.CharField(
                blank=True,
                choices=[("APROVADA", "Aprovada"), ("REPROVADA", "Reprovada")],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.RunPython(preencher_decisao_compras, limpar_decisao_compras),
    ]
