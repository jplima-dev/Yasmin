import { t } from '../../services/i18n.js';
import { el, pageHeading, button, select, emptyState, pager } from '../../components/ui.js';
import { openEditor } from '../../components/entity-editor.js';
import { taskRow } from '../../components/records.js';
import { page, projectOptions, get } from '../../services/data-service.js';
import { taskMatches } from '../../utils/dates.js';
import { priorities } from '../../domain/models.js';

export async function mount(root, ctx) {
  const projects = await projectOptions();
  if (ctx.signal.aborted) return;
  const projectMap = new Map(projects.map(project => [project.id, project]));
  const project = select([{ value: '', label: t('Todos os projetos') }, { value: 'none', label: t('Sem projeto') }, ...projects.map(p => ({ value: p.id, label: p.name }))], ctx.query.get('project') || '', { 'aria-label': t('Filtrar tarefas por projeto') });
  const priority = select([{ value: '', label: t('Todas as prioridades') }, ...Object.entries(priorities).map(([value, label]) => ({ value, label: t(label) }))], ctx.query.get('priority') || '', { 'aria-label': t('Filtrar por prioridade') });
  const tag = el('input', { type: 'search', value: ctx.query.get('tag') || '', placeholder: t('Filtrar por tag…'), 'aria-label': t('Filtrar tarefas por tag') });
  root.append(pageHeading(t('Tarefas'), t('Um passo de cada vez. O que vamos fazer hoje?'), button(t('Nova tarefa'), () => openEditor('tasks', {}, { projectId: project.value && project.value !== 'none' ? project.value : null }), { variant: 'primary', symbol: 'plus' })));
  const tabs = el('div', { className: 'tabs', 'aria-label': t('Visualizações de tarefas') });
  let filter = ctx.query.get('filter') || 'all';
  const list = el('div', { className: 'panel task-list' });
  const pagination = el('div');
  let cursor = null, history = [], generation = 0, timeout;
  function reset() {
    cursor = null; history = [];
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries({ filter, project: project.value, priority: priority.value, tag: tag.value })) if (value) params.set(key, value);
    historyReplace(params);
    return render();
  }
  function historyReplace(params) { window.history.replaceState(null, '', `#/tasks?${params}`); }
  for (const [value, label] of [['all', t('Todas')], ['today', t('Hoje')], ['upcoming', t('Próximas')], ['overdue', t('Atrasadas')], ['completed', t('Concluídas')]]) tabs.append(button(label, () => { filter = value; return reset(); }, { variant: 'tab', dataset: { filter: value } }));
  root.append(tabs, el('div', { className: 'filter-bar' }, project, priority, tag), list, pagination);
  async function render() {
    const run = ++generation;
    for (const tab of tabs.children) { tab.classList.toggle('active', tab.dataset.filter === filter); tab.setAttribute('aria-pressed', tab.dataset.filter === filter); }
    const result = await page('tasks', { after: cursor, filter: task => taskMatches(task, filter) && (!project.value || (project.value === 'none' ? !task.projectId : task.projectId === project.value)) && (!priority.value || task.priority === priority.value) && (!tag.value.trim() || task.tags.some(value => value.includes(tag.value.trim().toLowerCase()))) });
    if (ctx.signal.aborted || run !== generation) return;
    list.replaceChildren(...result.records.map(task => taskRow(task, projectMap.get(task.projectId))));
    if (!result.records.length) list.append(emptyState('tasks', filter === 'completed' ? t('Cada passo conta') : t('Tudo tranquilo por aqui'), filter === 'completed' ? t('Suas tarefas concluídas aparecerão nesta lista.') : t('Não há tarefas nesta visualização. Crie uma nova ou ajuste os filtros.'), button(t('Criar tarefa'), () => openEditor('tasks', {}, { projectId: project.value && project.value !== 'none' ? project.value : null }), { symbol: 'plus' })));
    pagination.replaceChildren(pager(result.next, history, direction => { if (direction === 'next') { history.push(cursor); cursor = result.next; } else cursor = history.pop(); return render(); }));
  }
  for (const control of [project, priority]) control.addEventListener('change', () => reset().catch(ctx.error), { signal: ctx.signal });
  tag.addEventListener('input', () => { clearTimeout(timeout); timeout = setTimeout(() => reset().catch(ctx.error), 150); }, { signal: ctx.signal });
  ctx.setDataRefresh(detail => {
    if (detail.kind !== 'tasks') return false;
    return render().then(() => true);
  });
  await render();
  if (ctx.id) { const task = await get('tasks', ctx.id); if (!ctx.signal.aborted) { if (task) { await openEditor('tasks', task); ctx.navigate('/tasks'); } else ctx.error(new Error(t('Tarefa não encontrada.'))); } }
  return () => clearTimeout(timeout);
}
