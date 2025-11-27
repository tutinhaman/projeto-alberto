from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class Funcionario(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.nome


class Autorizador(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.nome


class Almoxarifado(models.Model):
    nome = models.CharField(max_length=100)
    localizacao = models.CharField(max_length=150)

    def __str__(self) -> str:
        return f"{self.nome} - {self.localizacao}"


class Material(models.Model):
    nome = models.CharField(max_length=120)
    quantidade_estoque = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.nome} ({self.quantidade_estoque})"


class Acesso(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada'
        SAIDA = 'saida', 'Saida'

    class Status(models.TextChoices):
        ABERTO = 'ABERTO', 'Aberto'
        FECHADO = 'FECHADO', 'Fechado'

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE)
    autorizador = models.ForeignKey(Autorizador, on_delete=models.CASCADE)
    almoxarifado = models.ForeignKey(Almoxarifado, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    class Justificativa(models.TextChoices):
        RETIRADA_CAMPO = 'RETIRADA_CAMPO', 'Retirada de insumo para campo'
        DEVOLUCAO = 'DEVOLUCAO', 'Devolucao de material ao estoque'
        VERIFICACAO = 'VERIFICACAO', 'Verificacao de estoque'
        MANUTENCAO = 'MANUTENCAO', 'Manutencao no almoxarifado'
        FISCALIZACAO = 'FISCALIZACAO', 'Fiscalizacao interna'
        OUTROS = 'OUTROS', 'Outros'

    justificativa_padrao = models.CharField(
        max_length=100,
        choices=Justificativa.choices,
        default=Justificativa.RETIRADA_CAMPO,
    )
    observacao = models.CharField(max_length=200, blank=True, null=True)
    data_hora = models.DateTimeField(auto_now_add=True)
    data_saida = models.DateTimeField(null=True, blank=True)
    encerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='acessos_encerrados',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ABERTO,
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['-data_hora']

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} - {self.funcionario.nome} ({self.data_hora:%d/%m/%Y %H:%M})"

    def encerrar(self, *, quando=None, usuario=None):
        if self.status == self.Status.FECHADO:
            raise ValidationError('Acesso ja encerrado.')
        if not self.movimentacao_set.exists():
            raise ValidationError('Nao e possivel encerrar acesso sem movimentacoes.')
        self.status = self.Status.FECHADO
        self.data_saida = quando or timezone.now()
        self.ativo = False
        if usuario and not self.encerrado_por:
            self.encerrado_por = usuario
        self.save(update_fields=['status', 'data_saida', 'ativo', 'encerrado_por'])


class Movimentacao(models.Model):
    class Tipo(models.TextChoices):
        RETIRADA = 'retirada', 'Retirada'
        DEVOLUCAO = 'devolucao', 'Devolucao'

    acesso = models.ForeignKey(Acesso, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField()
    tipo = models.CharField(max_length=10, choices=Tipo.choices)

    class Meta:
        ordering = ['-acesso__data_hora']

    def __str__(self) -> str:
        return f"{self.material.nome} - {self.get_tipo_display()} ({self.quantidade})"

    def _atualizar_estoque(self, material: Material, quantidade: int, tipo: str, *, reverter: bool = False) -> None:
        delta = quantidade if tipo == self.Tipo.DEVOLUCAO else -quantidade
        if reverter:
            delta = -delta
        novo_estoque = material.quantidade_estoque + delta
        if novo_estoque < 0:
            raise ValidationError("Estoque insuficiente para a operacao.")
        material.quantidade_estoque = novo_estoque
        material.save(update_fields=['quantidade_estoque'])

    def save(self, *args, **kwargs):
        with transaction.atomic():
            material = None
            if self.pk:
                movimentacao_antiga = (
                    Movimentacao.objects.select_for_update()
                    .select_related('material')
                    .get(pk=self.pk)
                )
                material_antigo = movimentacao_antiga.material
                self._atualizar_estoque(
                    material_antigo,
                    movimentacao_antiga.quantidade,
                    movimentacao_antiga.tipo,
                    reverter=True,
                )
                if movimentacao_antiga.material_id == self.material_id:
                    material = material_antigo

            if material is None:
                material = Material.objects.select_for_update().get(pk=self.material_id)

            if self.tipo == self.Tipo.RETIRADA and material.quantidade_estoque < self.quantidade:
                raise ValidationError("Estoque insuficiente para retirada.")

            resultado = super().save(*args, **kwargs)
            self._atualizar_estoque(material, self.quantidade, self.tipo)
            return resultado
