from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("avaliacoes", "0002_alter_avaliacao_status_alter_devolucao_motivo_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="resposta",
            name="resposta",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
