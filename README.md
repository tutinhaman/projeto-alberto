# Controle de Almoxarifado

Aplicacao Django simples para registrar acessos ao almoxarifado, controlar retiradas e devolucoes de materiais e gerar relatorios mensais com saldo de estoque.

## Tecnologias utilizadas
- Python 3.13 e Django 5.2
- SQLite (padrao do `django-admin startproject`)
- Bootstrap 5 (via CDN) para o layout basico

## Como rodar localmente
1. **Criar e ativar o ambiente virtual**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
2. **Instalar dependencias**
   ```powershell
   pip install -r requirements.txt
   ```
3. **Aplicar migracoes**
   ```powershell
   python manage.py migrate
   ```
4. **Criar um superusuario para acessar o admin**
   ```powershell
   python manage.py createsuperuser
   ```
5. **Executar o servidor**
   ```powershell
   python manage.py runserver
   ```
6. Acesse `http://127.0.0.1:8000/`. Usuarios nao autenticados sao redirecionados para o login do admin (`/admin/login/`); apos autenticacao, a raiz volta para a tela de registro de acesso.

## Admin e cadastros basicos
- URL: `http://127.0.0.1:8000/admin/`
- Cadastre Funcionarios, Autorizadores, Almoxarifados e Materiais antes de registrar acessos.
- Todas as tabelas do app `core` estao disponiveis no painel e possuem filtros/pesquisas uteis para agilizar o cadastro.

## Telas principais
- **Registrar Acesso** (`/`): formulario para registrar entradas/saidas com funcionario, autorizador, almoxarifado e justificativa. Depois de salvar, o sistema direciona para a tela de movimentacao ligada ao acesso.
- **Registrar Movimentacao** (`/movimentacoes/` ou `/movimentacoes/<acesso_id>/`): permite vincular materiais a um acesso e registrar se houve retirada ou devolucao, com validacao automatica de estoque.
- **Historico** (`/historico/`): lista todos os acessos, mostrando justificativa e as movimentacoes de cada um.
- **Relatorio Mensal** (`/relatorio/`): permite selecionar mes/ano e apresenta totais de retiradas/devolucoes, saldo e detalhamento por material.

## Regra de negocio (estoque automatico)
Cada movimentacao recalcula o estoque do material:
- **Retirada** diminui o estoque e e bloqueada se nao houver quantidade suficiente.
- **Devolucao** aumenta o estoque.
- Atualizacoes sao executadas dentro de uma transacao (`transaction.atomic`) e tambem tratam edicoes, revertendo o efeito anterior antes de aplicar o novo.

Assim, o campo `Material.quantidade_estoque` permanece sincronizado com o saldo real sem precisar de planilhas externas.
