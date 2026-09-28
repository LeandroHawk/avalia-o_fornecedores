# Avaliacao e Qualificacao de Fornecedores - CESARI

Aplicacao web independente em Python, Django e Tabler para avaliacao de fornecedores.

## Stack

- Python 3.13
- Django 6.1.1
- Django REST Framework 3.18.1
- Tabler 1.5.1 com assets locais
- PostgreSQL preparado via `DATABASE_URL`; SQLite fica apenas como fallback local

## Primeiros passos

```powershell
$env:DJANGO_DEBUG="True"
.\\.venv\\Scripts\\python manage.py migrate
.\\.venv\\Scripts\\python manage.py seed_demo
.\\.venv\\Scripts\\python manage.py runserver
```

Usuarios demo:

- `admin` / `Cesari@12345`
- `compras` / `Cesari@12345`
- `fornecedor` / `Cesari@12345`

## Seguranca implementada

- Hash de senha com Argon2.
- Protecao de login com `django-axes`.
- CSRF, cookies HttpOnly, SameSite e parametros Secure por ambiente.
- Headers de seguranca e CSP conservadora.
- API autenticada em `/api/v1/`.
- Escopo por fornecedor em telas e API para reduzir risco de IDOR/BOLA.
- Upload de evidencias com extensao, MIME, tamanho maximo e nome interno por UUID.
- Download de evidencias somente por usuarios autorizados.
- Auditoria para upload, envio, devolucao, analise, correcao e finalizacao.
- Configuracao de e-mail via variaveis de ambiente. Use SMTP em producao.

## Pendencia de negocio registrada

A regra de qualificacao para exatamente 60 pontos e ambigua no documento. O sistema bloqueia a finalizacao nessa pontuacao ate existir a configuracao `QUALIFICACAO_SCORE_60` com o status aprovado pela area responsavel.



# Backend em Camadas Django

## Summary
Reorganizei o backend em camadas explícitas sem alterar comportamento funcional: rotas/controllers recebem HTTP, services concentram regras/orquestração, models/managers cuidam do acesso a dados, e middleware centraliza a exigência de autenticação global para rotas privadas. Não criar camada `repositories/` separada, conforme escolha feita.

## Key Changes
- Criar rotas por app com `urls.py` e deixar `config/urls.py` apenas agregando: admin/auth Django, `core.urls`, `avaliacoes.urls` e `api/v1/`.
- Mover handlers HTTP para controllers explícitos:
  - `core.controllers`: `home`, `dashboard`, `central_pendencias`
  - `avaliacoes.controllers`: lista, detalhe, download de evidência
  - converter `backend/apps/api.py` em pacote `backend/apps/api/` com `controllers.py`, `serializers.py`, `urls.py`
- Manter `views.py` como reexport de compatibilidade quando já existir, evitando quebra de imports externos.
- Services passam a entregar dados prontos para controllers:
  - `core.services`: contexto do dashboard e pendências
  - `avaliacoes.services`: fluxo de avaliação, cálculo, transições, contexto da tela e processamento de respostas
  - `auditoria.services`: permanece como serviço de auditoria
- Usar models/managers como camada de dados:
  - adicionar QuerySets/managers para consultas reutilizadas, como fornecedores visíveis por usuário, avaliações visíveis, questionários ativos, notificações do usuário e qualificações visíveis
  - substituir queries diretas em controllers/API por chamadas a managers ou services
- Criar middleware de autenticação global, após `AuthenticationMiddleware`, exigindo login para rotas privadas.
  - Rotas públicas: home, login, admin, static/media de desenvolvimento quando aplicável
  - Rotas privadas HTML: redirecionar para login
  - Rotas `/api/`: responder `401` JSON quando não autenticado
  - Permissões por objeto continuam em services/models para preservar segurança de fornecedor por avaliação

## Implementation Details
- Preservar nomes de URL existentes: `home`, `dashboard`, `pendencias`, `avaliacao_list`, `avaliacao_detail`, `evidencia_download`.
- Preservar endpoint base `api/v1/` e nomes de recursos do router: fornecedores, questionarios, avaliacoes, qualificacoes, notificacoes.
- Controllers devem conter apenas parsing/validação HTTP, mensagens, redirects/renders e chamada de service.
- Services não devem depender de `HttpRequest` exceto quando já necessário para auditoria; quando possível, receber `user`, dados limpos e `request=None`.
- Não mover migrations, admins, apps, modelos de domínio nem alterar schema do banco.
- Não criar migrations; mudanças em managers/querysets devem ser sem alteração de campos.
- Manter autenticação de baixo nível do Django/DRF: `AuthenticationMiddleware`, `AxesMiddleware`, `AUTHENTICATION_BACKENDS` e `REST_FRAMEWORK`.

## Test Plan
- Rodar `.\\.venv\\Scripts\\python.exe manage.py check`.
- Rodar `.\\.venv\\Scripts\\python.exe manage.py test backend.apps.avaliacoes`.
- Adicionar ou ajustar testes para:
  - home e login acessíveis sem autenticação
  - dashboard/pendências/avaliações redirecionam usuário anônimo
  - `/api/v1/` retorna erro de autenticação para anônimo
  - fornecedor não acessa avaliação/evidência de outro fornecedor
  - usuários autenticados mantêm acesso às mesmas telas e APIs atuais
- Validar com `git status --short` que não houve remoção indevida de migrations, `__init__.py` ou arquivos estruturais Django.

## Assumptions
- “Controllers” no contexto Django serão módulos `controllers.py`, mantendo `views.py` só como compatibilidade.
- “Repositories/Models” será implementado via models e managers/querysets, sem pasta `repositories/`.
- Middleware centraliza autenticação global, mas autorização por objeto permanece em services/models para evitar brechas.
