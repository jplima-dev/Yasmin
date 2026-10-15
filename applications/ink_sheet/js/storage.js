(() => {
  const DB_NAME = 'planilha-studio';
  const DB_VERSION = 1;
  const STORE = 'projects';
  const createId = () => window.crypto?.randomUUID?.() || `sheet-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const clone = value => typeof structuredClone === 'function' ? structuredClone(value) : JSON.parse(JSON.stringify(value));

  function open() {
    return new Promise((resolve, reject) => {
      if (!('indexedDB' in window)) return reject(new Error('IndexedDB indisponível'));
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: 'id' });
          store.createIndex('updatedAt', 'updatedAt');
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function withStore(mode, action) {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const store = tx.objectStore(STORE);
      let request;
      try { request = action(store); } catch (error) { db.close(); reject(error); return; }
      tx.oncomplete = () => { db.close(); resolve(request?.result); };
      tx.onerror = () => { db.close(); reject(tx.error || request?.error); };
      tx.onabort = () => { db.close(); reject(tx.error || new Error('Transação cancelada')); };
    });
  }

  async function putProject(project) {
    const now = new Date().toISOString();
    const record = {
      ...project,
      id: project.id || createId(),
      title: project.title || project.state?.title || 'Minha planilha',
      createdAt: project.createdAt || now,
      updatedAt: now,
    };
    await withStore('readwrite', store => store.put(record));
    return record;
  }
  const getProject = async id => id ? (await withStore('readonly', store => store.get(id)) || null) : null;
  async function getAllProjects() {
    const items = await withStore('readonly', store => store.getAll()) || [];
    return items.sort((a,b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')));
  }
  async function deleteProject(id) { if (id) await withStore('readwrite', store => store.delete(id)); }
  async function renameProject(id, title) {
    const p = await getProject(id); if (!p) return null;
    p.title = title; if (p.state) p.state.title = title; return putProject(p);
  }
  async function duplicateProject(id) {
    const p = await getProject(id); if (!p) return null;
    const state = clone(p.state || {}); const title = `${p.title || 'Planilha'} (cópia)`; state.title = title;
    return putProject({ title, state });
  }

  window.SheetDB = { createId, clone, putProject, getProject, getAllProjects, deleteProject, renameProject, duplicateProject };
})();
