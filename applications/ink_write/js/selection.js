(() => {
  function create(root) {
    let savedRange = null;

    function selectionInsideRoot(selection) {
      if (!selection?.rangeCount) return false;
      const anchor = selection.anchorNode;
      const focus = selection.focusNode;
      return !!anchor && !!focus && root.contains(anchor) && root.contains(focus);
    }

    function save() {
      const selection = window.getSelection();
      if (!selectionInsideRoot(selection)) return false;
      try {
        savedRange = selection.getRangeAt(0).cloneRange();
        return true;
      } catch {
        return false;
      }
    }

    function restore() {
      if (!savedRange) return false;
      const selection = window.getSelection();
      if (!selection) return false;
      try {
        selection.removeAllRanges();
        selection.addRange(savedRange.cloneRange());
        return true;
      } catch {
        savedRange = null;
        return false;
      }
    }

    function clear() { savedRange = null; }

    function getRange() {
      if (!savedRange) return null;
      try { return savedRange.cloneRange(); }
      catch { return null; }
    }

    function setRange(range) {
      if (!range) { clear(); return false; }
      try {
        savedRange = range.cloneRange();
        return true;
      } catch {
        return false;
      }
    }

    return { save, restore, clear, getRange, setRange, selectionInsideRoot };
  }

  window.InkWriteSelection = { create };
})();
