class WorkspaceEvents extends EventTarget {
  emit(type, detail = {}) { return this.dispatchEvent(new CustomEvent(type, { detail })); }
  on(type, listener) {
    const handler = (event) => listener(event.detail);
    this.addEventListener(type, handler);
    return () => this.removeEventListener(type, handler);
  }
}

export const Events = new WorkspaceEvents();
