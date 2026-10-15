(() => {
  function create({ capture, apply, onChange = () => {}, limit = 60, delay = 420 }) {
    let timer = null;
    let entries = [];
    let index = -1;
    let applying = false;

    const serialize = value => JSON.stringify(value);

    function state() {
      return {
        index,
        length: entries.length,
        canUndo: index > 0,
        canRedo: index >= 0 && index < entries.length - 1,
        applying
      };
    }

    function notify() { onChange(state()); }

    function pushNow() {
      clearTimeout(timer);
      timer = null;
      if (applying) return false;
      const shot = capture();
      const encoded = serialize(shot);
      if (index >= 0 && serialize(entries[index]) === encoded) return false;
      entries = entries.slice(0, index + 1);
      entries.push(shot);
      if (entries.length > limit) entries.shift();
      index = entries.length - 1;
      notify();
      return true;
    }

    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(pushNow, delay);
    }

    function applyAt(nextIndex) {
      if (nextIndex < 0 || nextIndex >= entries.length || nextIndex === index) return false;
      index = nextIndex;
      applying = true;
      try { apply(entries[index]); }
      finally { applying = false; }
      notify();
      return true;
    }

    function undo() { return applyAt(index - 1); }
    function redo() { return applyAt(index + 1); }

    function reset(initial) {
      clearTimeout(timer);
      timer = null;
      entries = initial == null ? [] : [initial];
      index = entries.length ? 0 : -1;
      applying = false;
      notify();
    }

    function clear() { reset(null); }
    function isApplying() { return applying; }

    return { pushNow, schedule, undo, redo, reset, clear, state, isApplying };
  }

  window.InkWriteHistory = { create };
})();
