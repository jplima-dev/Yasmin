export function confirmDialog({
  title = "Confirmar ação",
  message = "Deseja continuar?",
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  destructive = false,
} = {}) {
  return new Promise((resolve) => {
    const dialog = document.createElement("dialog");
    dialog.className = "mega-dialog";
    dialog.innerHTML = `
      <form method="dialog" class="mega-dialog__card">
        <h2></h2><p></p>
        <div class="mega-dialog__actions">
          <button type="submit" value="cancel" class="mega-button mega-button--secondary"></button>
          <button type="submit" value="confirm" class="mega-button ${destructive ? "mega-button--danger" : "mega-button--primary"}"></button>
        </div>
      </form>`;
    dialog.querySelector("h2").textContent = String(title);
    dialog.querySelector("p").textContent = String(message);
    dialog.querySelector('[value="cancel"]').textContent = String(cancelLabel);
    dialog.querySelector('[value="confirm"]').textContent = String(confirmLabel);
    dialog.addEventListener("close", () => {
      const accepted = dialog.returnValue === "confirm";
      dialog.remove();
      resolve(accepted);
    }, { once: true });
    dialog.addEventListener("cancel", (event) => { event.preventDefault(); dialog.close("cancel"); });
    document.body.append(dialog);
    dialog.showModal();
    dialog.querySelector('[value="cancel"]').focus();
  });
}
