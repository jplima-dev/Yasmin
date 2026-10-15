# Verificação da entrega

## Redesign e PT/EN — 20/09/2026

- 23 testes automatizados passaram: os 18 existentes e 5 novos para idioma, persistência da preferência, interpolação segura, datas e tradução de atividades/erros.
- Build de produção passou sem avisos. Nenhuma biblioteca de interface foi adicionada.
- Validação de interface em `http://127.0.0.1:5175`, com dados fictícios separados da origem normal 5173.
- Troca Português → English aplica-se imediatamente à navegação, página, formulários e datas. English permaneceu selecionado após recarregar.
- Retorno ao português, foco no seletor após a troca, temas claro/escuro e menu recolhido: verificados na interface.
- Criar projeto, criar tarefas com vínculo/prazo/prioridade/subtarefa, concluir uma tarefa e atualizar o progresso para 50%: verificado.
- Criar nota cujo título é “Configurações”: o título e o corpo permaneceram em português na interface inglesa; marcação HTML foi exibida como texto.
- Busca por corpo sem acentos, contagem de resultados, estado sem resultados, botão de limpar, ESC e abrir resultado com Enter: verificados.
- Visão geral sem rolagem horizontal da página ou conteúdo em 1280×800, 1366×768, 1600×900, 1920×1080 e 960×640.
- Quadros carregou o Notas Flutuantes original. A interface interna desse módulo continua em português; apenas o entorno do Organizador recebeu traduções. A fonte original não foi editada.
- Nenhum erro de console observado nos fluxos de interface acima.

Os testes automatizados cobrem preservação de dados, conflitos, backup/restauração e paginação; o relatório anterior abaixo documenta verificações adicionais da entrega original. Esta rodada não representa uma nova homologação de todos os recursos internos do Notas Flutuantes ou de todos os navegadores.

## Escopo

MVP 0.1 funcional com Dashboard, Projetos, Tarefas, Notas, busca, temas, persistência e backup. A pedido do usuário, o Notas Flutuantes existente foi integrado antecipadamente ao módulo Quadros, com ligação de fonte e relação quadro/projeto.

## Testes automatizados

`npm test`: **18 testes passaram**.

- Datas civis, filtros, adiamentos, conclusão/reabertura e ordenação da próxima tarefa.
- Normalização, limites e rejeição de valores inválidos.
- Persistência, rollback e conflito de revisão em IndexedDB simulado.
- Exclusão de projeto preservando tarefas/notas e removendo apenas os vínculos de quadros.
- Progresso derivado de tarefas e atualização dos projetos de origem/destino.
- Arquivamento sem perda de vínculos.
- Exportação/restauração, mesclagem idempotente, referências inválidas e versões incompatíveis.
- Importação concorrente e invalidação de editores com revisão obsoleta.
- Rejeição de arquivo acima de 50 MiB antes da leitura.
- Paginação com chaves de ordenação iguais.
- Identidade dos arquivos acessados pela ligação local e pela fonte real.

Esses testes usam `node:test` e `fake-indexeddb`. Não substituem validação em navegadores reais.

## IndexedDB real

A página de desenvolvimento `tests/browser.html` foi executada no navegador integrado. Ela cria um banco temporário com nome único, executa os cenários e remove apenas esse banco de teste.

Resultados:

- CRUD e cálculo de progresso: passou.
- Falha após escrita e rollback integral: passou.
- Rejeição de revisão obsoleta: passou.
- Exportar, validar e restaurar JSON: passou.
- Fechar/reabrir conexão preservando dados: passou.
- Busca em 5.002 registros: **253 ms** até finalizar; **24 ms** até os primeiros resultados; saída limitada a 50 itens.

A fixture de volume contém 500 projetos, 2.000 tarefas e 2.500 notas, mais dois registros do teste funcional. As notas possuem aproximadamente 2 mil caracteres. A medição corresponde a esta máquina, no navegador integrado, sem desaceleração de CPU. Não é garantia de desempenho em outros dispositivos. A interface da busca publica resultados parciais enquanto a consulta continua.

Para repetir, inicie o servidor de desenvolvimento e abra `/tests/browser.html`. Essa página não faz parte de `dist/`.

## Fluxos de interface verificados

Os dados fictícios de interface foram criados somente na origem de teste `http://127.0.0.1:5174`, separada do uso normal em 5173.

- Dashboard vazio sem exemplos misturados à base de uso normal.
- Criar projeto e refletir sua existência no Dashboard.
- Criar tarefa com prazo, projeto, prioridade e subtarefa; recarregar e conferir persistência.
- Concluir tarefa e atualizar o progresso para 100%.
- Criar nota com tags e texto contendo marcação HTML; texto exibido sem execução.
- Encontrar a nota pelo corpo, usando termos sem acentos, e abrir o resultado.
- Abrir a mesma nota em duas abas; salvar na segunda e tentar salvar o rascunho obsoleto na primeira. O conflito foi apresentado e o texto do formulário permaneceu intacto.
- Abrir o Notas Flutuantes integrado, criar uma nota, editar seu texto, vincular o quadro a um projeto e recarregar o visualizador. O texto permaneceu salvo.
- Layout de projetos e Dashboard em 360 px sem rolagem horizontal; abrir o menu móvel e navegar.

A verificação visual da importação pelo seletor de arquivos foi interrompida pela retomada da sessão; não a considerar concluída com base no teste de serviço. A restauração transacional foi executada com IndexedDB real, como descrito acima.

## Build e fonte compartilhada

`npm run build`: passou. Build estático, módulos separados e nenhuma dependência de framework em runtime.

Última medição de saída comprimida: aproximadamente **9,82 kB** para o JavaScript principal e **6,01 kB** para CSS. Os módulos de tela são separados. Esses números não incluem o aplicativo Notas Flutuantes nem sua imagem de logo, carregados ao abrir Quadros.

Os hashes de `index.html`, `script.js`, `storage.js`, `style.css`, `icons.css` e `LICENSE` em `dist/notas-flutuantes` coincidiram com os da fonte compartilhada. O Git do projeto original permaneceu sem alterações de arquivos causadas por esta implementação.

## Limites da validação atual

- Não foi executada uma matriz em Firefox/Safari nem em hardware modesto real.
- O ensaio de 20 mil itens e medições sistemáticas de memória ficam pendentes.
- O schema é inicial; migração de uma versão pública anterior ainda não existe para validar.
- O Notas Flutuantes preserva suas próprias regras de armazenamento/concorrência. A proteção de revisão do painel não cobre a edição simultânea do mesmo quadro em várias abas.
- PWA instalável, Service Worker, biblioteca/PDF próprios do painel e sincronização não fazem parte desta entrega.
