"""Leitura de arquivos: converte cada formato suportado em texto puro."""
import codecs
from pathlib import Path

TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".rst", ".log", ".tex",
    ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
    ".html", ".htm", ".css", ".scss", ".xml", ".sql",
    ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".csv", ".tsv",
    ".sh", ".bat", ".ps1", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".php", ".rb",
}
SPECIAL_NAMES = {"dockerfile", "makefile", "readme", "license", "changelog"}


class ExtractError(Exception):
    pass


def file_ext(name: str) -> str:
    return Path(name).suffix.lower()


def unsupported_reason(name: str):
    ext = file_ext(name)
    if ext in TEXT_EXTS or ext == ".pdf":
        return None
    if ext == "" and name.lower() in SPECIAL_NAMES:
        return None
    if ext == "":
        return "arquivo sem extensão reconhecida"
    return f"formato '{ext}' não é suportado (aceitos: texto, código, documentação e PDF)"


def _decode(raw: bytes) -> str:
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return raw.decode("utf-16")
    if b"\x00" in raw[:8192]:
        raise ExtractError("o arquivo parece binário, não texto")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("latin-1")


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ExtractError("suporte a PDF requer o pacote 'pypdf' (pip install pypdf)")
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        parts, has_text = [], False
        for i, page in enumerate(reader.pages, 1):
            t = (page.extract_text() or "").strip()
            has_text = has_text or bool(t)
            parts.append(f"--- Página {i} ---\n{t}")
    except Exception as e:
        raise ExtractError(f"não foi possível ler o PDF ({e})")
    if not has_text:
        raise ExtractError("PDF sem texto extraível (provavelmente escaneado/imagem)")
    return "\n".join(parts)


def extract_text(path: Path) -> str:
    if file_ext(path.name) == ".pdf":
        return _read_pdf(path)
    try:
        return _decode(path.read_bytes())
    except OSError as e:
        raise ExtractError(f"não foi possível abrir o arquivo ({e})")
