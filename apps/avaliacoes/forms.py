from django import forms

from .models import Devolucao, Resposta


class RespostaForm(forms.Form):
    resposta = forms.ChoiceField(choices=Resposta.Valor.choices, label="Resposta", required=True)
    observacao = forms.CharField(label="Observacao", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    justificativa = forms.CharField(label="Justificativa", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    evidencia = forms.FileField(label="Evidencia", required=False)


class DevolucaoForm(forms.Form):
    motivo = forms.ChoiceField(choices=Devolucao.Motivo.choices, label="Motivo")
    comentario = forms.CharField(label="Comentario", widget=forms.Textarea(attrs={"rows": 4}))
