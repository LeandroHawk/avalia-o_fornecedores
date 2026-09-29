# Seguranca - Avaliacao de Fornecedores

## Controle de acesso e autorizacao

1. Implementar 3 perfis oficiais: Fornecedor, Comprador e Admin.
2. Validar autorizacao sempre no backend, nunca apenas no front-end.
3. Impedir BOLA/IDOR: usuario nao pode acessar dados de terceiros alterando IDs em URLs ou APIs.
4. Aplicar permissao por objeto em avaliacoes, fornecedores, anexos e pendencias.
5. Impedir escalacao de privilegio por parametros enviados pelo navegador.
6. Nao armazenar perfil, permissoes ou flags administrativas no local storage.
7. Admin pode tudo; Comprador analisa avaliacoes; Fornecedor acessa apenas seus proprios dados.

## Autenticacao e sessao

8. Usar hash seguro de senha fornecido pelo Django.
9. Bloquear conta temporariamente por 5 minutos apos 5 tentativas incorretas.
10. Implementar rate limiting no backend para login e endpoints sensiveis.
11. Nao implementar rate limiting via local storage.
12. Nao armazenar tokens no local storage.
13. Configurar cookies com `HttpOnly`, `Secure` e `SameSite=Strict` ou `SameSite=Lax`.
14. Caso JWT seja usado no futuro, os tokens devem ser short-lived.
15. Redefinicao de senha nao pode aceitar senha fraca.
16. Redefinicao de senha nao pode permitir reutilizar a senha atual.

## Protecao contra ataques comuns

17. Prevenir SQL Injection usando Django ORM ou consultas parametrizadas.
18. Prevenir XSS com escaping automatico, sanitizacao e cuidado com HTML dinamico.
19. Manter CSRF ativo em formularios e rotas que alteram dados.
20. Configurar CORS restritivo somente para dominios autorizados.
21. Configurar Content-Security-Policy.
22. Configurar `Strict-Transport-Security` em producao.
23. Configurar `X-Frame-Options` para prevenir clickjacking.
24. Configurar `X-Content-Type-Options`.

## Dados, upload e segredos

25. Proibir segredos no codigo: credenciais, chaves, senhas e tokens devem ficar fora do repositorio.
26. Validar uploads por extensao, tamanho, MIME type e magic bytes; renomear arquivos e armazenar fora da raiz publica.
27. Validar todos os dados recebidos por whitelist: tipo, tamanho, formato, intervalo e opcoes permitidas.
