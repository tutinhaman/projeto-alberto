from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase

from .models import (
    Acesso,
    Almoxarifado,
    Autorizador,
    Funcionario,
    Material,
    Movimentacao,
)


class BaseSetupMixin:
    def setUp(self):
        self.funcionario = Funcionario.objects.create(nome='Fulano')
        self.autorizador = Autorizador.objects.create(nome='Chefe')
        self.almoxarifado = Almoxarifado.objects.create(nome='Central', localizacao='Base')
        self.material = Material.objects.create(nome='Cabo', quantidade_estoque=10)
        self.acesso = Acesso.objects.create(
            funcionario=self.funcionario,
            autorizador=self.autorizador,
            almoxarifado=self.almoxarifado,
            tipo=Acesso.Tipo.ENTRADA,
        )


class MovimentacaoEstoqueTest(BaseSetupMixin, TestCase):
    def test_nao_permite_retirada_acima_do_estoque(self):
        with self.assertRaises(ValidationError):
            Movimentacao.objects.create(
                acesso=self.acesso,
                material=self.material,
                quantidade=20,
                tipo=Movimentacao.Tipo.RETIRADA,
            )
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantidade_estoque, 10)

    def test_atualiza_estoque_e_rollback_em_edicao(self):
        mov = Movimentacao.objects.create(
            acesso=self.acesso,
            material=self.material,
            quantidade=3,
            tipo=Movimentacao.Tipo.RETIRADA,
        )
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantidade_estoque, 7)

        mov.quantidade = 5
        mov.save()
        self.material.refresh_from_db()
        self.assertEqual(self.material.quantidade_estoque, 5)

        mov.quantidade = 12
        with self.assertRaises(ValidationError):
            mov.save()
        mov.refresh_from_db()
        self.material.refresh_from_db()
        self.assertEqual(mov.quantidade, 5)
        self.assertEqual(self.material.quantidade_estoque, 5)


class EncerramentoAcessoTest(BaseSetupMixin, TestCase):
    def test_nao_encerrar_sem_movimentacao(self):
        with self.assertRaises(ValidationError):
            self.acesso.encerrar()
        self.acesso.refresh_from_db()
        self.assertEqual(self.acesso.status, Acesso.Status.ABERTO)

    def test_encerrar_com_movimentacao(self):
        Movimentacao.objects.create(
            acesso=self.acesso,
            material=self.material,
            quantidade=1,
            tipo=Movimentacao.Tipo.RETIRADA,
        )
        self.acesso.encerrar()
        self.acesso.refresh_from_db()
        self.assertEqual(self.acesso.status, Acesso.Status.FECHADO)
        self.assertFalse(self.acesso.ativo)
        self.assertIsNotNone(self.acesso.data_saida)


class RelatorioMensalTest(BaseSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='tester', password='123')
        self.client.login(username='tester', password='123')

    def test_considera_apenas_acessos_fechados(self):
        # aberto com movimentacao deve ser ignorado
        Movimentacao.objects.create(
            acesso=self.acesso,
            material=self.material,
            quantidade=2,
            tipo=Movimentacao.Tipo.RETIRADA,
        )

        acesso_fechado = Acesso.objects.create(
            funcionario=self.funcionario,
            autorizador=self.autorizador,
            almoxarifado=self.almoxarifado,
            tipo=Acesso.Tipo.ENTRADA,
        )
        Movimentacao.objects.create(
            acesso=acesso_fechado,
            material=self.material,
            quantidade=4,
            tipo=Movimentacao.Tipo.RETIRADA,
        )
        acesso_fechado.encerrar()

        agora = timezone.now()
        response = self.client.get(
            reverse('core:relatorio_mensal'),
            {'mes': f'{agora.month:02d}', 'ano': str(agora.year)},
        )
        totais = response.context['totais']
        self.assertEqual(totais['total_retiradas'], 4)
        self.assertEqual(totais['total_devolucoes'], 0)
        self.assertEqual(totais['saldo'], -4)
