export function createNamespace(namespace, storage = globalThis.localStorage) {
  const prefix = `workspace.${namespace}.`;
  return Object.freeze({
    get(key, fallback = null) {
      try {
        const value = storage.getItem(`${prefix}${key}`);
        return value === null ? fallback : JSON.parse(value);
      } catch { return fallback; }
    },
    set(key, value) {
      storage.setItem(`${prefix}${key}`, JSON.stringify(value));
      return value;
    },
    remove(key) { storage.removeItem(`${prefix}${key}`); },
    key(key) { return `${prefix}${key}`; },
  });
}
