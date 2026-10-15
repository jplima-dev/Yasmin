import { t, tr } from '../services/i18n.js';
import { el, icon, iconButton, button, confirmAction, toast } from './ui.js';
import { openEditor } from './entity-editor.js';
import { priorities, projectStatuses } from '../domain/models.js';
import { save, remove } from '../services/data-service.js';
import { today, formatDate } from '../utils/dates.js';

export function badge(text, tone = 'neutral') { return el('span', { className: `badge ${tone}` }, text); }

export function taskRow(task, project, { compact = false } = {}) {
  const overdue = task.status !== 'completed' && task.dueDate && task.dueDate < today();
  const check = el('input', { type: 'checkbox', checked: task.status === 'completed', dataset: { focusKey: `task-toggle:${task.id}` }, 'aria-label': `${task.status === 'completed' ? t('Reabrir') : t('Concluir')} ${task.title}`, onChange: async event => {
    event.target.disabled = true;
    try { await save('tasks', { ...task, status: event.target.checked ? 'completed' : 'pending' }); }
    catch (error) { event.target.checked = task.status === 'completed'; throw error; }
    finally { event.target.disabled = false; }
  } });
  return el('div', { className: `task-row ${task.status === 'completed' ? 'done' : ''}` },
    check,
    el('div', { className: 'task-info' }, el('button', { className: 'title-button', dataset: { focusKey: `task-edit:${task.id}` }, onClick: () => openEditor('tasks', task) }, task.title), el('div', { className: 'item-meta' }, project && el('span', {}, el('i', { className: 'color-dot', style: { backgroundColor: project.color } }), project.name), task.subtasks.length > 0 && el('span', {}, tr`${task.subtasks.filter(s => s.completed).length}/${task.subtasks.length} etapas`))),
    el('div', { className: 'task-tail' }, !compact && badge(t(priorities[task.priority]), task.priority === 'urgent' || task.priority === 'high' ? 'orange' : 'neutral'), task.dueDate && el('span', { className: `date-label ${overdue ? 'overdue' : ''}` }, task.dueDate === today() ? t('Hoje') : formatDate(task.dueDate))),
    !compact && iconButton(tr`Excluir ${task.title}`, 'trash', async () => {
      if (await confirmAction(t('Excluir tarefa?'), t('Esta ação remove a tarefa e suas subtarefas.'), { label: t('Excluir tarefa'), danger: true })) { await remove('tasks', task); toast(t('Tarefa excluída.')); }
    }, { dataset: { focusKey: `task-delete:${task.id}` } }),
  );
}

export function projectCard(project, stats) {
  return el('a', { className: 'project-card', href: `#/projects/${project.id}` },
    el('div', { className: 'project-card-top' }, el('span', { className: 'project-symbol', style: { color: project.color, backgroundColor: `${project.color}16` } }, icon('projects')), badge(t(projectStatuses[project.status]), project.status === 'active' ? 'blue' : 'neutral')),
    el('h3', {}, project.name),
    el('p', { className: 'project-description' }, project.description || t('Um espaço para suas próximas conquistas.')),
    el('div', { className: 'progress-label' }, el('span', {}, stats.total ? tr`${stats.completed} de ${stats.total} tarefas` : t('Sem tarefas')), el('strong', {}, stats.total ? `${stats.progress}%` : '—')),
    el('div', { className: 'progress-track' }, el('div', { className: 'progress-fill', style: { width: `${stats.progress}%`, backgroundColor: project.color } })),
    el('div', { className: 'project-card-foot' }, el('span', {}, icon('clock'), project.dueDate ? formatDate(project.dueDate) : t('Sem prazo')), icon('arrow')),
    stats.next && el('small', { className: 'project-next' }, tr`Próxima: ${stats.next.title}`),
  );
}

export function noteCard(note, project) {
  return el('a', { className: 'note-card', href: `#/notes/${note.id}` }, el('div', { className: 'note-card-top' }, icon('notes'), el('small', { className: 'muted' }, formatDate(note.updatedAt))), el('h3', {}, note.title), el('p', { className: 'note-excerpt' }, note.body.slice(0, 200) || t('Esta nota ainda está em branco.')), el('div', { className: 'tag-row' }, project && badge(project.name, 'blue'), note.tags.slice(0, 3).map(tag => badge(`#${tag}`))));
}

export function sectionTitle(title, link, href) {
  return el('div', { className: 'section-title' }, el('h2', {}, title), link && el('a', { className: 'text-link', href }, link, icon('arrow')));
}
