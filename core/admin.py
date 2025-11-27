from django.contrib import admin

from .models import (
    Acesso,
    Almoxarifado,
    Autorizador,
    Funcionario,
    Material,
    Movimentacao,
)


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


@admin.register(Autorizador)
class AutorizadorAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)


@admin.register(Almoxarifado)
class AlmoxarifadoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'localizacao')
    search_fields = ('nome', 'localizacao')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('nome', 'quantidade_estoque')
    search_fields = ('nome',)


@admin.register(Acesso)
class AcessoAdmin(admin.ModelAdmin):
    list_display = ('funcionario', 'almoxarifado', 'tipo', 'data_hora')
    list_filter = ('tipo', 'almoxarifado')
    search_fields = (
        'funcionario__nome',
        'autorizador__nome',
        'justificativa_padrao',
        'observacao',
    )
    date_hierarchy = 'data_hora'


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('material', 'tipo', 'quantidade', 'acesso')
    list_filter = ('tipo', 'material')
    search_fields = ('material__nome', 'acesso__funcionario__nome')
