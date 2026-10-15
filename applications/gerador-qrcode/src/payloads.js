const WIFI_ESCAPE = /([\\;,:"])/g;
const VCARD_ESCAPE = /([\\;,])/g;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function escapeWifi(value) {
  return String(value ?? "").replace(WIFI_ESCAPE, "\\$1");
}

export function escapeVCard(value) {
  return String(value ?? "").replace(VCARD_ESCAPE, "\\$1").replace(/\r?\n/g, "\\n");
}

export function normalizeUrl(value) {
  const trimmed = String(value ?? "").trim();
  if (!trimmed) throw new Error("Informe um endereço.");
  const withProtocol = /^[a-z][a-z\d+.-]*:/i.test(trimmed) ? trimmed : `https://${trimmed}`;
  let parsed;
  try { parsed = new URL(withProtocol); } catch { throw new Error("Digite um endereço válido."); }
  if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Use um endereço http:// ou https://.");
  return parsed.href;
}

function digits(value) {
  return String(value ?? "").replace(/\D/g, "");
}

function hasValidCpf(value) {
  const cpf = digits(value);
  if (cpf.length !== 11 || /^(\d)\1+$/.test(cpf)) return false;
  const check = (length) => {
    let sum = 0;
    for (let index = 0; index < length; index += 1) sum += Number(cpf[index]) * (length + 1 - index);
    const remainder = (sum * 10) % 11;
    return Number(cpf[length]) === (remainder === 10 ? 0 : remainder);
  };
  return check(9) && check(10);
}

function hasValidCnpj(value) {
  const cnpj = digits(value);
  if (cnpj.length !== 14 || /^(\d)\1+$/.test(cnpj)) return false;
  const calculate = (base) => {
    let weight = base.length - 7;
    const sum = [...base].reduce((total, digit) => {
      const next = total + Number(digit) * weight;
      weight = weight === 2 ? 9 : weight - 1;
      return next;
    }, 0);
    const remainder = sum % 11;
    return remainder < 2 ? 0 : 11 - remainder;
  };
  const first = calculate(cnpj.slice(0, 12));
  const second = calculate(`${cnpj.slice(0, 12)}${first}`);
  return cnpj.endsWith(`${first}${second}`);
}

function ascii(value, maxLength) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^A-Za-z0-9 $%*+\-./:]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase()
    .slice(0, maxLength);
}

function emv(id, value) {
  const content = String(value);
  const length = new TextEncoder().encode(content).length;
  if (length > 99) throw new Error(`O campo PIX ${id} ultrapassa 99 caracteres.`);
  return `${id}${String(length).padStart(2, "0")}${content}`;
}

export function crc16Pix(value) {
  const bytes = new TextEncoder().encode(value);
  let crc = 0xffff;
  for (const byte of bytes) {
    crc ^= byte << 8;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

export function normalizePixKey(type, value) {
  const raw = String(value ?? "").trim();
  if (!raw) throw new Error("Informe a chave PIX.");
  switch (type) {
    case "cpf":
      if (!hasValidCpf(raw)) throw new Error("Informe um CPF válido para a chave PIX.");
      return digits(raw);
    case "cnpj":
      if (!hasValidCnpj(raw)) throw new Error("Informe um CNPJ válido para a chave PIX.");
      return digits(raw);
    case "phone": {
      const phone = raw.replace(/[\s()-]/g, "");
      if (!/^\+[1-9]\d{7,14}$/.test(phone)) throw new Error("Use o telefone PIX no formato internacional, como +5585999999999.");
      return phone;
    }
    case "email":
      if (!EMAIL.test(raw) || raw.length > 77) throw new Error("Informe um e-mail válido para a chave PIX.");
      return raw;
    case "random":
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(raw)) throw new Error("Informe uma chave aleatória PIX válida.");
      return raw.toLowerCase();
    default:
      throw new Error("Escolha o tipo da chave PIX.");
  }
}

export function buildPixPayload(values) {
  const key = normalizePixKey(values.pixKeyType, values.pixKey);
  const receiver = ascii(values.pixName, 25);
  const city = ascii(values.pixCity, 15);
  if (!receiver) throw new Error("Informe o nome do recebedor.");
  if (!city) throw new Error("Informe a cidade do recebedor.");

  const description = ascii(values.pixDescription, 72);
  let merchantAccount = emv("00", "BR.GOV.BCB.PIX") + emv("01", key);
  if (description) merchantAccount += emv("02", description);
  if (new TextEncoder().encode(merchantAccount).length > 99) throw new Error("A chave e a descrição PIX juntas excedem o tamanho permitido. Reduza a descrição.");

  const rawAmount = String(values.pixAmount ?? "").trim();
  let amount = "";
  if (rawAmount) {
    if (!/^\d{1,10}([.,]\d{1,2})?$/.test(rawAmount)) throw new Error("Informe um valor PIX válido, com até duas casas decimais.");
    const number = Number(rawAmount.replace(",", "."));
    if (!Number.isFinite(number) || number <= 0) throw new Error("O valor PIX deve ser maior que zero.");
    amount = number.toFixed(2);
  }

  const rawTxid = String(values.pixTxid ?? "").trim() || "***";
  if (rawTxid !== "***" && !/^[A-Za-z0-9]{1,25}$/.test(rawTxid)) throw new Error("O identificador PIX deve ter até 25 letras ou números, sem espaços.");

  let payload = emv("00", "01");
  payload += emv("26", merchantAccount);
  payload += emv("52", "0000");
  payload += emv("53", "986");
  if (amount) payload += emv("54", amount);
  payload += emv("58", "BR");
  payload += emv("59", receiver);
  payload += emv("60", city);
  payload += emv("62", emv("05", rawTxid));
  payload += "6304";
  return `${payload}${crc16Pix(payload)}`;
}

export function buildPayload(type, values) {
  switch (type) {
    case "url":
      return normalizeUrl(values.url);
    case "text": {
      const text = String(values.text ?? "").trim();
      if (!text) throw new Error("Digite o texto do QR Code.");
      return text;
    }
    case "wifi": {
      const ssid = String(values.ssid ?? "").trim();
      if (!ssid) throw new Error("Informe o nome da rede Wi-Fi.");
      const security = ["WPA", "WEP", "nopass"].includes(values.security) ? values.security : "WPA";
      const password = security === "nopass" ? "" : escapeWifi(values.password ?? "");
      return `WIFI:T:${security};S:${escapeWifi(ssid)};P:${password};H:${values.hidden ? "true" : "false"};;`;
    }
    case "contact": {
      const name = String(values.name ?? "").trim();
      if (!name) throw new Error("Informe o nome do contato.");
      const lines = ["BEGIN:VCARD", "VERSION:3.0", `FN:${escapeVCard(name)}`];
      if (values.phone) lines.push(`TEL:${escapeVCard(values.phone)}`);
      if (values.email) lines.push(`EMAIL:${escapeVCard(values.email)}`);
      if (values.organization) lines.push(`ORG:${escapeVCard(values.organization)}`);
      lines.push("END:VCARD");
      return lines.join("\n");
    }
    case "phone": {
      const phone = String(values.phone ?? "").trim();
      if (!phone) throw new Error("Informe o telefone.");
      return `tel:${phone.replace(/\s+/g, "")}`;
    }
    case "email": {
      const email = String(values.email ?? "").trim();
      if (!EMAIL.test(email)) throw new Error("Informe um e-mail válido.");
      const params = new URLSearchParams();
      if (values.subject) params.set("subject", String(values.subject));
      if (values.body) params.set("body", String(values.body));
      return `mailto:${email}${params.size ? `?${params.toString()}` : ""}`;
    }
    case "pix":
      return buildPixPayload(values);
    default:
      throw new Error("Tipo de QR Code desconhecido.");
  }
}

export function safeFilename(value, fallback = "qrcode") {
  const normalized = String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  return normalized.slice(0, 60) || fallback;
}
