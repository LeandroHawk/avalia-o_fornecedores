from django import forms
from django.core.validators import RegexValidator

from backend.apps.fornecedores.models import Fornecedor

UF_CHOICES = [("", "UF")] + [(uf, uf) for uf in [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]]


class FornecedorCadastroForm(forms.ModelForm):
    cnpj = forms.CharField(validators=[RegexValidator(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$", "Informe o CNPJ no formato 00.000.000/0000-00.")])
    estado = forms.ChoiceField(choices=UF_CHOICES, required=False)

    class Meta:
        model = Fornecedor
        fields = [
            "razao_social",
            "nome_fantasia",
            "cnpj",
            "inscricao_municipal",
            "inscricao_estadual",
            "endereco",
            "cidade",
            "estado",
            "telefone",
            "site",
            "quantidade_funcionarios",
            "responsavel",
            "cargo_responsavel",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-select" if name == "estado" else "form-control"
            field.widget.attrs.setdefault("class", css)
        self.fields["cnpj"].widget.attrs.setdefault("placeholder", "00.000.000/0000-00")
        self.fields["telefone"].widget.attrs.setdefault("placeholder", "(00) 00000-0000")
        self.fields["site"].widget.attrs.setdefault("placeholder", "https://www.empresa.com.br")
