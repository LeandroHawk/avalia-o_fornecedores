# Backend - Avaliacao de Fornecedores

## Stack

- Backend: Django.
- Arquitetura: MVT.
- Banco atual: SQLite.
- Banco futuro: SQL Server.
- ORM: Django ORM.
- Execucao: `python app.py`.

## Inicializacao da aplicacao

- Manter o arquivo de inicializacao como `app.py`.
- O comando principal deve ser `python app.py`.
- Nao criar outro arquivo principal de inicializacao.
- Caso existam comandos antigos de execucao, documentar no README apenas como alternativa tecnica.

## Banco de dados

Banco atual:

- SQLite para desenvolvimento local.

Evolucao futura:

- Preparar configuracao para SQL Server futuramente.
- Evitar SQL escrito manualmente quando o Django ORM resolver.
- Criar indices em campos usados para busca, filtros e relacionamentos.

Campos candidatos a indice:

- usuario;
- perfil;
- fornecedor;
- avaliacao;
- status;
- data de criacao;
- data de atualizacao;
- campos usados em telas de listagem.

## Seed inicial do banco

Criar ou ajustar comando de seed para excluir dados atuais do SQLite em ambiente de desenvolvimento, recriar dados iniciais e criar os usuarios solicitados.

Usuarios iniciais:

| Perfil | Usuario | Nome | Senha inicial |
|---|---|---|---|
| Admin | `admin` | Admin | `Cesari@12345` |
| Comprador | `leandro` | Leandro | `Cesari@12345` |
| Fornecedor | `cellula.matter` | Cellula Matter | `Cesari@12345` |

Observacoes:

- A senha acima deve ser usada apenas no seed local ou ambiente controlado.
- Em producao, a senha inicial deve ser definida por variavel de ambiente ou fluxo seguro.
- O sistema deve exigir troca de senha quando aplicavel.
- Nao gravar senhas em texto puro.

## Regras de negocio principais

Fornecedor:

- Preenche as informacoes.
- Todos os campos obrigatorios devem ser preenchidos antes do envio final.
- Pode salvar rascunho e continuar de onde parou.
- Ao enviar tudo, status vira `Em analise`.
- Quando receber ajuste, corrige os campos solicitados e reenvia.

Comprador:

- Analisa respostas e arquivos.
- Pode solicitar ajustes por campo, com motivo obrigatorio.
- Pode reprovar ou aprovar.
- Ao aprovar ou reprovar, dispara e-mail SMTP para o fornecedor.

Admin:

- Pode criar usuarios.
- Pode acessar dashboards, logs e acoes administrativas.
- Pode acessar tudo.

## Status oficiais

Depois que o fornecedor terminar de preencher e enviar o checklist, existem apenas 4 status:

- `Em analise`
- `Ajustes solicitados`
- `Reprovado`
- `Aprovado`

Regras:

- Nao criar status extra para o fluxo final.
- `Aprovado` e `Reprovado` devem ser estados finais.
- `Ajustes solicitados` deve permitir correcao pelo fornecedor.
- `Em analise` deve bloquear edicao livre pelo fornecedor, exceto quando houver devolucao.

## E-mail via SMTP

Configurar envio de e-mail para aprovacao, reprovacao e solicitacao de ajustes quando necessario.

Regras:

- SMTP deve usar variaveis de ambiente.
- Nao gravar usuario, senha, token ou host sensivel no codigo.
- Registrar falha de envio em log.
- Evitar que falha de e-mail quebre uma transacao ja concluida sem tratamento.

## Arquitetura

Padrao definido:

- Django MVT:
  - Model: dados e regras relacionadas ao dominio persistido.
  - View/Controller: entrada HTTP, validacao de requisicao, renderizacao e redirecionamento.
  - Template: apresentacao com Tabler.

Organizacao recomendada:

- Models para entidades centrais.
- Services para regras de negocio e transicoes de status.
- Forms para validacao server-side de formularios.
- Templates para telas.
- Middleware para autenticacao global, seguranca e auditoria quando necessario.
- Management commands para seed e rotinas administrativas.

Modulos esperados:

- Accounts ou Usuarios.
- Fornecedores.
- Questionarios.
- Avaliacoes.
- Evidencias ou Anexos.
- Notificacoes.
- Auditoria ou Logs.
- Core ou Dashboard.

## Fluxo principal do sistema

1. Admin cria os usuarios.
2. Fornecedor acessa o sistema.
3. Fornecedor preenche o checklist.
4. Fornecedor salva rascunho se ainda nao terminou.
5. Fornecedor envia o checklist completo.
6. Sistema muda status para `Em analise`.
7. Comprador analisa respostas e arquivos.
8. Comprador aprova, reprova ou solicita ajustes.
9. Se solicitar ajustes, fornecedor corrige os campos indicados.
10. Fornecedor reenvia.
11. Comprador aprova ou reprova.
12. Sistema envia e-mail ao fornecedor quando houver aprovacao ou reprovacao.

## Modelagem e diagramas

Ferramenta definida: DRAW.IO.

Diagramas recomendados:

- Diagrama de fluxo do fornecedor.
- Diagrama de fluxo do comprador.
- Diagrama de permissao por perfil.
- Diagrama de status da avaliacao.
- Diagrama de entidades principais.
- Diagrama MVT do sistema.

## Evolucao para SQL Server

- Evitar dependencias especificas do SQLite.
- Usar migrations do Django.
- Usar Django ORM para consultas.
- Evitar queries raw sem necessidade.
- Centralizar configuracao de banco por variaveis de ambiente.
- Testar migrations antes da troca.
- Revisar tipos de campos, indices e constraints.

## Observabilidade e logs

Registrar logs para login, falha de login, criacao de usuario, envio do checklist, upload de arquivos, solicitacao de ajustes, aprovacao, reprovacao, erro de envio de e-mail e tentativas de acesso nao autorizado.

Admin deve ter tela para ver logs e filtrar por usuario, data, tipo de evento, avaliacao ou fornecedor.

## Limpeza tecnica e refatoracao

Prompt de analise tecnica:

> Analise o projeto e identifique componentes criados, mas nunca renderizados, funcoes declaradas, mas nunca chamadas, importacoes nao utilizadas, variaveis de estado que nunca mudam ou nunca sao lidas, codigo comentado sem explicacao. Sugira a remocao desses elementos, depois disso monte tarefas e subtarefas para refatoracao.

Tarefas:

- Mapear arquivos nao utilizados.
- Mapear funcoes nao chamadas.
- Mapear imports sem uso.
- Mapear duplicidades.
- Remover codigo morto.
- Criar testes para fluxos criticos.
- Atualizar README.

## Documentacao e checklist

Atualizar o README com instalacao, `.env`, execucao com `python app.py`, migrations, seed, usuarios de desenvolvimento, testes, SMTP, banco e regras de acesso por perfil.

Checklist de conclusao:

- Front-end com Tabler revisado.
- Responsividade testada em celular, tablet e computador.
- Telas do Fornecedor, Comprador e Admin implementadas.
- Seed recriando Admin, Comprador Leandro e Fornecedor Cellula Matter.
- SQLite limpo e populado pelo seed em desenvolvimento.
- Status limitados aos 4 oficiais apos envio do checklist.
- SMTP configurado por variavel de ambiente.
- Logs administrativos disponiveis.
- 27 regras de seguranca revisadas.
- README atualizado.
- Diagrama DRAW.IO criado.
- Testes dos fluxos principais executados.
