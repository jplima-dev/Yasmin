import QRCode from "qrcode";
import { buildPayload, safeFilename } from "./payloads.js";

const form = document.querySelector("#qr-form");
const preview = document.querySelector("#qr-preview");
const emptyPreview = document.querySelector("#empty-preview");
const status = document.querySelector("#status");
const validation = document.querySelector("#validation");
const pngButton = document.querySelector("#download-png");
const svgButton = document.querySelector("#download-svg");
const logoInput = document.querySelector("#logo-input");
const logoName = document.querySelector("#logo-name");
const toastElement = document.querySelector("#toast");
const pixCopyWrap = document.querySelector("#pix-copy-wrap");
const pixCopy = document.querySelector("#pix-copy");
const copyPixButton = document.querySelector("#copy-pix");

let currentPayload = "";
let currentOptions = null;
let logoDataUrl = "";
let debounceTimer = 0;
let renderVersion = 0;

function valuesFromForm() {
  const data = new FormData(form);
  return {
    url: data.get("url"), text: data.get("text"), ssid: data.get("ssid"),
    security: data.get("security"), password: data.get("password"), hidden: data.get("hidden") === "on",
    name: data.get("name"), organization: data.get("organization"),
    phone: data.get("type") === "contact" ? data.get("contactPhone") : data.get("phone"),
    email: data.get("type") === "contact" ? data.get("contactEmail") : data.get("email"),
    subject: data.get("subject"), body: data.get("body"),
    pixKeyType: data.get("pixKeyType"), pixKey: data.get("pixKey"),
    pixName: data.get("pixName"), pixCity: data.get("pixCity"),
    pixAmount: data.get("pixAmountMode") === "fixed" ? data.get("pixAmount") : "",
    pixDescription: data.get("pixDescription"), pixTxid: data.get("pixTxid"),
  };
}

function optionsFromForm() {
  const data = new FormData(form);
  const hasLogo = Boolean(logoDataUrl);
  return {
    size: Number(data.get("size")),
    margin: Number(data.get("margin")),
    dark: String(data.get("dark")),
    light: String(data.get("light")),
    errorCorrectionLevel: hasLogo ? "H" : String(data.get("errorLevel")),
    title: String(data.get("title") || "").trim(),
    frame: data.get("frame") === "on",
    hasLogo,
  };
}

function setValidation(kind, heading, detail) {
  validation.classList.toggle("valid", kind === "valid");
  validation.querySelector("span").textContent = kind === "valid" ? "✓" : kind === "error" ? "!" : "○";
  validation.querySelector("strong").textContent = heading;
  validation.querySelector("small").textContent = detail;
}

function showToast(message) {
  toastElement.textContent = message;
  toastElement.classList.add("show");
  window.setTimeout(() => toastElement.classList.remove("show"), 2800);
}

function drawRoundedRect(context, x, y, width, height, radius) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
  context.fill();
}

async function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Não foi possível ler o logo."));
    image.src = source;
  });
}

async function composeCanvas(payload, options) {
  const qrCanvas = document.createElement("canvas");
  await QRCode.toCanvas(qrCanvas, payload, {
    width: options.size,
    margin: options.margin,
    errorCorrectionLevel: options.errorCorrectionLevel,
    color: { dark: `${options.dark}ff`, light: `${options.light}ff` },
  });
  const padding = options.frame ? Math.max(12, Math.round(options.size * .035)) : 0;
  const titleHeight = options.title ? Math.max(38, Math.round(options.size * .1)) : 0;
  const canvas = document.createElement("canvas");
  canvas.width = options.size + padding * 2;
  canvas.height = options.size + padding * 2 + titleHeight;
  const context = canvas.getContext("2d");
  context.fillStyle = options.light;
  context.fillRect(0, 0, canvas.width, canvas.height);
  if (options.frame) {
    context.strokeStyle = options.dark;
    context.lineWidth = Math.max(2, Math.round(options.size / 180));
    context.strokeRect(context.lineWidth / 2, context.lineWidth / 2, canvas.width - context.lineWidth, canvas.height - context.lineWidth);
  }
  context.drawImage(qrCanvas, padding, padding, options.size, options.size);
  if (logoDataUrl) {
    const logo = await loadImage(logoDataUrl);
    const logoSize = Math.round(options.size * .18);
    const x = padding + (options.size - logoSize) / 2;
    const y = padding + (options.size - logoSize) / 2;
    const backing = Math.round(logoSize * .14);
    context.fillStyle = options.light;
    drawRoundedRect(context, x - backing, y - backing, logoSize + backing * 2, logoSize + backing * 2, backing * 1.5);
    context.drawImage(logo, x, y, logoSize, logoSize);
  }
  if (options.title) {
    context.fillStyle = options.dark;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.font = `700 ${Math.max(15, Math.round(options.size * .038))}px system-ui, sans-serif`;
    context.fillText(options.title, canvas.width / 2, padding + options.size + titleHeight / 2, canvas.width - padding * 2 - 12);
  }
  return { canvas, qrCanvas };
}

async function validateReadable(qrCanvas, payload) {
  if (!("BarcodeDetector" in window)) {
    setValidation("valid", "Código gerado", "Faça o teste final com a câmera do celular.");
    return;
  }
  try {
    const formats = await BarcodeDetector.getSupportedFormats();
    if (!formats.includes("qr_code")) throw new Error("QR não suportado");
    const detector = new BarcodeDetector({ formats: ["qr_code"] });
    const results = await detector.detect(qrCanvas);
    const matched = results.some((result) => result.rawValue === payload);
    setValidation(matched ? "valid" : "error", matched ? "Leitura confirmada" : "Não foi possível confirmar", matched ? "O navegador leu o mesmo conteúdo gerado." : "Aumente a margem ou remova o logo e teste novamente.");
  } catch {
    setValidation("valid", "Código gerado", "Faça o teste final com a câmera do celular.");
  }
}

async function render() {
  const version = ++renderVersion;
  const type = new FormData(form).get("type");
  try {
    const payload = buildPayload(type, valuesFromForm());
    const options = optionsFromForm();
    const result = await composeCanvas(payload, options);
    if (version !== renderVersion) return;
    preview.width = result.canvas.width;
    preview.height = result.canvas.height;
    preview.getContext("2d").drawImage(result.canvas, 0, 0);
    emptyPreview.classList.add("hidden");
    status.textContent = "Pronto";
    status.classList.add("ready");
    pngButton.disabled = false;
    svgButton.disabled = false;
    currentPayload = payload;
    currentOptions = options;
    pixCopyWrap.classList.toggle("hidden", type !== "pix");
    pixCopy.value = type === "pix" ? payload : "";
    await validateReadable(result.qrCanvas, payload);
  } catch (error) {
    if (version !== renderVersion) return;
    currentPayload = "";
    currentOptions = null;
    pixCopyWrap.classList.add("hidden");
    pixCopy.value = "";
    emptyPreview.classList.remove("hidden");
    status.textContent = "Preencha o conteúdo";
    status.classList.remove("ready");
    pngButton.disabled = true;
    svgButton.disabled = true;
    setValidation(error.message ? "error" : "idle", error.message || "Aguardando conteúdo", "Revise os campos destacados acima.");
  }
}

function scheduleRender() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(render, 180);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function buildSvg(payload, options) {
  const raw = await QRCode.toString(payload, {
    type: "svg", margin: options.margin, errorCorrectionLevel: options.errorCorrectionLevel,
    color: { dark: `${options.dark}ff`, light: `${options.light}ff` },
  });
  const documentNode = new DOMParser().parseFromString(raw, "image/svg+xml");
  const source = documentNode.documentElement;
  const viewBox = (source.getAttribute("viewBox") || "0 0 100 100").split(/\s+/).map(Number);
  const width = viewBox[2];
  const qrHeight = viewBox[3];
  const padding = options.frame ? width * .035 : 0;
  const titleHeight = options.title ? width * .1 : 0;
  const totalWidth = width + padding * 2;
  const totalHeight = qrHeight + padding * 2 + titleHeight;
  const wrapper = document.implementation.createDocument("http://www.w3.org/2000/svg", "svg", null);
  const svg = wrapper.documentElement;
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svg.setAttribute("viewBox", `0 0 ${totalWidth} ${totalHeight}`);
  svg.setAttribute("width", String(options.size));
  svg.setAttribute("height", String(Math.round(options.size * totalHeight / totalWidth)));
  const background = wrapper.createElementNS(svg.namespaceURI, "rect");
  background.setAttribute("width", "100%"); background.setAttribute("height", "100%"); background.setAttribute("fill", options.light);
  svg.append(background);
  const group = wrapper.createElementNS(svg.namespaceURI, "g");
  group.setAttribute("transform", `translate(${padding} ${padding})`);
  [...source.childNodes].forEach((node) => group.append(wrapper.importNode(node, true)));
  svg.append(group);
  if (options.frame) {
    const frame = wrapper.createElementNS(svg.namespaceURI, "rect");
    frame.setAttribute("x", String(width * .006)); frame.setAttribute("y", String(width * .006));
    frame.setAttribute("width", String(totalWidth - width * .012)); frame.setAttribute("height", String(totalHeight - width * .012));
    frame.setAttribute("fill", "none"); frame.setAttribute("stroke", options.dark); frame.setAttribute("stroke-width", String(width * .006));
    svg.append(frame);
  }
  if (logoDataUrl) {
    const logoSize = width * .18;
    const x = padding + (width - logoSize) / 2;
    const y = padding + (qrHeight - logoSize) / 2;
    const backing = wrapper.createElementNS(svg.namespaceURI, "rect");
    backing.setAttribute("x", String(x - width * .025)); backing.setAttribute("y", String(y - width * .025));
    backing.setAttribute("width", String(logoSize + width * .05)); backing.setAttribute("height", String(logoSize + width * .05));
    backing.setAttribute("rx", String(width * .03)); backing.setAttribute("fill", options.light); svg.append(backing);
    const image = wrapper.createElementNS(svg.namespaceURI, "image");
    image.setAttribute("href", logoDataUrl); image.setAttribute("x", String(x)); image.setAttribute("y", String(y));
    image.setAttribute("width", String(logoSize)); image.setAttribute("height", String(logoSize)); svg.append(image);
  }
  if (options.title) {
    const text = wrapper.createElementNS(svg.namespaceURI, "text");
    text.setAttribute("x", String(totalWidth / 2)); text.setAttribute("y", String(padding + qrHeight + titleHeight * .62));
    text.setAttribute("text-anchor", "middle"); text.setAttribute("font-family", "system-ui, sans-serif");
    text.setAttribute("font-size", String(width * .038)); text.setAttribute("font-weight", "700"); text.setAttribute("fill", options.dark);
    text.textContent = options.title; svg.append(text);
  }
  return new XMLSerializer().serializeToString(svg);
}

form.addEventListener("input", scheduleRender);
form.addEventListener("change", (event) => {
  if (event.target.name === "type") {
    document.querySelectorAll("[data-fields]").forEach((group) => group.classList.toggle("hidden", group.dataset.fields !== event.target.value));
  }
  if (event.target.name === "pixAmountMode") {
    document.querySelector("[data-pix-amount]").classList.toggle("hidden", event.target.value !== "fixed");
  }
  scheduleRender();
});

copyPixButton.addEventListener("click", async () => {
  if (!pixCopy.value) return;
  try {
    await navigator.clipboard.writeText(pixCopy.value);
  } catch {
    pixCopy.select();
    document.execCommand("copy");
    pixCopy.setSelectionRange(0, 0);
  }
  showToast("Código PIX copiado.");
});

logoInput.addEventListener("change", () => {
  const file = logoInput.files?.[0];
  logoDataUrl = "";
  logoName.textContent = file ? file.name : "Escolher imagem";
  if (!file) { scheduleRender(); return; }
  if (file.size > 5 * 1024 * 1024) { showToast("O logo deve ter no máximo 5 MiB."); logoInput.value = ""; return; }
  const reader = new FileReader();
  reader.onload = () => { logoDataUrl = String(reader.result); scheduleRender(); };
  reader.onerror = () => showToast("Não foi possível ler o logo.");
  reader.readAsDataURL(file);
});

pngButton.addEventListener("click", () => {
  if (!currentPayload) return;
  preview.toBlob((blob) => {
    if (blob) downloadBlob(blob, `${safeFilename(currentOptions.title)}.png`);
  }, "image/png");
});

svgButton.addEventListener("click", async () => {
  if (!currentPayload) return;
  try {
    const svg = await buildSvg(currentPayload, currentOptions);
    downloadBlob(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }), `${safeFilename(currentOptions.title)}.svg`);
  } catch (error) { showToast(error.message || "Não foi possível gerar o SVG."); }
});

render();
