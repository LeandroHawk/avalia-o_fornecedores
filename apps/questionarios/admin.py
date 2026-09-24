from django.contrib import admin

from .models import Categoria, OpcaoResposta, Questao, Questionario, QuestionarioVersao


class CategoriaInline(admin.TabularInline):
    model = Categoria
    extra = 0


class QuestaoInline(admin.TabularInline):
    model = Questao
    extra = 0


class OpcaoRespostaInline(admin.TabularInline):
    model = OpcaoResposta
    extra = 0


@admin.register(Questionario)
class QuestionarioAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo", "atualizado_em")
    list_filter = ("ativo",)
    search_fields = ("nome",)


@admin.register(QuestionarioVersao)
class QuestionarioVersaoAdmin(admin.ModelAdmin):
    list_display = ("questionario", "numero", "titulo", "publicado", "ativo")
    list_filter = ("publicado", "ativo")
    inlines = [CategoriaInline]


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "versao", "ordem", "peso", "ativa")
    list_filter = ("ativa",)
    inlines = [QuestaoInline]


@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = ("enunciado", "categoria", "tipo", "ordem", "peso", "obrigatoria", "ativa")
    list_filter = ("tipo", "obrigatoria", "ativa")
    search_fields = ("enunciado",)
    inlines = [OpcaoRespostaInline]


@admin.register(OpcaoResposta)
class OpcaoRespostaAdmin(admin.ModelAdmin):
    list_display = ("rotulo", "questao", "valor", "pontuacao", "ativa")
    list_filter = ("ativa",)

# Register your models here.
