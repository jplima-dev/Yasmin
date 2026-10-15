import { t, tr } from '../../services/i18n.js';
import { el, pageHeading, button, emptyState, select, pager, confirmAction, toast, icon } from '../../components/ui.js';
import { noteCard, badge } from '../../components/records.js';
import { openEditor } from '../../components/entity-editor.js';
import { page, get, projectOptions, remove } from '../../services/data-service.js';
import { search } from '../../services/search-service.js';
import { formatDate } from '../../utils/dates.js';

export async function mount(root, ctx) {
  if (ctx.id) return detail(root, ctx);
  const projects = await projectOptions();
  if (ctx.signal.aborted) return;
  const projectMap = new Map(projects.map(project => [project.id, project]));
  const project = select([{ value: '', label: t('Todos os projetos') }, ...projects.map(p => ({ value: p.id, label: p.name }))], ctx.query.get('project') || '', { 'aria-label': t('Filtrar notas por projeto') });
  const query = el('input', { type: 'search', placeholder: t('Pesquisar nas notas…'), 'aria-label': t('Pesquisar nas notas') });
  const tag = el('input', { type: 'search', placeholder: t('Filtrar por tag…'), 'aria-label': t('Filtrar notas por tag') });
  root.append(pageHeading(t('Notas'), t('Um lugar para o que você aprende, pensa e quer lembrar.'), button(t('Nova nota'), () => openEditor('notes', {}, { projectId: project.value || null }), { variant: 'primary', symbol: 'plus' })));
  const grid = el('div', { className: 'note-grid' });
  const pagination = el('div');
  root.append(el('div', { className: 'filter-bar' }, query, project, tag), grid, pagination);
  let cursor = null, history = [], generation = 0, timeout, controller;
  async function render() {
    controller?.abort(); controller = new AbortController();
    const run = ++generation;
    const matches = note => (!project.value || note.projectId === project.value) && (!tag.value.trim() || note.tags.some(value => value.includes(tag.value.trim().toLowerCase())));
    let result;
    if (query.value.trim()) {
      const hits = await search(query.value, { kind: 'notes', signal: controller.signal });
      const records = (await Promise.all(hits.map(hit => get('notes', hit.entityId)))).filter(Boolean).filter(matches);
      result = { records, next: null };
    } else result = await page('notes', { after: cursor, filter: matches });
    if (ctx.signal.aborted || run !== generation) return;
    grid.replaceChildren(...result.records.map(note => noteCard(note, projectMap.get(note.projectId))));
    if (!result.records.length) grid.append(emptyState('notes', t('Sua próxima ideia começa aqui'), t('Escreva algo que você queira guardar ou ajuste os filtros para encontrar uma nota.'), button(t('Criar nota'), () => openEditor('notes', {}, { projectId: project.value || null }), { symbol: 'plus' })));
    pagination.replaceChildren(query.value.trim() ? el('small', { className: 'muted' }, t('Até 50 resultados por pesquisa.')) : pager(result.next, history, direction => { if (direction === 'next') { history.push(cursor); cursor = result.next; } else cursor = history.pop(); return render(); }));
  }
  for (const control of [query, tag, project]) control.addEventListener(control === project ? 'change' : 'input', () => { clearTimeout(timeout); timeout = setTimeout(() => { cursor = null; history = []; render().catch(ctx.error); }, 150); }, { signal: ctx.signal });
  ctx.setDataRefresh(detail => {
    if (detail.kind !== 'notes') return false;
    return render().then(() => true);
  });
  await render();
  return () => { clearTimeout(timeout); controller?.abort(); };
}

async function detail(root, ctx) {
  const note = await get('notes', ctx.id);
  if (!note) { root.append(emptyState('notes', t('Nota não encontrada'), t('Ela pode ter sido excluída em outra aba.'), el('a', { className: 'button secondary', href: '#/notes' }, t('Voltar às notas')))); return; }
  const project = note.projectId ? await get('projects', note.projectId) : null;
  if (ctx.signal.aborted) return;
  root.append(el('a', { className: 'back-link', href: '#/notes' }, icon('back'), t('Todas as notas')));
  root.append(pageHeading(note.title, tr`Atualizada em ${formatDate(note.updatedAt, { year: 'numeric' })}`, el('div', { className: 'button-row' }, button(t('Excluir'), async () => {
    if (await confirmAction(t('Excluir nota?'), t('O texto desta nota será removido do painel.'), { label: t('Excluir nota'), danger: true })) { await remove('notes', note); ctx.navigate('/notes'); toast(t('Nota excluída.')); }
  }, { symbol: 'trash' }), button(t('Editar nota'), () => openEditor('notes', note), { variant: 'primary', symbol: 'edit' }))));
  root.append(el('div', { className: 'tag-row section-space' }, project && el('a', { href: `#/projects/${project.id}` }, badge(project.name, 'blue')), note.tags.map(tag => badge(`#${tag}`)), badge(note.format === 'markdown' ? t('Markdown · texto') : t('Texto simples'))));
  root.append(el('article', { className: `note-reader ${note.format === 'markdown' ? 'monospace' : ''}` }, note.body || t('Esta nota está em branco. Clique em Editar nota para começar.')));
}
