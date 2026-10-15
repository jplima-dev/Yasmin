export const entityTypes = ['projects', 'tasks', 'notes'];
export const projectStatuses = { planning: 'Planejando', active: 'Ativo', paused: 'Pausado', completed: 'Concluído', archived: 'Arquivado' };
export const taskStatuses = { pending: 'A fazer', in_progress: 'Em andamento', completed: 'Concluída' };
export const priorities = { low: 'Baixa', normal: 'Normal', high: 'Alta', urgent: 'Urgente' };
export const entityNames = { projects: 'Projeto', tasks: 'Tarefa', notes: 'Nota' };

export class ValidationError extends Error {}
export class ConflictError extends Error {
  constructor() { super('Este item mudou em outra aba. Seu texto foi preservado; copie suas alterações e reabra o item para comparar.'); }
}

export function normalizeText(value = '') {
  return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').replace(/\s+/g, ' ').trim();
}

function text(value, field, maximum, required = false) {
  if (typeof value !== 'string') throw new ValidationError(`${field}: texto inválido.`);
  const result = value.trim();
  if (required && !result) throw new ValidationError(`Preencha ${field.toLowerCase()}.`);
  if (result.length > maximum) throw new ValidationError(`${field}: limite de ${maximum.toLocaleString('pt-BR')} caracteres.`);
  return result;
}

export function civilDate(value) {
  if (value === null || value === '' || value === undefined) return null;
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new ValidationError('Data inválida.');
  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(`${value}T12:00:00Z`);
  if (year < 1000 || year > 9999 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) throw new ValidationError('Data inválida.');
  return value;
}

export function tags(value = []) {
  const items = typeof value === 'string' ? value.split(',') : value;
  if (!Array.isArray(items) || items.length > 30) throw new ValidationError('Use até 30 tags.');
  return [...new Set(items.map(item => text(item, 'Tag', 40).toLocaleLowerCase('pt-BR')).filter(Boolean))];
}

export function normalizeEntity(kind, input) {
  if (!entityTypes.includes(kind)) throw new ValidationError('Tipo de item inválido.');
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new ValidationError('Registro inválido.');
  if (kind === 'projects') {
    const status = input.status || 'active';
    if (!Object.hasOwn(projectStatuses, status)) throw new ValidationError('Status de projeto inválido.');
    const color = input.color || '#5576e8';
    if (!/^#[0-9a-f]{6}$/i.test(color)) throw new ValidationError('Cor inválida.');
    return {
      name: text(input.name ?? '', 'Nome', 200, true), description: text(input.description ?? '', 'Descrição', 10000),
      status, color, icon: text(input.icon || 'folder', 'Ícone', 30), dueDate: civilDate(input.dueDate),
    };
  }
  const base = {
    title: text(input.title ?? '', 'Título', 200, true),
    projectId: input.projectId || null,
    tags: tags(input.tags),
  };
  if (base.projectId !== null && typeof base.projectId !== 'string') throw new ValidationError('Projeto inválido.');
  if (kind === 'notes') {
    const format = input.format || 'plain';
    if (!['plain', 'markdown'].includes(format)) throw new ValidationError('Formato de nota inválido.');
    return { ...base, body: text(input.body ?? '', 'Texto', 200000), format };
  }
  const status = input.status || 'pending';
  const priority = input.priority || 'normal';
  if (!Object.hasOwn(taskStatuses, status) || !Object.hasOwn(priorities, priority)) throw new ValidationError('Status ou prioridade inválidos.');
  const subtasks = input.subtasks ?? [];
  if (!Array.isArray(subtasks) || subtasks.length > 100) throw new ValidationError('Use até 100 subtarefas.');
  const seen = new Set();
  return {
    ...base, description: text(input.description ?? '', 'Descrição', 10000), status, priority,
    dueDate: civilDate(input.dueDate),
    subtasks: subtasks.map(subtask => {
      const id = subtask.id || crypto.randomUUID();
      if (typeof id !== 'string' || seen.has(id)) throw new ValidationError('Subtarefa inválida ou repetida.');
      seen.add(id);
      return { id, title: text(subtask.title ?? '', 'Subtarefa', 200, true), completed: Boolean(subtask.completed) };
    }),
  };
}

export function taskTransition(before, after, now) {
  return {
    completedAt: after.status === 'completed' ? (before?.status === 'completed' ? before.completedAt : now) : null,
    postponementCount: (before?.postponementCount || 0) + (before?.dueDate && after.dueDate && after.dueDate > before.dueDate ? 1 : 0),
  };
}

export function searchEntry(kind, record) {
  return {
    key: `${kind}:${record.id}`, entityType: kind, entityId: record.id,
    title: record.name || record.title, titleNormalized: normalizeText(record.name || record.title),
    tagsNormalized: normalizeText((record.tags || []).join(' ')),
    textNormalized: normalizeText([record.name, record.title, record.description, record.body, ...(record.tags || [])].filter(Boolean).join(' ')),
    updatedAt: record.updatedAt,
  };
}
