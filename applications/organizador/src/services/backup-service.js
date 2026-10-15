import { transaction, request, walk, STORES, currentRevision } from '../storage/database.js';
import { normalizeEntity, searchEntry, ValidationError, ConflictError } from '../domain/models.js';
import { announce, bumpRevision } from './data-service.js';

export const BACKUP_LIMIT = 50 * 1024 * 1024;
export const collections = ['projects', 'tasks', 'notes', 'activities', 'boardLinks'];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const actions = ['created', 'updated', 'deleted', 'completed', 'reopened', 'postponed'];
function ensure(condition, message) { if (!condition) throw new ValidationError(message); }
function instant(value) { ensure(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && !Number.isNaN(Date.parse(value)), 'Data de registro inválida no backup.'); return value; }
function shortText(value, max = 500) { ensure(typeof value === 'string' && value.length <= max, 'Texto inválido no backup.'); return value; }

export function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stable(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

export function validateBackup(input) {
  ensure(input && input.format === 'organizador-pessoal' && input.formatVersion === 1, 'Formato de backup não reconhecido ou versão incompatível. Use um backup do painel; os Quadros têm importação própria.');
  const data = {};
  for (const kind of collections) {
    ensure(Array.isArray(input.data?.[kind]), `Coleção ${kind} ausente ou inválida.`);
    const ids = new Set();
    data[kind] = input.data[kind].map(item => {
      ensure(item && typeof item.id === 'string' && !ids.has(item.id), `ID inválido ou repetido em ${kind}.`);
      ids.add(item.id);
      if (kind === 'boardLinks') return { id: shortText(item.id, 200), boardName: shortText(item.boardName, 200), projectId: shortText(item.projectId, 100) };
      ensure(uuid.test(item.id), `ID inválido em ${kind}.`);
      if (kind === 'activities') {
        ensure(['projects', 'tasks', 'notes'].includes(item.entityType) && actions.some(action => item.type === `${item.entityType}.${action}`), 'Atividade inválida.');
        ensure(typeof item.entityId === 'string' && uuid.test(item.entityId), 'Referência de atividade inválida.');
        ensure(item.projectId === null || typeof item.projectId === 'string' && uuid.test(item.projectId), 'Projeto de atividade inválido.');
        return { id: item.id, type: item.type, entityType: item.entityType, entityId: item.entityId, projectId: item.projectId, label: shortText(item.label), occurredAt: instant(item.occurredAt) };
      }
      ensure(Number.isSafeInteger(item.revision) && item.revision > 0, 'Revisão inválida no backup.');
      const record = { ...normalizeEntity(kind, item), id: item.id, createdAt: instant(item.createdAt), updatedAt: instant(item.updatedAt), revision: item.revision };
      if (kind === 'projects') record.lastActivityAt = instant(item.lastActivityAt);
      if (kind === 'tasks') {
        ensure(Number.isSafeInteger(item.postponementCount) && item.postponementCount >= 0, 'Contador de adiamentos inválido.');
        ensure(record.status === 'completed' ? Boolean(item.completedAt) : item.completedAt === null, 'Data de conclusão incompatível com o status.');
        record.completedAt = item.completedAt === null ? null : instant(item.completedAt);
        record.postponementCount = item.postponementCount;
      }
      return record;
    });
  }
  const projectIds = new Set(data.projects.map(project => project.id));
  for (const kind of ['tasks', 'notes', 'boardLinks']) {
    for (const record of data[kind]) ensure(!record.projectId || projectIds.has(record.projectId), 'O backup contém vínculo com projeto inexistente. Nenhum dado foi alterado.');
  }
  return { format: 'organizador-pessoal', formatVersion: 1, appVersion: '0.1.0', exportedAt: instant(input.exportedAt), sourceDatasetId: shortText(input.sourceDatasetId, 100), data };
}

export async function snapshot() {
  return transaction([...collections, 'meta'], 'readonly', async tx => {
    const values = await Promise.all(collections.map(kind => request(tx.objectStore(kind).getAll())));
    const dataset = await request(tx.objectStore('meta').get('datasetId'));
    const revision = await request(tx.objectStore('meta').get('revision'));
    return {
      revision: revision.value,
      backup: { format: 'organizador-pessoal', formatVersion: 1, appVersion: '0.1.0', exportedAt: new Date().toISOString(), sourceDatasetId: dataset.value, data: Object.fromEntries(collections.map((kind, i) => [kind, values[i]])) },
    };
  });
}

export async function exportBackup() {
  const { backup } = await snapshot();
  const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
  ensure(blob.size <= BACKUP_LIMIT, 'Este backup ultrapassa o limite restaurável de 50 MiB desta versão. Os dados continuam intactos; amplie a capacidade antes de exportar esse volume.');
  return blob;
}

export async function parseBackup(file) {
  ensure(file.size <= BACKUP_LIMIT, 'O arquivo excede o limite de 50 MiB.');
  let parsed;
  try { parsed = JSON.parse(await file.text()); } catch { throw new ValidationError('Não foi possível ler o JSON. Verifique se o arquivo está completo.'); }
  return validateBackup(parsed);
}

export async function previewBackup(backup) {
  const { backup: local, revision } = await snapshot();
  const counts = { added: 0, identical: 0, conflicts: 0 };
  const conflicts = [];
  for (const kind of collections) {
    const current = new Map(local.data[kind].map(record => [record.id, record]));
    for (const record of backup.data[kind]) {
      const previous = current.get(record.id);
      if (!previous) counts.added++;
      else if (stable(previous) === stable(record)) counts.identical++;
      else { counts.conflicts++; if (conflicts.length < 50) conflicts.push({ kind, local: previous, incoming: record }); }
    }
  }
  return { counts, conflicts, revision };
}

export async function importBackup(input, { mode, conflictPolicy = 'local', expectedRevision }) {
  const backup = validateBackup(input);
  ensure(['merge', 'replace'].includes(mode) && ['local', 'incoming'].includes(conflictPolicy), 'Modo de importação inválido.');
  await transaction(STORES, 'readwrite', async tx => {
    const actual = await request(tx.objectStore('meta').get('revision'));
    if (actual.value !== expectedRevision) throw new ConflictError();
    const replaced = new Map();
    if (mode === 'replace') {
      for (const kind of ['projects', 'tasks', 'notes']) await walk(tx.objectStore(kind), record => replaced.set(`${kind}:${record.id}`, record));
      for (const kind of [...collections, 'searchEntries']) tx.objectStore(kind).clear();
    }
    for (const kind of collections) {
      const store = tx.objectStore(kind);
      for (const record of backup.data[kind]) {
        const previous = mode === 'replace' ? replaced.get(`${kind}:${record.id}`) : await request(store.get(record.id));
        if (mode === 'replace' || !previous || conflictPolicy === 'incoming') {
          // An imported overwrite must invalidate editors open on the old local revision.
          const next = previous && 'revision' in record && stable(previous) !== stable(record) ? { ...record, revision: Math.max(previous.revision, record.revision) + 1 } : record;
          store.put(next);
        }
      }
    }
    const projectIds = new Set(await request(tx.objectStore('projects').getAllKeys()));
    for (const kind of ['tasks', 'notes', 'boardLinks']) {
      await walk(tx.objectStore(kind), record => { ensure(!record.projectId || projectIds.has(record.projectId), 'Importação produziria um vínculo inválido.'); });
    }
    tx.objectStore('searchEntries').clear();
    for (const kind of ['projects', 'tasks', 'notes']) await walk(tx.objectStore(kind), record => tx.objectStore('searchEntries').put(searchEntry(kind, record)));
    await bumpRevision(tx);
  });
  announce({ imported: true });
  return currentRevision();
}
