from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("avaliacoes", "0004_avaliacao_decisao_compras"),
        ("questionarios", "0004_exige_evidencia_documentacao_sim"),
    ]

    operations = [
        migrations.CreateModel(
            name="AjusteQuestao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                ("motivo", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDENTE", "Pendente"), ("RESPONDIDO", "Respondido"), ("RESOLVIDO", "Resolvido")],
                        db_index=True,
                        default="PENDENTE",
                        max_length=20,
                    ),
                ),
                (
                    "avaliacao",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ajustes_questoes", to="avaliacoes.avaliacao"),
                ),
                (
                    "questao",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ajustes", to="questionarios.questao"),
                ),
                (
                    "solicitado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ajustes_solicitados",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["questao__categoria__ordem", "questao__ordem", "criado_em"],
                "indexes": [models.Index(fields=["avaliacao", "status"], name="avaliacoes__avaliac_088226_idx")],
                "constraints": [models.UniqueConstraint(fields=("avaliacao", "questao"), name="uniq_ajuste_avaliacao_questao")],
            },
        ),
    ]
