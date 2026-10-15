export const CORE_ORIGIN = new URL(import.meta.url).origin;

let sessionPromise;

export function coreUrl(path = "/") {
  return new URL(path, `${CORE_ORIGIN}/`).href;
}

export async function getSession() {
  if (!sessionPromise) {
    sessionPromise = fetch(coreUrl("/api/session"), { cache: "no-store", credentials: "include" })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || !payload.token) throw new Error(payload.error || "Não foi possível autenticar a sessão local.");
        return payload;
      })
      .catch((error) => { sessionPromise = null; throw error; });
  }
  return sessionPromise;
}

export async function authorizedFetch(path, options = {}) {
  const url = /^https?:\/\//i.test(String(path)) ? String(path) : coreUrl(path);
  const method = String(options.method || "GET").toUpperCase();
  const { authenticated = false, ...fetchOptions } = options;
  const requiresSession = authenticated || !["GET", "HEAD", "OPTIONS"].includes(method);
  const headers = new Headers(options.headers || {});
  if (requiresSession) {
    const session = await getSession();
    headers.set("X-Workspace-Token", session.token);
    if (method !== "GET" && method !== "HEAD" && !headers.has("Idempotency-Key")) {
      headers.set("Idempotency-Key", globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`);
    }
  }
  let response = await fetch(url, { credentials: "include", ...fetchOptions, headers });
  if (response.status === 401 && requiresSession) {
    sessionPromise = null;
    const session = await getSession();
    headers.set("X-Workspace-Token", session.token);
    response = await fetch(url, { credentials: "include", ...fetchOptions, headers });
  }
  return response;
}

export async function apiRequest(path, options = {}) {
  const response = await authorizedFetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.error || payload.reason || `Falha ${response.status}`);
    Object.assign(error, payload, { status: response.status });
    throw error;
  }
  return payload;
}
