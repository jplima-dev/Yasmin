import { t, tr, errorText } from '../services/i18n.js';
import { el, field, select, modal, button, iconButton, toast, confirmAction } from './ui.js';
import { projectStatuses, taskStatuses, priorities } from '../domain/models.js';
import { save, projectOptions } from '../services/data-service.js';

export async function openEditor(kind, existing = {}, defaults = {}) {
  const record = { ...defaults, ...existing };
  const isProject = kind === 'projects';
  const isNote = kind === 'notes';
  const noun = isProject ? t('projeto') : isNote ? t('nota') : t('tarefa');
  const projects = isProject ? [] : await projectOptions();
  const box = modal(`${existing.id ? t('Editar') : isProject ? t('Novo') : t('Nova')} ${noun}`, { wide: isNote });
  const form = el('form', { className: 'entity-form' });
  const errorBox = el('p', { className: 'form-error', role: 'alert', hidden: true });
  const name = el('input', { type: 'text', name: isProject ? 'name' : 'title', value: record.name || record.title || '', maxLength: 200, required: true, placeholder: isProject ? t('Ex.: Meu portfólio') : isNote ? t('Dê um título à sua ideia') : t('O que precisa ser feito?') });
  form.append(field(isProject ? t('Nome do projeto') : t('Título'), name));
  const description = el('textarea', { name: isNote ? 'body' : 'description', rows: isNote ? 13 : 3, maxLength: isNote ? 200000 : 10000, placeholder: isNote ? t('Escreva livremente. Texto, listas e trechos de código…') : t('Adicione um pouco de contexto…'), value: record.body || record.description || '' });
  form.append(field(isNote ? t('Texto da nota') : t('Descrição'), description));
  const controls = {};
  const pair = el('div', { className: 'form-grid' });
  if (!isProject) {
    controls.projectId = select([{ value: '', label: t('Sem projeto') }, ...projects.map(project => ({ value: project.id, label: project.name }))], record.projectId || '');
    pair.append(field(t('Projeto'), controls.projectId));
    controls.tags = el('input', { value: (record.tags || []).join(', '), placeholder: t('estudos, trabalho…') });
    pair.append(field('Tags', controls.tags, t('Separe por vírgula.')));
  }
  if (!isNote) {
    controls.status = select(Object.entries(isProject ? projectStatuses : taskStatuses).map(([value, label]) => ({ value, label: t(label) })), record.status || (isProject ? 'active' : 'pending'));
    pair.append(field('Status', controls.status));
    controls.dueDate = el('input', { type: 'date', value: record.dueDate || '', min: '1000-01-01', max: '9999-12-31' });
    pair.append(field(t('Prazo'), controls.dueDate));
    if (!isProject) {
      controls.priority = select(Object.entries(priorities).map(([value, label]) => ({ value, label: t(label) })), record.priority || 'normal');
      pair.append(field(t('Prioridade'), controls.priority));
    } else {
      controls.color = el('input', { type: 'color', value: record.color || '#5576e8' });
      pair.append(field(t('Cor do projeto'), controls.color));
    }
  } else {
    controls.format = select([{ value: 'plain', label: t('Texto simples') }, { value: 'markdown', label: t('Markdown (edição em texto)') }], record.format || 'plain');
    pair.append(field(t('Formato'), controls.format));
  }
  form.append(pair);
  let dirty = false, saving = false;
  const subtasks = (record.subtasks || []).map(item => ({ ...item }));
  if (kind === 'tasks') {
    const sublist = el('div', { className: 'subtask-list' });
    const renderSubtasks = () => {
      sublist.replaceChildren(...subtasks.map((subtask, index) => el('div', { className: 'subtask-input' },
        el('input', { type: 'checkbox', checked: subtask.completed, 'aria-label': tr`Concluir subtarefa ${index + 1}`, onChange: event => { subtask.completed = event.target.checked; dirty = true; } }),
        el('input', { value: subtask.title, required: true, maxLength: 200, placeholder: t('Uma pequena etapa'), 'aria-label': tr`Subtarefa ${index + 1}`, onInput: event => { subtask.title = event.target.value; } }),
        iconButton(t('Remover subtarefa'), 'close', () => { subtasks.splice(index, 1); dirty = true; renderSubtasks(); }),
      )));
    };
    renderSubtasks();
    form.append(el('div', { className: 'form-field' }, el('span', { className: 'field-label' }, t('Subtarefas')), sublist, button(t('Adicionar etapa'), () => { if (subtasks.length >= 100) return; subtasks.push({ id: crypto.randomUUID(), title: '', completed: false }); dirty = true; renderSubtasks(); sublist.lastElementChild.querySelector('input[type="text"], input:not([type])')?.focus(); }, { variant: 'text', symbol: 'plus' })));
  }
  const saveButton = button(t('Salvar'), () => form.requestSubmit(), { variant: 'primary' });
  box.body.append(form, errorBox);
  box.footer.append(button(t('Cancelar'), box.close), saveButton);
  form.addEventListener('input', () => { dirty = true; });
  box.setBeforeClose(async () => !saving && (!dirty || await confirmAction(t('Descartar alterações?'), t('Seu texto ainda não foi salvo. Você pode voltar para continuar editando.'), { label: t('Descartar alterações'), danger: true })));
  const unload = event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
  window.addEventListener('beforeunload', unload);
  box.dialog.addEventListener('close', () => window.removeEventListener('beforeunload', unload), { once: true });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving) return;
    saving = true; saveButton.disabled = true; saveButton.textContent = t('Salvando…'); errorBox.hidden = true;
    try {
      const input = { ...record, [isProject ? 'name' : 'title']: name.value, [isNote ? 'body' : 'description']: description.value };
      for (const [key, control] of Object.entries(controls)) input[key] = control.value;
      if (kind === 'tasks') input.subtasks = subtasks;
      await save(kind, input);
      dirty = false; saving = false; box.close(); toast(`${isProject ? t('Projeto salvo') : isNote ? t('Nota salva') : t('Tarefa salva')}.`);
    } catch (error) {
      errorBox.textContent = errorText(error); errorBox.hidden = false; errorBox.focus();
    } finally { saving = false; saveButton.disabled = false; saveButton.textContent = t('Salvar'); }
  });
  name.focus();
  return box;
}
