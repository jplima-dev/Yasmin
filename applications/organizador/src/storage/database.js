export const DB_NAME = 'organizador-pessoal';
export const DB_VERSION = 1;
export const STORES = ['projects', 'tasks', 'notes', 'activities', 'searchEntries', 'boardLinks', 'meta'];
let connection;
let opening;

export function request(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// A different name may be supplied for an isolated verification connection.
// The application always uses the default name; a document owns one connection.
export function openDatabase(name = DB_NAME) {
  if (connection) return Promise.resolve(connection);
  if (opening) return opening;
  opening = new Promise((resolve, reject) => {
    const req = indexedDB.open(name, DB_VERSION);
    req.onblocked = () => {
      if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('database-blocked'));
    };
    req.onupgradeneeded = () => {
      const db = req.result;
      for (const name of STORES) {
        const store = db.createObjectStore(name, { keyPath: name === 'meta' || name === 'searchEntries' ? 'key' : 'id' });
        if (['projects', 'tasks', 'notes'].includes(name)) store.createIndex('updatedAt', 'updatedAt');
        if (['tasks', 'notes', 'boardLinks'].includes(name)) store.createIndex('projectId', 'projectId');
        if (['tasks', 'notes'].includes(name)) store.createIndex('tags', 'tags', { multiEntry: true });
        if (name === 'projects') {
          for (const key of ['status', 'lastActivityAt', 'dueDate']) store.createIndex(key, key);
        }
        if (name === 'tasks') {
          store.createIndex('statusDueDate', ['status', 'dueDate']);
          store.createIndex('projectStatus', ['projectId', 'status']);
          store.createIndex('completedAt', 'completedAt');
        }
        if (name === 'activities') {
          store.createIndex('occurredAt', 'occurredAt');
          store.createIndex('projectTime', ['projectId', 'occurredAt']);
        }
        if (name === 'searchEntries') store.createIndex('entityType', 'entityType');
      }
      req.transaction.objectStore('meta').put({ key: 'revision', value: 0 });
      req.transaction.objectStore('meta').put({ key: 'datasetId', value: crypto.randomUUID() });
    };
    req.onsuccess = () => {
      connection = req.result;
      connection.onversionchange = () => {
        connection.close(); connection = undefined; opening = undefined;
        if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('database-versionchange'));
      };
      resolve(connection);
    };
    req.onerror = () => { opening = undefined; reject(req.error); };
  });
  return opening;
}

export async function transaction(names, mode, action) {
  const db = await openDatabase();
  const tx = db.transaction(names, mode);
  const done = new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onabort = () => reject(tx.error || new Error('Transação cancelada. Os dados anteriores foram preservados.'));
    tx.onerror = () => {}; // Request errors abort the transaction; onabort is the final outcome.
  });
  done.catch(() => {});
  try {
    const result = await action(tx);
    await done;
    return result;
  } catch (error) {
    try { tx.abort(); } catch { /* transaction already settled */ }
    await done.catch(() => {});
    throw error;
  }
}

export async function get(kind, id) {
  return transaction([kind], 'readonly', tx => request(tx.objectStore(kind).get(id)));
}

export function walk(source, visitor, query = null, direction = 'next') {
  return new Promise((resolve, reject) => {
    const req = source.openCursor(query, direction);
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const cursor = req.result;
      if (!cursor) return resolve();
      try {
        if (visitor(cursor.value, cursor) === false) resolve();
        else cursor.continue();
      } catch (error) { reject(error); }
    };
  });
}

export async function scan(kind, visitor, { index, query, direction = 'next' } = {}) {
  return transaction([kind], 'readonly', tx => {
    const store = tx.objectStore(kind);
    return walk(index ? store.index(index) : store, visitor, query, direction);
  });
}

export async function page(kind, { filter = () => true, after = null, limit = 50, index = 'updatedAt', direction = 'prev' } = {}) {
  const records = [];
  let next = null;
  let lastIncluded;
  const range = after ? (direction === 'prev' ? IDBKeyRange.upperBound(after.key) : IDBKeyRange.lowerBound(after.key)) : null;
  await scan(kind, (record, cursor) => {
    if (after && indexedDB.cmp(cursor.key, after.key) === 0 && (direction === 'prev' ? indexedDB.cmp(cursor.primaryKey, after.id) >= 0 : indexedDB.cmp(cursor.primaryKey, after.id) <= 0)) return;
    if (!filter(record)) return;
    if (records.length === limit) { next = lastIncluded; return false; }
    records.push(record);
    lastIncluded = { key: cursor.key, id: cursor.primaryKey };
  }, { index, direction, query: range });
  return { records, next };
}

export async function currentRevision() {
  return (await get('meta', 'revision'))?.value || 0;
}

export function closeDatabase() {
  connection?.close(); connection = undefined; opening = undefined;
}
