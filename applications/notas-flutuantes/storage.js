/* Camada de persistência: IndexedDB para quadros, anexos e versões. */
const NotesStorage = (() => {
  const DB_NAME = 'notas-flutuantes-db';
  const DB_VERSION = 1;
  const BOARD_STORE = 'boards';
  const ATTACHMENT_STORE = 'attachments';
  const SNAPSHOT_STORE = 'snapshots';
  const WORKSPACE_SNAPSHOT_KEY = '__workspace__';

  let dbPromise = null;

  function requestToPromise(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Falha no IndexedDB'));
    });
  }

  function transactionDone(tx) {
    return new Promise((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onabort = () => reject(tx.error || new Error('Transação cancelada'));
      tx.onerror = () => reject(tx.error || new Error('Falha na transação'));
    });
  }

  function open() {
    if (dbPromise) return dbPromise;

    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = () => {
        const db = request.result;

        if (!db.objectStoreNames.contains(BOARD_STORE)) {
          db.createObjectStore(BOARD_STORE, { keyPath: 'id' });
        }

        if (!db.objectStoreNames.contains(ATTACHMENT_STORE)) {
          const store = db.createObjectStore(ATTACHMENT_STORE, { keyPath: 'id' });
          store.createIndex('boardId', 'boardId', { unique: false });
        }

        if (!db.objectStoreNames.contains(SNAPSHOT_STORE)) {
          const store = db.createObjectStore(SNAPSHOT_STORE, { keyPath: 'id' });
          store.createIndex('boardId', 'boardId', { unique: false });
          store.createIndex('createdAt', 'createdAt', { unique: false });
        }
      };

      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Não foi possível abrir o IndexedDB'));
    });

    return dbPromise;
  }

  function cleanState(state) {
    const safe = state || { notes: [], links: [], nextId: 1 };
    return {
      notes: Array.isArray(safe.notes) ? safe.notes.map(note => {
        const copy = { ...note };
        delete copy.fileData;
        delete copy.image;
        delete copy._previewUrl;
        return copy;
      }) : [],
      links: Array.isArray(safe.links) ? safe.links.map(link => ({ ...link })) : [],
      nextId: typeof safe.nextId === 'number' ? safe.nextId : 1
    };
  }

  function dataUrlToBlob(dataUrl) {
    if (!dataUrl || typeof dataUrl !== 'string' || !dataUrl.startsWith('data:')) return null;
    const comma = dataUrl.indexOf(',');
    if (comma < 0) return null;
    const header = dataUrl.slice(0, comma);
    const body = dataUrl.slice(comma + 1);
    const mimeMatch = /^data:([^;,]+)/i.exec(header);
    const mime = mimeMatch ? mimeMatch[1] : 'application/octet-stream';
    const isBase64 = /;base64/i.test(header);

    try {
      if (isBase64) {
        const binary = atob(body);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return new Blob([bytes], { type: mime });
      }
      return new Blob([decodeURIComponent(body)], { type: mime });
    } catch {
      return null;
    }
  }

  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error('Falha ao ler anexo'));
      reader.readAsDataURL(blob);
    });
  }

  async function saveBoard(id, state) {
    const db = await open();
    const tx = db.transaction(BOARD_STORE, 'readwrite');
    tx.objectStore(BOARD_STORE).put({
      id,
      state: cleanState(state),
      updatedAt: Date.now()
    });
    await transactionDone(tx);
  }

  async function loadBoard(id) {
    const db = await open();
    const tx = db.transaction(BOARD_STORE, 'readonly');
    const record = await requestToPromise(tx.objectStore(BOARD_STORE).get(id));
    return record ? cleanState(record.state) : null;
  }

  async function putAttachment(boardId, blob, meta = {}, preferredId = null) {
    const db = await open();
    const id = preferredId || `att-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    const tx = db.transaction(ATTACHMENT_STORE, 'readwrite');
    tx.objectStore(ATTACHMENT_STORE).put({
      id,
      boardId,
      blob,
      name: meta.name || '',
      mime: meta.mime || blob.type || 'application/octet-stream',
      createdAt: meta.createdAt || Date.now()
    });
    await transactionDone(tx);
    return id;
  }

  async function updateAttachment(id, blob, meta = {}) {
    const db = await open();
    const tx = db.transaction(ATTACHMENT_STORE, 'readwrite');
    const store = tx.objectStore(ATTACHMENT_STORE);
    const current = await requestToPromise(store.get(id));
    if (!current) throw new Error('Anexo não encontrado');
    store.put({
      ...current,
      blob,
      name: meta.name ?? current.name,
      mime: meta.mime ?? blob.type ?? current.mime,
      updatedAt: Date.now()
    });
    await transactionDone(tx);
  }

  async function getAttachment(id) {
    if (!id) return null;
    const db = await open();
    const tx = db.transaction(ATTACHMENT_STORE, 'readonly');
    return requestToPromise(tx.objectStore(ATTACHMENT_STORE).get(id));
  }

  async function migrateState(boardId, sourceState) {
    const input = sourceState || { notes: [], links: [], nextId: 1 };
    const result = {
      notes: [],
      links: Array.isArray(input.links) ? input.links.map(link => ({ ...link })) : [],
      nextId: typeof input.nextId === 'number' ? input.nextId : 1
    };

    for (const original of (Array.isArray(input.notes) ? input.notes : [])) {
      const note = { ...original };
      let dataUrl = note.fileData || note.image || null;

      if (dataUrl) {
        const blob = dataUrlToBlob(dataUrl);
        if (blob) {
          note.attachmentId = await putAttachment(boardId, blob, {
            name: note.fileName || '',
            mime: note.fileMime || blob.type
          });
          note.fileName = note.fileName || '';
          note.fileMime = note.fileMime || blob.type;
        }
      }

      delete note.fileData;
      delete note.image;
      delete note._previewUrl;
      result.notes.push(note);
    }

    return result;
  }

  function cleanWorkspace(workspace) {
    const safe = workspace || {};
    const cleanBoards = Array.isArray(safe.boards)
      ? safe.boards
          .filter(board => board && board.id)
          .map(board => ({
            id: String(board.id),
            name: String(board.name || ''),
            state: cleanState(board.state)
          }))
      : [];

    const currentBoard = cleanBoards.some(board => board.id === safe.currentBoard)
      ? safe.currentBoard
      : (cleanBoards[0] ? cleanBoards[0].id : null);

    return { currentBoard, boards: cleanBoards };
  }

  async function createSnapshot(boardId, state, reason = 'auto') {
    const clean = cleanState(state);
    const serialized = JSON.stringify(clean);
    const existing = await listSnapshots(boardId, 1);
    if (existing[0] && existing[0].fingerprint === serialized) return existing[0];

    const record = {
      id: `snap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      boardId,
      createdAt: Date.now(),
      reason,
      state: clean,
      fingerprint: serialized
    };
    await putSnapshot(record);
    await pruneSnapshots(boardId, 30);
    return record;
  }

  async function createWorkspaceSnapshot(workspace, reason = 'auto') {
    const clean = cleanWorkspace(workspace);
    const serialized = JSON.stringify(clean);
    const existing = await listWorkspaceSnapshots(1);
    if (existing[0] && existing[0].fingerprint === serialized) return existing[0];

    const record = {
      id: `snap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      boardId: WORKSPACE_SNAPSHOT_KEY,
      createdAt: Date.now(),
      reason,
      workspace: clean,
      fingerprint: serialized
    };
    await putSnapshot(record);
    await pruneSnapshots(WORKSPACE_SNAPSHOT_KEY, 30);
    return record;
  }

  async function listSnapshots(boardId, limit = 30) {
    const db = await open();
    const tx = db.transaction(SNAPSHOT_STORE, 'readonly');
    const all = await requestToPromise(tx.objectStore(SNAPSHOT_STORE).index('boardId').getAll(boardId));
    return all.sort((a, b) => b.createdAt - a.createdAt).slice(0, limit);
  }

  function listWorkspaceSnapshots(limit = 30) {
    return listSnapshots(WORKSPACE_SNAPSHOT_KEY, limit);
  }

  async function getSnapshot(id) {
    const db = await open();
    const tx = db.transaction(SNAPSHOT_STORE, 'readonly');
    return requestToPromise(tx.objectStore(SNAPSHOT_STORE).get(id));
  }

  async function putSnapshot(snapshot) {
    if (!snapshot || !snapshot.id) throw new Error('Versão inválida');
    const db = await open();
    const tx = db.transaction(SNAPSHOT_STORE, 'readwrite');
    tx.objectStore(SNAPSHOT_STORE).put(snapshot);
    await transactionDone(tx);
    return snapshot;
  }

  async function deleteSnapshot(id) {
    const db = await open();
    const tx = db.transaction(SNAPSHOT_STORE, 'readwrite');
    tx.objectStore(SNAPSHOT_STORE).delete(id);
    await transactionDone(tx);
  }

  async function pruneSnapshots(boardId, maxCount = 30) {
    const all = await listSnapshots(boardId, 10000);
    if (all.length <= maxCount) return;
    const db = await open();
    const tx = db.transaction(SNAPSHOT_STORE, 'readwrite');
    const store = tx.objectStore(SNAPSHOT_STORE);
    all.slice(maxCount).forEach(item => store.delete(item.id));
    await transactionDone(tx);
  }

  async function deleteBoardState(id) {
    const db = await open();
    const tx = db.transaction(BOARD_STORE, 'readwrite');
    tx.objectStore(BOARD_STORE).delete(id);
    await transactionDone(tx);
  }

  async function deleteBoard(id, { preserveAttachments = true } = {}) {
    const stores = preserveAttachments
      ? [BOARD_STORE, SNAPSHOT_STORE]
      : [BOARD_STORE, ATTACHMENT_STORE, SNAPSHOT_STORE];
    const db = await open();
    const tx = db.transaction(stores, 'readwrite');
    tx.objectStore(BOARD_STORE).delete(id);

    // Versões antigas por quadro podem ser removidas. As versões globais usam
    // WORKSPACE_SNAPSHOT_KEY e permanecem intactas para permitir restauração.
    const snapshotIndex = tx.objectStore(SNAPSHOT_STORE).index('boardId');
    const snapshotReq = snapshotIndex.openCursor(IDBKeyRange.only(id));
    snapshotReq.onsuccess = () => {
      const cursor = snapshotReq.result;
      if (!cursor) return;
      cursor.delete();
      cursor.continue();
    };

    // Por padrão os anexos ficam preservados: uma versão global antiga pode
    // voltar a referenciá-los depois que um quadro tiver sido apagado.
    if (!preserveAttachments) {
      const attachmentIndex = tx.objectStore(ATTACHMENT_STORE).index('boardId');
      const attachmentReq = attachmentIndex.openCursor(IDBKeyRange.only(id));
      attachmentReq.onsuccess = () => {
        const cursor = attachmentReq.result;
        if (!cursor) return;
        cursor.delete();
        cursor.continue();
      };
    }

    await transactionDone(tx);
  }

  async function exportStateWithAttachments(state) {
    const clean = cleanState(state);
    const notes = [];
    for (const note of clean.notes) {
      const copy = { ...note };
      if (copy.attachmentId) {
        const attachment = await getAttachment(copy.attachmentId);
        if (attachment && attachment.blob) {
          copy.fileData = await blobToDataUrl(attachment.blob);
          copy.fileName = copy.fileName || attachment.name;
          copy.fileMime = copy.fileMime || attachment.mime;
        }
      }
      notes.push(copy);
    }
    return { ...clean, notes };
  }

  return {
    open,
    cleanState,
    dataUrlToBlob,
    blobToDataUrl,
    saveBoard,
    loadBoard,
    putAttachment,
    updateAttachment,
    getAttachment,
    migrateState,
    cleanWorkspace,
    createSnapshot,
    createWorkspaceSnapshot,
    listSnapshots,
    listWorkspaceSnapshots,
    getSnapshot,
    putSnapshot,
    deleteSnapshot,
    deleteBoardState,
    deleteBoard,
    exportStateWithAttachments
  };
})();
