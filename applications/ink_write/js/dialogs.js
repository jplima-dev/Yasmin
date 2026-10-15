(() => {
  function create() {
    function get(id) { return typeof id === 'string' ? document.getElementById(id) : id; }
    function open(id) {
      const dialog = get(id);
      if (!dialog) return false;
      if (!dialog.open) dialog.showModal();
      return true;
    }
    function close(id, result = 'cancel') {
      const dialog = get(id);
      if (!dialog?.open) return false;
      dialog.close(result);
      return true;
    }
    function isOpen(id) { return !!get(id)?.open; }
    function closeTopmost() {
      const dialogs = [...document.querySelectorAll('dialog[open]')];
      const dialog = dialogs.at(-1);
      if (!dialog) return false;
      dialog.close('cancel');
      return true;
    }
    return { open, close, isOpen, closeTopmost };
  }
  window.InkWriteDialogs = { create };
})();
