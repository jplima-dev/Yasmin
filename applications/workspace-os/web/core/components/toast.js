function region() {
  let element = document.querySelector("#mega-toast-region");
  if (element) return element;
  element = document.createElement("div");
  element.id = "mega-toast-region";
  element.className = "mega-toast-region";
  element.setAttribute("role", "status");
  element.setAttribute("aria-live", "polite");
  document.body.append(element);
  return element;
}

export function toast(message, { tone = "neutral", duration = 3200 } = {}) {
  const item = document.createElement("div");
  item.className = `mega-toast mega-toast--${tone}`;
  item.textContent = String(message);
  region().append(item);
  requestAnimationFrame(() => item.classList.add("is-visible"));
  const dismiss = () => {
    item.classList.remove("is-visible");
    window.setTimeout(() => item.remove(), 180);
  };
  window.setTimeout(dismiss, Math.max(800, duration));
  return dismiss;
}

