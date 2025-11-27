from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('acessos/', views.registrar_acesso, name='registrar_acesso'),
    path('acessos/<int:id>/encerrar/', views.encerrar_acesso, name='encerrar_acesso'),
    path('historico/', views.historico, name='historico'),
    path('movimentacoes/', views.registrar_movimentacao, name='registrar_movimentacao'),
    path('movimentacoes/<int:acesso_id>/', views.registrar_movimentacao, name='registrar_movimentacao_por_acesso'),
    path('relatorio/', views.relatorio_mensal, name='relatorio_mensal'),
]
