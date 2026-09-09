from django import forms

from .models import ContaPagar


class ContaPagarAdminForm(forms.ModelForm):
    class Meta:
        model = ContaPagar
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "valor" in self.fields:
            self.fields["valor"].help_text = (
                "Conta parcelada: informe o valor total. Conta fixa mensal: informe o valor de cada mês."
            )
        if "total_ocorrencias" in self.fields:
            self.fields["total_ocorrencias"].help_text = (
                "Informe de 2 a 120 parcelas ou meses. As datas serão geradas mensalmente a partir do primeiro vencimento."
            )

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo_recorrencia")
        if tipo == "unica":
            cleaned_data["total_ocorrencias"] = 1
            self.instance.total_ocorrencias = 1
        return cleaned_data
