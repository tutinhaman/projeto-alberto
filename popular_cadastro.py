"""Popula cadastros base do almoxarifado."""

import os

import django


def configurar_django() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_almoxarifado.settings')
    django.setup()


def popular_dados() -> None:
    from core.models import Almoxarifado, Autorizador, Funcionario, Material

    funcionarios = [
        'Bruno Lima',
        'Ana Paula Ribeiro',
        'Marcos Vinicius Alves',
        'Fernanda Souza',
    ]
    autorizadores = [
        'Gustavo Alves',
        'Carla Ferreira',
    ]
    almoxarifados = [
        ('Unidade Sinop', 'Sinop - MT'),
        ('Unidade Lucas do Rio Verde', 'Lucas do Rio Verde - MT'),
        ('Unidade Sorriso', 'Sorriso - MT'),
    ]
    materiais = [
        ('Fertilizante NPK 20-05-20', 500),
        ('Semente de Soja Premium', 800),
        ('Defensivo Agricola Biologico', 200),
        ('Micronutriente Foliar', 400),
        ('Corretivo de Solo Calcario', 300),
    ]

    for nome in funcionarios:
        Funcionario.objects.get_or_create(nome=nome)

    for nome in autorizadores:
        Autorizador.objects.get_or_create(nome=nome)

    for nome, localizacao in almoxarifados:
        Almoxarifado.objects.get_or_create(
            nome=nome,
            defaults={'localizacao': localizacao},
        )

    for nome, quantidade in materiais:
        material, _ = Material.objects.get_or_create(nome=nome)
        material.quantidade_estoque = quantidade
        material.save(update_fields=['quantidade_estoque'])

    print('Cadastros basicos populados com sucesso! Pronto para registrar acessos e movimentacoes.')


if __name__ == '__main__':
    configurar_django()
    popular_dados()
