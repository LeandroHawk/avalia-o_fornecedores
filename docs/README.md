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
