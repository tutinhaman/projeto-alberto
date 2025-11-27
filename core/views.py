from datetime import datetime

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import AcessoForm, MovimentacaoForm, RelatorioMensalForm
from .models import Acesso, Movimentacao


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:registrar_acesso')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Login realizado com sucesso.')
            return redirect('core:registrar_acesso')
        messages.error(request, 'Credenciais invalidas. Verifique usuario e senha.')

    return render(request, 'core/login.html')


@login_required
def logout_view(request):
    logout(request)
    return render(request, 'core/logout.html')


@login_required
def registrar_acesso(request):
    if request.method == 'POST':
        form = AcessoForm(request.POST)
        if form.is_valid():
            funcionario = form.cleaned_data['funcionario']
            tipo = form.cleaned_data['tipo']

            if tipo == Acesso.Tipo.ENTRADA and Acesso.objects.filter(
                funcionario=funcionario, status=Acesso.Status.ABERTO
            ).exists():
                messages.error(
                    request,
                    'Este funcionário já tem um acesso em aberto.',
                )
            elif tipo == Acesso.Tipo.ENTRADA:
                acesso = form.save(commit=False)
                acesso.status = Acesso.Status.ABERTO
                acesso.data_saida = None
                acesso.ativo = True
                acesso.save()
                messages.success(request, 'Acesso registrado com sucesso.')
                return redirect(
                    'core:registrar_movimentacao_por_acesso', acesso_id=acesso.id
                )
            else:
                messages.error(
                    request,
                    'O encerramento de acessos deve ser feito pela pagina de historico.',
                )
    else:
        form = AcessoForm()

    return render(request, 'core/registrar_acesso.html', {'form': form})


@login_required
def registrar_movimentacao(request, acesso_id=None):
    acesso = get_object_or_404(Acesso, pk=acesso_id) if acesso_id else None
    if acesso and acesso.status != Acesso.Status.ABERTO:
        messages.error(request, 'Nao e possivel registrar movimentacoes em um acesso encerrado.')
        return redirect('core:historico')
    initial = {'acesso': acesso} if acesso else None
    acessos_queryset = (
        Acesso.objects.select_related('funcionario', 'almoxarifado')
        .filter(status=Acesso.Status.ABERTO)
        .order_by('-data_hora')
        .all()
    )

    if request.method == 'POST':
        form = MovimentacaoForm(request.POST, initial=initial)
    else:
        form = MovimentacaoForm(initial=initial)

    form.fields['acesso'].queryset = acessos_queryset
    if acesso:
        form.fields['acesso'].initial = acesso
        form.fields['acesso'].disabled = True
        form.fields['acesso'].widget.attrs['disabled'] = True

    material_estoques = {
        material.id: material.quantidade_estoque
        for material in form.fields['material'].queryset
    }

    if request.method == 'POST' and form.is_valid():
        acesso_escolhido = form.cleaned_data['acesso']
        if acesso_escolhido.status != Acesso.Status.ABERTO:
            messages.error(request, 'Nao e possivel registrar movimentacoes em um acesso encerrado.')
            return redirect(request.path)
        try:
            movimentacao = form.save()
        except ValidationError as exc:
            for mensagem in exc.messages:
                form.add_error(None, mensagem)
        else:
            messages.success(request, 'Movimentacao registrada com sucesso.')
            estoque_restante = movimentacao.material.quantidade_estoque
            if estoque_restante < 5:
                messages.warning(
                    request,
                    f'Estoque baixo: {movimentacao.material.nome} com {estoque_restante} unidades.',
                )
            anchor_url = f"{reverse('core:historico')}#acesso-{acesso_escolhido.id}"
            return redirect(anchor_url)

    context = {
        'form': form,
        'acesso': acesso,
        'material_estoques': material_estoques,
        'estoque_limite': 5,
    }
    return render(request, 'core/registrar_movimentacao.html', context)


@login_required
def historico(request):
    acessos_qs = (
        Acesso.objects.select_related('funcionario', 'autorizador', 'almoxarifado')
        .prefetch_related('movimentacao_set__material')
        .annotate(
            total_retiradas=Coalesce(
                Sum(
                    'movimentacao__quantidade',
                    filter=Q(movimentacao__tipo=Movimentacao.Tipo.RETIRADA),
                ),
                Value(0),
            ),
            total_devolucoes=Coalesce(
                Sum(
                    'movimentacao__quantidade',
                    filter=Q(movimentacao__tipo=Movimentacao.Tipo.DEVOLUCAO),
                ),
                Value(0),
            ),
        )
        .annotate(saldo=F('total_devolucoes') - F('total_retiradas'))
    )
    status = request.GET.get('status')
    funcionario = request.GET.get('funcionario')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if status in [Acesso.Status.ABERTO, Acesso.Status.FECHADO]:
        acessos_qs = acessos_qs.filter(status=status)
    if funcionario:
        acessos_qs = acessos_qs.filter(funcionario__nome__icontains=funcionario)

    if data_inicio:
        try:
            data_ini = datetime.fromisoformat(data_inicio).date()
        except ValueError:
            data_ini = None
        if data_ini:
            acessos_qs = acessos_qs.filter(data_hora__date__gte=data_ini)
    if data_fim:
        try:
            data_final = datetime.fromisoformat(data_fim).date()
        except ValueError:
            data_final = None
        if data_final:
            acessos_qs = acessos_qs.filter(data_hora__date__lte=data_final)

    paginator = Paginator(acessos_qs, 10)
    page_number = request.GET.get('page')
    acessos = paginator.get_page(page_number)

    acessos_ids = [acesso.id for acesso in acessos]
    saldos_por_acesso = {}
    if acessos_ids:
        saldos_qs = (
            Movimentacao.objects.filter(acesso_id__in=acessos_ids)
            .values('acesso_id', 'material__nome', 'material__quantidade_estoque')
            .annotate(
                retiradas=Coalesce(
                    Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.RETIRADA)),
                    Value(0),
                ),
                devolucoes=Coalesce(
                    Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.DEVOLUCAO)),
                    Value(0),
                ),
            )
            .annotate(
                saldo=F('devolucoes') - F('retiradas'),
                estoque_atual=F('material__quantidade_estoque'),
            )
        )
        for row in saldos_qs:
            saldos_por_acesso.setdefault(row['acesso_id'], []).append(row)
        for acesso in acessos:
            acesso.saldos_material = saldos_por_acesso.get(acesso.id, [])

    params_sem_pagina = request.GET.copy()
    params_sem_pagina.pop('page', None)
    querystring_sem_pagina = params_sem_pagina.urlencode()

    context = {
        'acessos': acessos,
        'filtros': {
            'status': status or '',
            'funcionario': funcionario or '',
            'data_inicio': data_inicio or '',
            'data_fim': data_fim or '',
        },
        'querystring_sem_pagina': querystring_sem_pagina,
        'saldos_por_acesso': saldos_por_acesso,
    }
    return render(request, 'core/historico.html', context)


@login_required
def encerrar_acesso(request, id):
    acesso = get_object_or_404(Acesso, pk=id)
    if acesso.status == Acesso.Status.FECHADO:
        messages.info(request, 'Este acesso ja foi encerrado anteriormente.')
        return redirect('core:historico')
    if request.method != 'POST':
        messages.error(request, 'Metodo invalido para encerrar acesso.')
        return redirect('core:historico')
    try:
        acesso.encerrar(usuario=request.user)
    except ValidationError as exc:
        for mensagem in exc.messages:
            messages.error(request, mensagem)
    else:
        messages.success(request, 'Acesso encerrado com sucesso.')
    return redirect('core:historico')


@login_required
def relatorio_mensal(request):
    agora = timezone.now()
    anos_disponiveis = list(
        {data.year for data in Acesso.objects.dates('data_hora', 'year')}
    ) or [agora.year]
    anos_disponiveis = sorted(anos_disponiveis)
    ano_choices = [(str(ano), str(ano)) for ano in anos_disponiveis]

    initial = {'mes': f"{agora.month:02d}", 'ano': str(anos_disponiveis[-1])}
    if request.GET:
        form = RelatorioMensalForm(request.GET)
    else:
        form = RelatorioMensalForm(initial=initial)
    form.fields['ano'].choices = ano_choices

    if form.is_bound and form.is_valid():
        mes_selecionado = int(form.cleaned_data['mes'])
        ano_selecionado = int(form.cleaned_data['ano'])
        almoxarifado = form.cleaned_data.get('almoxarifado')
        funcionario = form.cleaned_data.get('funcionario')
    else:
        mes_selecionado = int(form.initial.get('mes', initial['mes']))
        ano_selecionado = int(form.initial.get('ano', initial['ano']))
        almoxarifado = None
        funcionario = None

    movimentacoes = Movimentacao.objects.filter(
        acesso__data_hora__year=ano_selecionado,
        acesso__data_hora__month=mes_selecionado,
        acesso__status=Acesso.Status.FECHADO,
    ).select_related('material', 'acesso', 'acesso__funcionario', 'acesso__almoxarifado')
    if almoxarifado:
        movimentacoes = movimentacoes.filter(acesso__almoxarifado=almoxarifado)
    if funcionario:
        movimentacoes = movimentacoes.filter(acesso__funcionario=funcionario)

    resumo_por_tipo_acesso = []
    # Mantemos apenas acessos de entrada, que sao os usados no fluxo atual.
    qs_entrada = movimentacoes.filter(acesso__tipo=Acesso.Tipo.ENTRADA)
    agregados_entrada = qs_entrada.aggregate(
        retiradas=Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.RETIRADA)),
        devolucoes=Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.DEVOLUCAO)),
    )
    resumo_por_tipo_acesso.append(
        {
            'tipo': Acesso.Tipo.ENTRADA,
            'label': dict(Acesso.Tipo.choices)[Acesso.Tipo.ENTRADA],
            'total_movimentacoes': qs_entrada.count(),
            'total_retiradas': agregados_entrada['retiradas'] or 0,
            'total_devolucoes': agregados_entrada['devolucoes'] or 0,
        }
    )

    totais = movimentacoes.aggregate(
        total_retiradas=Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.RETIRADA)),
        total_devolucoes=Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.DEVOLUCAO)),
    )
    totais = {chave: valor or 0 for chave, valor in totais.items()}
    totais['saldo'] = totais['total_devolucoes'] - totais['total_retiradas']

    resumo_por_material = (
        movimentacoes.values('material__nome')
        .annotate(
            retiradas=Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.RETIRADA)),
            devolucoes=Sum('quantidade', filter=Q(tipo=Movimentacao.Tipo.DEVOLUCAO)),
        )
        .order_by('material__nome')
    )

    context = {
        'form': form,
        'movimentacoes': movimentacoes,
        'totais': totais,
        'resumo_por_material': resumo_por_material,
        'resumo_por_tipo_acesso': resumo_por_tipo_acesso,
        'mes_selecionado': mes_selecionado,
        'ano_selecionado': ano_selecionado,
        'filtros': {
            'almoxarifado': almoxarifado,
            'funcionario': funcionario,
        },
    }
    return render(request, 'core/relatorio_mensal.html', context)
