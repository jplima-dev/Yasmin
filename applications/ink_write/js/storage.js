(() => {
  const DB_NAME = 'inkwrite-studio';
  const DB_VERSION = 2;
  const DOCUMENT_STORE = 'documents';
  const VERSION_STORE = 'versions';
  const DRAFT_STORE = 'drafts';

  const FALLBACK_KEY = 'inkwrite-documents-v1';
  const FALLBACK_VERSIONS_KEY = 'inkwrite-versions-v1';
  const FALLBACK_DRAFTS_KEY = 'inkwrite-drafts-v1';
  const STORAGE_SETTINGS_KEY = 'inkwrite-storage-settings-v1';
  const DEFAULT_MAX_VERSIONS = 30;
  const DEFAULT_MAX_VERSION_STORAGE_MB = 25;

  const createId = () => window.crypto?.randomUUID?.() || `doc-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  function openDB() {
    return new Promise((resolve, reject) => {
      if (!('indexedDB' in window)) return reject(new Error('IndexedDB unavailable'));
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;

        if (!db.objectStoreNames.contains(DOCUMENT_STORE)) {
          const store = db.createObjectStore(DOCUMENT_STORE, { keyPath: 'id' });
          store.createIndex('updatedAt', 'updatedAt');
        }

        if (!db.objectStoreNames.contains(VERSION_STORE)) {
          const store = db.createObjectStore(VERSION_STORE, { keyPath: 'id' });
          store.createIndex('documentId', 'documentId');
          store.createIndex('createdAt', 'createdAt');
        }

        if (!db.objectStoreNames.contains(DRAFT_STORE)) {
          const store = db.createObjectStore(DRAFT_STORE, { keyPath: 'documentId' });
          store.createIndex('updatedAt', 'updatedAt');
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function withStore(storeName, mode, action) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, mode);
      const store = tx.objectStore(storeName);
      let request;
      try { request = action(store); }
      catch (error) { db.close(); reject(error); return; }
      tx.oncomplete = () => { const result = request?.result; db.close(); resolve(result); };
      tx.onerror = () => { const error = tx.error || request?.error; db.close(); reject(error); };
      tx.onabort = () => { const error = tx.error || new Error('Transaction aborted'); db.close(); reject(error); };
    });
  }

  function fallbackRead(key, fallback = []) {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || 'null');
      return parsed ?? fallback;
    } catch {
      return fallback;
    }
  }

  function fallbackWrite(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function normalize(doc = {}) {
    const now = new Date().toISOString();
    return {
      id: doc.id || createId(),
      title: doc.title?.trim() || 'Documento sem título',
      createdAt: doc.createdAt || now,
      updatedAt: doc.updatedAt || now,
      template: doc.template || 'blank',
      // Importante: string vazia é conteúdo válido. Não preencher documentos novos.
      content: doc.content ?? '',
      semantic: doc.semantic && [1, 2].includes(doc.semantic.schemaVersion) && Array.isArray(doc.semantic.blocks) ? structuredCloneSafe(doc.semantic) : null,
      settings: {
        paper: 'a4',
        orientation: 'portrait',
        margin: 'normal',
        customMargin: 72,
        pageColor: '#ffffff',
        lineHeight: '1.6',
        paragraphSpacing: 8,
        zoom: 90,
        accent: '#2563eb',
        uiTheme: 'light',
        templateStyle: 'default',
        ...(doc.settings || {})
      }
    };
  }

  function cloneDocumentPayload(doc = {}) {
    const normalized = normalize(doc);
    return {
      title: normalized.title,
      template: normalized.template,
      content: normalized.content,
      semantic: structuredCloneSafe(normalized.semantic),
      settings: structuredCloneSafe(normalized.settings)
    };
  }

  function structuredCloneSafe(value) {
    if (typeof structuredClone === 'function') {
      try { return structuredClone(value); } catch {}
    }
    return JSON.parse(JSON.stringify(value));
  }

  function documentFingerprint(doc = {}) {
    return JSON.stringify(cloneDocumentPayload(doc));
  }

  function getStorageSettings() {
    const saved = fallbackRead(STORAGE_SETTINGS_KEY, {});
    const maxVersions = Number.parseInt(saved?.maxVersions, 10);
    const maxVersionStorageMB = Number.parseInt(saved?.maxVersionStorageMB, 10);
    return {
      maxVersions: Number.isFinite(maxVersions)
        ? Math.min(100, Math.max(10, maxVersions))
        : DEFAULT_MAX_VERSIONS,
      maxVersionStorageMB: Number.isFinite(maxVersionStorageMB)
        ? Math.min(200, Math.max(5, maxVersionStorageMB))
        : DEFAULT_MAX_VERSION_STORAGE_MB
    };
  }

  function setStorageSettings(next = {}) {
    const current = getStorageSettings();
    const maxVersions = Number.parseInt(next.maxVersions ?? current.maxVersions, 10);
    const maxVersionStorageMB = Number.parseInt(next.maxVersionStorageMB ?? current.maxVersionStorageMB, 10);
    const settings = {
      maxVersions: Number.isFinite(maxVersions)
        ? Math.min(100, Math.max(10, maxVersions))
        : current.maxVersions,
      maxVersionStorageMB: Number.isFinite(maxVersionStorageMB)
        ? Math.min(200, Math.max(5, maxVersionStorageMB))
        : current.maxVersionStorageMB
    };
    fallbackWrite(STORAGE_SETTINGS_KEY, settings);
    return settings;
  }

  async function putDocument(doc) {
    const record = normalize({ ...doc, updatedAt: new Date().toISOString() });
    try {
      await withStore(DOCUMENT_STORE, 'readwrite', store => store.put(record));
    } catch {
      const items = fallbackRead(FALLBACK_KEY, []).filter(item => item.id !== record.id);
      items.push(record);
      fallbackWrite(FALLBACK_KEY, items);
    }
    return record;
  }

  async function getDocument(id) {
    if (!id) return null;
    try { return (await withStore(DOCUMENT_STORE, 'readonly', store => store.get(id))) || null; }
    catch { return fallbackRead(FALLBACK_KEY, []).find(item => item.id === id) || null; }
  }

  async function getAllDocuments() {
    let items;
    try { items = (await withStore(DOCUMENT_STORE, 'readonly', store => store.getAll())) || []; }
    catch { items = fallbackRead(FALLBACK_KEY, []); }
    return items.map(normalize).sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));
  }

  async function deleteDocument(id) {
    try { await withStore(DOCUMENT_STORE, 'readwrite', store => store.delete(id)); }
    catch { fallbackWrite(FALLBACK_KEY, fallbackRead(FALLBACK_KEY, []).filter(item => item.id !== id)); }

    const versions = await getVersions(id, 1000);
    await Promise.allSettled(versions.map(version => deleteVersion(version.id)));
    await deleteDraft(id);
  }

  async function renameDocument(id, title) {
    const doc = await getDocument(id);
    if (!doc) return null;
    doc.title = title?.trim() || doc.title;
    return putDocument(doc);
  }

  async function duplicateDocument(id) {
    const doc = await getDocument(id);
    if (!doc) return null;
    const copy = normalize({
      ...doc,
      id: createId(),
      title: `${doc.title} (cópia)`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    });
    return putDocument(copy);
  }

  function normalizeDraft(doc = {}) {
    const normalized = normalize(doc);
    return {
      documentId: normalized.id,
      title: normalized.title,
      template: normalized.template,
      content: normalized.content,
      semantic: structuredCloneSafe(normalized.semantic),
      settings: structuredCloneSafe(normalized.settings),
      createdAt: normalized.createdAt,
      updatedAt: new Date().toISOString()
    };
  }

  function putDraftSync(doc) {
    if (!doc?.id) return null;
    const draft = normalizeDraft(doc);
    const items = fallbackRead(FALLBACK_DRAFTS_KEY, []).filter(item => item.documentId !== draft.documentId);
    items.push(draft);
    fallbackWrite(FALLBACK_DRAFTS_KEY, items);
    return draft;
  }

  async function putDraft(doc) {
    const draft = normalizeDraft(doc);
    try { await withStore(DRAFT_STORE, 'readwrite', store => store.put(draft)); }
    catch { putDraftSync(doc); }
    return draft;
  }

  async function getDraft(documentId) {
    if (!documentId) return null;
    let indexed = null;
    try { indexed = (await withStore(DRAFT_STORE, 'readonly', store => store.get(documentId))) || null; }
    catch {}

    const emergency = fallbackRead(FALLBACK_DRAFTS_KEY, []).find(item => item.documentId === documentId) || null;
    if (!indexed) return emergency;
    if (!emergency) return indexed;
    return String(emergency.updatedAt || '').localeCompare(String(indexed.updatedAt || '')) > 0 ? emergency : indexed;
  }

  async function deleteDraft(documentId) {
    if (!documentId) return;
    try { await withStore(DRAFT_STORE, 'readwrite', store => store.delete(documentId)); }
    catch {}
    fallbackWrite(
      FALLBACK_DRAFTS_KEY,
      fallbackRead(FALLBACK_DRAFTS_KEY, []).filter(item => item.documentId !== documentId)
    );
  }

  function normalizeVersion(doc = {}, meta = {}) {
    const normalized = normalize(doc);
    const now = new Date().toISOString();
    return {
      id: createId(),
      documentId: normalized.id,
      createdAt: now,
      reason: meta.reason || 'autosave',
      label: String(meta.label || '').trim().slice(0, 80),
      title: normalized.title,
      template: normalized.template,
      content: normalized.content,
      semantic: structuredCloneSafe(normalized.semantic),
      settings: structuredCloneSafe(normalized.settings)
    };
  }

  async function getVersions(documentId, limit = 50) {
    if (!documentId) return [];
    let items;
    try {
      items = await withStore(VERSION_STORE, 'readonly', store => store.index('documentId').getAll(IDBKeyRange.only(documentId)));
    } catch {
      items = fallbackRead(FALLBACK_VERSIONS_KEY, []).filter(item => item.documentId === documentId);
    }
    return (items || [])
      .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)))
      .slice(0, Math.max(1, limit));
  }

  async function getVersion(id) {
    if (!id) return null;
    try { return (await withStore(VERSION_STORE, 'readonly', store => store.get(id))) || null; }
    catch { return fallbackRead(FALLBACK_VERSIONS_KEY, []).find(item => item.id === id) || null; }
  }

  async function deleteVersion(id) {
    if (!id) return;
    try { await withStore(VERSION_STORE, 'readwrite', store => store.delete(id)); }
    catch {}
    fallbackWrite(FALLBACK_VERSIONS_KEY, fallbackRead(FALLBACK_VERSIONS_KEY, []).filter(item => item.id !== id));
  }

  async function pruneVersions(documentId, maxVersions = getStorageSettings().maxVersions, maxStorageMB = getStorageSettings().maxVersionStorageMB) {
    const safeLimit = Math.min(100, Math.max(10, Number.parseInt(maxVersions, 10) || DEFAULT_MAX_VERSIONS));
    const safeBytes = Math.min(200, Math.max(5, Number.parseInt(maxStorageMB, 10) || DEFAULT_MAX_VERSION_STORAGE_MB)) * 1024 * 1024;
    const versions = await getVersions(documentId, 1000);
    if (!versions.length) return 0;

    // Checkpoints nomeados funcionam como marcos manuais. Preserve-os quando possível
    // e descarte primeiro autosaves/checkpoints automáticos mais antigos.
    const named = versions.filter(version => version.reason === 'named' || version.pinned === true);
    const automatic = versions.filter(version => version.reason !== 'named' && version.pinned !== true);
    const keepNamed = named.slice(0, safeLimit);
    const remainingSlots = Math.max(0, safeLimit - keepNamed.length);
    let kept = [...keepNamed, ...automatic.slice(0, remainingSlots)];

    // O limite em MB é um teto suave. Checkpoints nomeados não são apagados automaticamente;
    // autosaves mais antigos são removidos primeiro até a coleção caber no teto.
    let bytes = approximateJsonBytes(kept);
    if (bytes > safeBytes) {
      const removable = kept
        .filter(version => version.reason !== 'named' && version.pinned !== true)
        .sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt)));
      const removeIds = new Set();
      for (const version of removable) {
        if (bytes <= safeBytes) break;
        removeIds.add(version.id);
        bytes -= approximateJsonBytes(version);
      }
      kept = kept.filter(version => !removeIds.has(version.id));
    }

    const keepIds = new Set(kept.map(version => version.id));
    const stale = versions.filter(version => !keepIds.has(version.id));
    if (!stale.length) return 0;
    await Promise.allSettled(stale.map(version => deleteVersion(version.id)));
    return stale.length;
  }

  async function createVersion(doc, meta = {}) {
    if (!doc?.id) return null;
    const [latest] = await getVersions(doc.id, 1);
    if (latest && documentFingerprint(latest) === documentFingerprint(doc)) return latest;

    const version = normalizeVersion(doc, meta);
    try { await withStore(VERSION_STORE, 'readwrite', store => store.put(version)); }
    catch {
      const items = fallbackRead(FALLBACK_VERSIONS_KEY, []).filter(item => item.id !== version.id);
      items.push(version);
      fallbackWrite(FALLBACK_VERSIONS_KEY, items);
    }
    const storageSettings = getStorageSettings();
    await pruneVersions(doc.id, meta.maxVersions ?? storageSettings.maxVersions, meta.maxVersionStorageMB ?? storageSettings.maxVersionStorageMB);
    return version;
  }


  function approximateJsonBytes(value) {
    try { return new Blob([JSON.stringify(value ?? null)]).size; }
    catch {
      try { return new TextEncoder().encode(JSON.stringify(value ?? null)).byteLength; }
      catch { return 0; }
    }
  }

  async function getStorageSummary(documentId) {
    const summary = {
      documentBytes: 0,
      draftBytes: 0,
      versionsBytes: 0,
      totalBytes: 0,
      versionCount: 0,
      browserUsage: null,
      browserQuota: null
    };

    if (documentId) {
      const [doc, draft, versions] = await Promise.all([
        getDocument(documentId),
        getDraft(documentId),
        getVersions(documentId, 1000)
      ]);
      summary.documentBytes = approximateJsonBytes(doc);
      summary.draftBytes = approximateJsonBytes(draft);
      summary.versionsBytes = approximateJsonBytes(versions);
      summary.versionCount = versions.length;
      summary.totalBytes = summary.documentBytes + summary.draftBytes + summary.versionsBytes;
    }

    if (navigator.storage?.estimate) {
      try {
        const estimate = await navigator.storage.estimate();
        summary.browserUsage = Number.isFinite(estimate.usage) ? estimate.usage : null;
        summary.browserQuota = Number.isFinite(estimate.quota) ? estimate.quota : null;
      } catch {}
    }
    return summary;
  }

  window.InkWriteDB = {
    createId,
    normalize,
    putDocument,
    getDocument,
    getAllDocuments,
    deleteDocument,
    renameDocument,
    duplicateDocument,
    putDraft,
    putDraftSync,
    getDraft,
    deleteDraft,
    createVersion,
    getVersion,
    getVersions,
    deleteVersion,
    pruneVersions,
    getStorageSettings,
    setStorageSettings,
    getStorageSummary,
    documentFingerprint
  };
})();
