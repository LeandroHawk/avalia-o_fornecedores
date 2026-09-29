# Frontend - Avaliacao de Fornecedores

## Stack

- Front-end server-side renderizado pelo Django.
- UI Kit: Tabler.
- Responsividade obrigatoria para celular, tablet e computador.
- Imagens preferencialmente em SVG ou WEBP.
- Arquivo de execucao do sistema: `python app.py`.

## Estrutura visual principal

- Criar ou revisar a Side NavBar com menus conforme o perfil autenticado.
- Remover o acesso ao WhatsApp Web da Tela de Inicio.
- Manter layout responsivo em celular, tablet e computador.
- Usar componentes Tabler para botoes, cards, tabelas, formularios, badges de status, alertas, sidebar, topbar e dashboard.

## Telas obrigatorias

- Tela de Inicio.
- Tela de Login.
- Dashboard.
- Perfil do usuario.
- Tela de preencher formulario - Visao do Fornecedor.
- Tela de pendencias - Visao do Fornecedor.
- Tela de analisar avaliacao - Visao do Comprador.
- Tela de verificacao de logs - Visao do Admin.
- Tela de gestao de usuarios - Visao do Admin.

## Visao do Fornecedor

O fornecedor deve conseguir preencher todas as informacoes do checklist, anexar arquivos solicitados, salvar rascunho, continuar de onde parou, enviar somente quando todos os obrigatorios estiverem preenchidos, visualizar pendencias, corrigir apenas campos devolvidos e reenviar ajustes.

Regras de tela:

- Nenhum campo obrigatorio pode ficar pendente no envio final.
- A regra de negocio do Excel nao deve ser alterada.
- Ao enviar tudo corretamente, o status deve mudar para `Em analise`.
- Quando houver ajuste solicitado, o fornecedor deve enxergar o campo, o motivo e a acao necessaria.

## Visao do Comprador

O comprador deve conseguir visualizar informacoes enviadas, respostas e anexos; analisar cada campo; solicitar ajustes em campos especificos; informar motivo por campo; aprovar ou reprovar a avaliacao.

Acoes disponiveis:

- `Solicitar ajustes`
- `Reprovar`
- `Aprovar`

Ao aprovar ou reprovar, o status deve ser finalizado como `Aprovado` ou `Reprovado`, e o sistema deve disparar e-mail via SMTP para o fornecedor.

## Visao do Admin

O Admin deve conseguir acessar dashboards, verificar logs, gerenciar usuarios, criar usuarios dos perfis Fornecedor, Comprador e Admin, definir nome, e-mail, usuario, senha e perfil, e ter acesso completo ao sistema.

## Estados e feedback visual

Usar badges Tabler para os 4 status oficiais:

- `Em analise`
- `Ajustes solicitados`
- `Reprovado`
- `Aprovado`

Nao criar outros status apos o fornecedor finalizar o checklist.

## Performance no front

- Controlar tamanho e extensao de imagens no upload.
- Usar imagens SVG ou WEBP sempre que possivel.
- Aplicar cache para imagens.
- Aplicar cache para paginas onde fizer sentido.
- Evitar componentes criados e nunca renderizados.
- Remover importacoes nao utilizadas.
- Remover codigo comentado sem explicacao.
- Revisar estados, variaveis e funcoes nunca utilizados.
