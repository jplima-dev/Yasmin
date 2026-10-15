import { transaction, request, get, scan, page, walk, STORES } from '../storage/database.js';
import { normalizeEntity, taskTransition, searchEntry, entityNames, ConflictError, ValidationError } from '../domain/models.js';
import { compareTasks } from '../utils/dates.js';

export { get, scan, page };
export const changes = new EventTarget();
let channel;
if (typeof window !== 'undefined' && typeof BroadcastChannel !== 'undefined') {
  channel = new BroadcastChannel('organizador:changes');
  channel.onmessage = event => changes.dispatchEvent(new CustomEvent('change', { detail: { ...event.data, external: true } }));
}

export function announce(detail = {}) {
  changes.dispatchEvent(new CustomEvent('change', { detail }));
  channel?.postMessage(detail);
}

export async function bumpRevision(tx) {
  const store = tx.objectStore('meta');
  const current = await request(store.get('revision'));
  store.put({ key: 'revision', value: (current?.value || 0) + 1 });
}

function addActivity(tx, kind, entity, action, now) {
  const words = { created: 'criado', updated: 'atualizado', deleted: 'excluído', completed: 'concluído', reopened: 'reaberto', postponed: 'adiado' };
  const actionLabel = kind === 'projects' ? words[action] : words[action].replace(/o$/, 'a');
  tx.objectStore('activities').put({
    id: crypto.randomUUID(), type: `${kind}.${action}`, entityType: kind, entityId: entity.id,
    projectId: kind === 'projects' ? entity.id : entity.projectId,
    label: `${entityNames[kind]} ${actionLabel}: ${entity.name || entity.title}`,
    occurredAt: now,
  });
}

async function touchProjects(tx, projectIds, now) {
  for (const id of new Set(projectIds.filter(Boolean))) {
    const store = tx.objectStore('projects');
    const project = await request(store.get(id));
    if (project) store.put({ ...project, lastActivityAt: now, revision: project.revision + 1 });
  }
}

export async function save(kind, input) {
  const clean = normalizeEntity(kind, input);
  const now = new Date().toISOString();
  const id = input.id || crypto.randomUUID();
  const result = await transaction(STORES, 'readwrite', async tx => {
    const store = tx.objectStore(kind);
    const before = input.id ? await request(store.get(id)) : null;
    if (input.id && (!before || input.revision !== before.revision)) throw new ConflictError();
    if (clean.projectId && !await request(tx.objectStore('projects').get(clean.projectId))) throw new ValidationError('O projeto vinculado não existe mais. Escolha outro projeto.');
    const record = { ...clean, id, createdAt: before?.createdAt || now, updatedAt: now, revision: (before?.revision || 0) + 1 };
    if (kind === 'projects') record.lastActivityAt = now;
    if (kind === 'tasks') Object.assign(record, taskTransition(before, clean, now));
    store.put(record);
    tx.objectStore('searchEntries').put(searchEntry(kind, record));
    let action = before ? 'updated' : 'created';
    if (kind === 'tasks' && before) {
      if (before.status !== 'completed' && record.status === 'completed') action = 'completed';
      else if (before.status === 'completed' && record.status !== 'completed') action = 'reopened';
      else if (record.postponementCount > before.postponementCount) action = 'postponed';
    }
    addActivity(tx, kind, record, action, now);
    if (kind !== 'projects') await touchProjects(tx, [before?.projectId, record.projectId], now);
    await bumpRevision(tx);
    return record;
  });
  announce({ kind, id });
  return result;
}

export async function remove(kind, record) {
  await transaction(STORES, 'readwrite', async tx => {
    const current = await request(tx.objectStore(kind).get(record.id));
    if (!current || current.revision !== record.revision) throw new ConflictError();
    const now = new Date().toISOString();
    if (kind === 'projects') {
      for (const childKind of ['tasks', 'notes']) {
        await walk(tx.objectStore(childKind).index('projectId'), child => {
          const unlinked = { ...child, projectId: null, updatedAt: now, revision: child.revision + 1 };
          tx.objectStore(childKind).put(unlinked);
          tx.objectStore('searchEntries').put(searchEntry(childKind, unlinked));
        }, IDBKeyRange.only(record.id));
      }
      await walk(tx.objectStore('boardLinks').index('projectId'), (_, cursor) => cursor.delete(), IDBKeyRange.only(record.id));
    } else await touchProjects(tx, [current.projectId], now);
    tx.objectStore(kind).delete(record.id);
    tx.objectStore('searchEntries').delete(`${kind}:${record.id}`);
    addActivity(tx, kind, current, 'deleted', now);
    await bumpRevision(tx);
  });
  announce({ kind, id: record.id, deleted: true });
}

export async function projectOptions() {
  const results = [];
  await scan('projects', project => results.push({ id: project.id, name: project.name, color: project.color, status: project.status }));
  return results.sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
}

export async function projectStats(id) {
  let total = 0, completed = 0, next = null;
  await scan('tasks', task => {
    total++;
    if (task.status === 'completed') completed++;
    else if (!next || compareTasks(task, next) < 0) next = task;
  }, { index: 'projectId', query: IDBKeyRange.only(id) });
  return { total, completed, next, progress: total ? Math.round(completed / total * 100) : 0 };
}

export async function setBoardProject(boardId, boardName, projectId) {
  if (!boardId) throw new ValidationError('Selecione um quadro primeiro.');
  await transaction(['boardLinks', 'projects', 'meta'], 'readwrite', async tx => {
    if (projectId && !await request(tx.objectStore('projects').get(projectId))) throw new ValidationError('Projeto não encontrado.');
    if (projectId) tx.objectStore('boardLinks').put({ id: boardId, boardName, projectId });
    else tx.objectStore('boardLinks').delete(boardId);
    await bumpRevision(tx);
  });
  announce({ kind: 'boardLinks' });
}
