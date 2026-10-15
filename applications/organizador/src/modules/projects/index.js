import { t, tr } from '../../services/i18n.js';
import { el, pageHeading, button, emptyState, select, pager, confirmAction, toast, icon } from '../../components/ui.js';
import { projectCard, taskRow, noteCard, badge, sectionTitle } from '../../components/records.js';
import { openEditor } from '../../components/entity-editor.js';
import { page, get, scan, projectStats, save, remove } from '../../services/data-service.js';
import { projectStatuses } from '../../domain/models.js';
import { formatDate } from '../../utils/dates.js';

export async function mount(root, ctx) {
  if (ctx.id) return detail(root, ctx);
  root.append(pageHeading(t('Projetos'), t('Transforme suas ideias em próximos passos.'), button(t('Novo projeto'), () => openEditor('projects'), { variant: 'primary', symbol: 'plus' })));
  const filter = select([{ value: '', label: t('Todos os status') }, ...Object.entries(projectStatuses).map(([value, label]) => ({ value, label: t(label) }))], ctx.query.get('status') || '', { 'aria-label': t('Filtrar projetos por status') });
  const list = el('div', { className: 'project-grid' });
  const pagination = el('div');
  root.append(el('div', { className: 'filter-bar' }, filter), list, pagination);
  let cursor = null, history = [], generation = 0;
  async function render() {
    const run = ++generation;
    const result = await page('projects', { after: cursor, filter: project => !filter.value || project.status === filter.value });
    const stats = await Promise.all(result.records.map(project => projectStats(project.id)));
    if (ctx.signal.aborted || run !== generation) return;
    list.replaceChildren(...result.records.map((project, i) => projectCard(project, stats[i])));
    if (!result.records.length) list.append(emptyState('projects', t('Dê espaço a uma ideia'), t('Crie um projeto para reunir tarefas e notas em um só lugar.'), button(t('Criar projeto'), () => openEditor('projects'), { variant: 'primary', symbol: 'plus' })));
    pagination.replaceChildren(pager(result.next, history, direction => { if (direction === 'next') { history.push(cursor); cursor = result.next; } else cursor = history.pop(); return render(); }));
  }
  filter.addEventListener('change', () => { cursor = null; history = []; window.history.replaceState(null, '', `#/projects?status=${filter.value}`); render().catch(ctx.error); }, { signal: ctx.signal });
  ctx.setDataRefresh(detail => {
    if (!['projects', 'tasks'].includes(detail.kind)) return false;
    return render().then(() => true);
  });
  await render();
}

async function detail(root, ctx) {
  const project = await get('projects', ctx.id);
  if (!project) { root.append(emptyState('projects', t('Projeto não encontrado'), t('Ele pode ter sido excluído em outra aba.'), el('a', { className: 'button secondary', href: '#/projects' }, t('Voltar aos projetos')))); return; }
  const stats = await projectStats(project.id);
  if (ctx.signal.aborted) return;
  root.append(el('a', { className: 'back-link', href: '#/projects' }, icon('back'), t('Todos os projetos')));
  const actions = el('div', { className: 'button-row' }, button(t('Editar'), () => openEditor('projects', project), { symbol: 'edit' }), button(t('Nova tarefa'), () => openEditor('tasks', {}, { projectId: project.id }), { symbol: 'plus', variant: 'primary' }));
  root.append(pageHeading(project.name, project.description || t('Suas tarefas, notas e ideias reunidas.'), actions));
  root.append(el('div', { className: 'project-summary' }, badge(t(projectStatuses[project.status]), 'blue'), el('span', {}, icon('clock'), formatDate(project.dueDate)), el('span', {}, tr`Última atividade: ${formatDate(project.lastActivityAt)}`), el('strong', {}, stats.total ? tr`${stats.progress}% concluído · ${stats.completed}/${stats.total} tarefas` : t('Sem tarefas'))));
  const tabs = el('div', { className: 'tabs', role: 'tablist', 'aria-label': t('Seções do projeto') });
  const content = el('div');
  let active = ctx.query.get('tab') || 'overview', generation = 0;
  for (const [value, label] of [['overview', t('Visão geral')], ['tasks', t('Tarefas')], ['notes', t('Notas')], ['boards', t('Quadros')]]) tabs.append(button(label, () => { active = value; render().catch(ctx.error); }, { variant: 'tab', role: 'tab', dataset: { tab: value } }));
  tabs.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const items = [...tabs.children];
    const index = items.indexOf(document.activeElement);
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
    items[next].focus(); items[next].click();
  }, { signal: ctx.signal });
  root.append(tabs, content);
  async function render() {
    const run = ++generation;
    for (const tab of tabs.children) { tab.classList.toggle('active', tab.dataset.tab === active); tab.setAttribute('aria-selected', tab.dataset.tab === active); tab.tabIndex = tab.dataset.tab === active ? 0 : -1; }
    content.replaceChildren();
    if (active === 'boards') {
      const links = [];
      await scan('boardLinks', item => links.push(item), { index: 'projectId', query: IDBKeyRange.only(project.id) });
      if (ctx.signal.aborted || run !== generation) return;
      content.append(sectionTitle(t('Quadros relacionados'), t('Abrir Notas Flutuantes'), `#/boards?project=${project.id}`));
      if (!links.length) content.append(emptyState('boards', t('Ideias precisam de espaço'), t('Abra um quadro e vincule-o a este projeto.'), el('a', { className: 'button primary', href: `#/boards?project=${project.id}` }, t('Abrir Quadros'))));
      else for (const link of links) content.append(el('a', { className: 'linked-board', href: `#/boards?board=${encodeURIComponent(link.id)}` }, icon('boards'), link.boardName, icon('arrow')));
      return;
    }
    for (const kind of active === 'overview' ? ['tasks', 'notes'] : [active]) {
      const result = await page(kind, { filter: record => record.projectId === project.id, limit: active === 'overview' ? 6 : 50 });
      if (ctx.signal.aborted || run !== generation) return;
      const section = el('section', { className: 'panel section-space' });
      section.append(sectionTitle(kind === 'tasks' ? t('Tarefas') : t('Notas'), t('Ver todas'), `#/${kind}?project=${project.id}`));
      if (!result.records.length) section.append(emptyState(kind, kind === 'tasks' ? t('Qual é o primeiro passo?') : t('Guarde o contexto do projeto'), t('Tudo o que você criar aqui ficará relacionado a este projeto.'), button(kind === 'tasks' ? t('Criar tarefa') : t('Criar nota'), () => openEditor(kind, {}, { projectId: project.id }), { symbol: 'plus' })));
      else section.append(el('div', { className: kind === 'notes' ? 'note-grid padded' : '' }, result.records.map(record => kind === 'tasks' ? taskRow(record, project) : noteCard(record, project))));
      content.append(section);
    }
    if (active === 'overview') content.append(el('div', { className: 'project-management' }, button(project.status === 'archived' ? t('Reativar projeto') : t('Arquivar projeto'), () => save('projects', { ...project, status: project.status === 'archived' ? 'active' : 'archived' })), button(t('Excluir projeto'), async () => {
      let notes = 0;
      await scan('notes', () => { notes++; }, { index: 'projectId', query: IDBKeyRange.only(project.id) });
      if (await confirmAction(t('Excluir projeto?'), tr`${stats.total} tarefa(s) e ${notes} nota(s) serão preservadas e ficarão sem projeto. Vínculos de quadros serão removidos; os quadros continuarão intactos.`, { label: t('Excluir projeto'), danger: true })) { await remove('projects', project); ctx.navigate('/projects'); toast(t('Projeto excluído. Seus itens foram preservados.')); }
    }, { variant: 'text danger-text', symbol: 'trash' })));
  }
  await render();
}
