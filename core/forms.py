from django import forms

from .models import Acesso, Almoxarifado, Funcionario, Movimentacao


class AcessoForm(forms.ModelForm):
    class Meta:
        model = Acesso
        fields = [
            'funcionario',
            'autorizador',
            'almoxarifado',
            'tipo',
            'justificativa_padrao',
            'observacao',
        ]
        widgets = {
            'tipo': forms.RadioSelect(attrs={'class': 'flex gap-3 text-sm text-gray-700'}),
            'observacao': forms.Textarea(
                attrs={
                    'rows': 3,
                    'class': 'border border-gray-300 rounded-lg p-3 w-full focus:outline-none focus:ring-2 focus:ring-blue-600',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        selects = ['funcionario', 'autorizador', 'almoxarifado', 'justificativa_padrao']
        select_classes = 'border border-gray-300 rounded-lg p-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-600 bg-white'
        for nome in selects:
            self.fields[nome].widget.attrs.update({'class': select_classes})
        self.fields['observacao'].widget.attrs.setdefault('placeholder', 'Detalhe adicional (opcional)')
        self.fields['funcionario'].label = 'Funcionario'
        self.fields['autorizador'].label = 'Autorizador'
        self.fields['almoxarifado'].label = 'Almoxarifado'
        self.fields['justificativa_padrao'].label = 'Justificativa'
        tipo_field = self.fields['tipo']
        tipo_field.initial = Acesso.Tipo.ENTRADA
        tipo_field.choices = [
            choice for choice in tipo_field.choices if choice[0] == Acesso.Tipo.ENTRADA
        ]

    def clean(self):
        cleaned_data = super().clean()
        justificativa = cleaned_data.get('justificativa_padrao')
        observacao = cleaned_data.get('observacao')
        if justificativa == Acesso.Justificativa.OUTROS and not observacao:
            self.add_error('observacao', 'Descreva a justificativa quando selecionar "Outros".')
        return cleaned_data


class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ['acesso', 'material', 'quantidade', 'tipo']
        widgets = {
            'tipo': forms.RadioSelect(attrs={'class': 'flex gap-3 text-sm text-gray-700'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = 'border border-gray-300 rounded-lg p-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-600 bg-white text-base'
        for nome, field in self.fields.items():
            if nome != 'tipo':
                field.widget.attrs.update({'class': base_class})
        tipo_field = self.fields['tipo']
        tipo_field.choices = Movimentacao.Tipo.choices
        tipo_field.widget.choices = tipo_field.choices
        tipo_field.initial = Movimentacao.Tipo.RETIRADA


class RelatorioMensalForm(forms.Form):
    MES_CHOICES = [(str(i), f"{i:02d}") for i in range(1, 13)]

    mes = forms.ChoiceField(choices=MES_CHOICES, label='Mes')
    ano = forms.ChoiceField(label='Ano')
    almoxarifado = forms.ModelChoiceField(
        queryset=Almoxarifado.objects.all(),
        required=False,
        empty_label='Todos',
        label='Almoxarifado',
    )
    funcionario = forms.ModelChoiceField(
        queryset=Funcionario.objects.all(),
        required=False,
        empty_label='Todos',
        label='Funcionario',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        select_class = 'border border-gray-300 rounded-lg p-2 w-full bg-white focus:outline-none focus:ring-2 focus:ring-blue-600'
        for field in self.fields.values():
            field.widget.attrs.update({'class': select_class})
