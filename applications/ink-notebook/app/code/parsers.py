"""Parsers estruturais por linguagem. Para adicionar uma linguagem: escreva parse_x(text) e registre em PARSERS.

Cada parser devolve um dict:
  imports [{spec,line,kind,optional}], exports [str], symbols [{name,kind,line,end,parent,sig}],
  calls [(nome,linha)], refs [(nome,linha,tipo)], doc (resumo), entry (bool)
"""
import ast
import json
import re

KW = set("if for while switch catch return function typeof new await async super import require delete void yield "
         "else do in of with class constructor elif print def lambda not and or is assert except finally try "
         "echo isset empty array list foreach unset exit die".split())
_STR = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)""")
_LINE_COMMENT = re.compile(r"(^|\s)//.*$")
_CALL = re.compile(r"(?<![\w$])([A-Za-z_$][\w$]*)\s*\(")


def new():
    return {"imports": [], "exports": [], "symbols": [], "calls": [], "refs": [], "doc": "", "entry": False}


def _clean(line):
    return _LINE_COMMENT.sub("", _STR.sub('""', line))


def _brace_end(lines, i, cap=600):
    depth, seen = 0, False
    for j in range(i, min(len(lines), i + cap)):
        c = _clean(lines[j])
        depth += c.count("{") - c.count("}")
        seen = seen or "{" in c
        if seen and depth <= 0:
            return j + 1
    return i + 1


def _sym(out, name, kind, line, end=None, parent="", sig=""):
    out["symbols"].append({"name": name, "kind": kind, "line": line, "end": end or line, "parent": parent, "sig": sig[:160]})


def _doc_js(lines):
    buf = []
    for ln in lines[:15]:
        s = ln.strip()
        if s.startswith(("/**", "/*", "*", "//")):
            t = s.lstrip("/*").rstrip("*/ ").strip()
            if t:
                buf.append(t)
        elif s:
            break
    return " ".join(buf)[:240]


# ---------------- JavaScript / TypeScript ----------------
_IMP = [re.compile(r"""^\s*import\s+(?:[\w*{}\s,$]+?\s+from\s+)?['"]([^'"]+)['"]"""),
        re.compile(r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)"""),
        re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
        re.compile(r"""^\s*export\s+(?:\*|\{[^}]*\})\s+from\s+['"]([^'"]+)['"]""")]
_FN = re.compile(r"^\s*(export\s+)?(?:default\s+)?(?:async\s+)?function\*?\s+([\w$]+)\s*\(")
_CLS = re.compile(r"^\s*(export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+([\w$]+)")
_ARROW = re.compile(r"^\s*(export\s+)?(?:const|let|var)\s+([\w$]+)\s*(?::[^=]+)?=\s*(?:async\s*)?"
                    r"(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[\w$]+\s*=>)")
_VAR = re.compile(r"^(export\s+)?(?:const|let|var)\s+([\w$]+)\s*(?::[^=]+)?=")
_TYPE = re.compile(r"^\s*(?:export\s+)?(?:interface|type|enum)\s+([\w$]+)")
_METHOD = re.compile(r"^\s+(?:static\s+|public\s+|private\s+|protected\s+)*(?:async\s+)?(?:get\s+|set\s+)?([\w$#]+)\s*\([^)]*\)\s*(?::[^{]+)?\{\s*$")
_EXPORT_NAMES = re.compile(r"^\s*export\s*\{([^}]*)\}")
_EXPORT_DECL = re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|class|const|let|var|interface|type|enum)\s+([\w$]+)")
_DOM_ID = re.compile(r"""(?:getElementById\(\s*|\$\(\s*|querySelector(?:All)?\(\s*)['"]#?([\w-]+)['"]""")


def parse_js(text):
    out, lines = new(), text.split("\n")
    out["doc"] = _doc_js(lines)
    cls_stack = []  # (nome, fim)
    for i, raw in enumerate(lines):
        n = i + 1
        line = _clean(raw)
        for rx in _IMP:
            for m in rx.finditer(raw):
                out["imports"].append({"spec": m.group(1), "line": n, "kind": "import", "optional": False})
        m = _EXPORT_NAMES.match(raw)
        if m:
            out["exports"] += [x.split(" as ")[-1].strip() for x in m.group(1).split(",") if x.strip()]
        m = _EXPORT_DECL.match(raw)
        if m:
            out["exports"].append(m.group(1))
        elif re.match(r"^\s*export\s+default\b", raw):
            out["exports"].append("default")
        me = re.match(r"^\s*module\.exports\s*=\s*\{([^}]*)\}", raw)
        if me:
            out["exports"] += [x.split(":")[0].strip() for x in me.group(1).split(",") if x.strip()]
        for m in _DOM_ID.finditer(raw):
            out["refs"].append((m.group(1), n, "id"))
        while cls_stack and n > cls_stack[-1][1]:
            cls_stack.pop()
        defined = None
        if (m := _FN.match(raw)):
            defined = m.group(2)
            _sym(out, defined, "function", n, _brace_end(lines, i), sig=raw.strip().rstrip("{").strip())
        elif (m := _CLS.match(raw)):
            end = _brace_end(lines, i)
            _sym(out, m.group(2), "class", n, end, sig=raw.strip().rstrip("{").strip())
            cls_stack.append((m.group(2), end))
        elif (m := _ARROW.match(raw)):
            defined = m.group(2)
            _sym(out, defined, "function", n, _brace_end(lines, i), sig=raw.strip()[:120])
        elif (m := _TYPE.match(raw)):
            _sym(out, m.group(1), "type", n, n)
        elif (m := _VAR.match(raw)) and (m.group(2).isupper() or m.group(1)):
            _sym(out, m.group(2), "variable", n, n)
        elif cls_stack and (m := _METHOD.match(raw)) and m.group(1) not in KW:
            defined = m.group(1)
            _sym(out, defined, "method", n, _brace_end(lines, i), parent=cls_stack[-1][0], sig=raw.strip().rstrip("{").strip())
        for m in _CALL.finditer(line):
            name = m.group(1)
            if name in KW or name == defined or name in ("require",):
                continue
            out["calls"].append((name, n))
    if re.search(r"\bapp\.listen\(|createRoot\(|ReactDOM\.render\(|DOMContentLoaded", text):
        out["entry"] = True
    return out


# ---------------- Python ----------------
_PY_ROUTE = {"route", "get", "post", "put", "delete", "patch"}


def _py_sig(fn):
    try:
        return f"def {fn.name}({', '.join(a.arg for a in fn.args.args)})"
    except Exception:
        return f"def {fn.name}()"


def parse_py(text):
    out = new()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _py_fallback(text)
    out["doc"] = (ast.get_docstring(tree) or "").strip().split("\n\n")[0].replace("\n", " ")[:240]
    all_names = None
    for node in tree.body:
        if isinstance(node, ast.If) and "__name__" in ast.dump(node.test) and "__main__" in ast.dump(node.test):
            out["entry"] = True
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    if t.id == "__all__" and isinstance(node.value, (ast.List, ast.Tuple)):
                        all_names = [e.value for e in node.value.elts if isinstance(e, ast.Constant)]
                    elif t.id.isupper():
                        _sym(out, t.id, "variable", node.lineno)

    def visit(node, parent=""):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, ast.Import):
                for a in ch.names:
                    out["imports"].append({"spec": a.name, "line": ch.lineno, "kind": "import", "optional": False})
            elif isinstance(ch, ast.ImportFrom):
                base = "." * ch.level + (ch.module or "")
                out["imports"].append({"spec": base, "line": ch.lineno, "kind": "import", "optional": False})
                for a in ch.names:
                    if a.name != "*":
                        out["imports"].append({"spec": base.rstrip(".") + "." + a.name if ch.module else base + a.name,
                                               "line": ch.lineno, "kind": "import", "optional": True})
            elif isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if parent else "function"
                _sym(out, ch.name, kind, ch.lineno, getattr(ch, "end_lineno", ch.lineno), parent, _py_sig(ch))
                for d in ch.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in _PY_ROUTE \
                            and d.args and isinstance(d.args[0], ast.Constant) and isinstance(d.args[0].value, str):
                        verb = d.func.attr.upper() if d.func.attr != "route" else "ROUTE"
                        _sym(out, d.args[0].value, "route", ch.lineno, getattr(ch, "end_lineno", ch.lineno), parent, f"{verb} → {ch.name}")
                visit(ch, parent)
                continue
            elif isinstance(ch, ast.ClassDef):
                _sym(out, ch.name, "class", ch.lineno, getattr(ch, "end_lineno", ch.lineno), "", f"class {ch.name}")
                visit(ch, ch.name)
                continue
            elif isinstance(ch, ast.Call):
                f = ch.func
                nm = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if nm and nm not in KW:
                    out["calls"].append((nm, ch.lineno))
            visit(ch, parent)

    visit(tree)
    top = [s["name"] for s in out["symbols"] if not s["parent"] and s["kind"] in ("function", "class") and not s["name"].startswith("_")]
    out["exports"] = all_names if all_names is not None else top
    return out


def _py_fallback(text):
    out = new()
    for n, ln in enumerate(text.split("\n"), 1):
        if (m := re.match(r"\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", ln)):
            out["imports"].append({"spec": m.group(1) or m.group(2), "line": n, "kind": "import", "optional": False})
        elif (m := re.match(r"\s*(?:async\s+)?def\s+(\w+)", ln)):
            _sym(out, m.group(1), "function", n)
        elif (m := re.match(r"\s*class\s+(\w+)", ln)):
            _sym(out, m.group(1), "class", n)
    return out


# ---------------- HTML ----------------
_SCRIPT = re.compile(r"<script(?P<a>[^>]*)>(?P<b>.*?)</script>", re.S | re.I)
_ATTR_ID = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""")
_ATTR_CLS = re.compile(r"""\bclass\s*=\s*["']([^"']+)["']""")
_SRC = re.compile(r"""<(?:script|img|iframe)\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']""", re.I)
_HREF = re.compile(r"""<link\b[^>]*?\bhref\s*=\s*["']([^"']+)["']""", re.I)
_HANDLER = re.compile(r"""\bon\w+\s*=\s*["']\s*([A-Za-z_$][\w$.]*)\s*\(""")


def parse_html(text):
    out = new()
    seen_ids, seen_cls = set(), set()
    for i, ln in enumerate(text.split("\n"), 1):
        for m in _ATTR_ID.finditer(ln):
            if m.group(1) not in seen_ids:
                seen_ids.add(m.group(1))
                _sym(out, m.group(1), "html-id", i)
        for m in _ATTR_CLS.finditer(ln):
            for c in m.group(1).split():
                if c not in seen_cls and len(seen_cls) < 200:
                    seen_cls.add(c)
                    _sym(out, c, "html-class", i)
        for rx in (_SRC, _HREF):
            for m in rx.finditer(ln):
                if not re.match(r"^(https?:|data:|//|#|mailto:)", m.group(1)):
                    out["imports"].append({"spec": m.group(1).split("?")[0], "line": i, "kind": "html-ref", "optional": False})
        for m in _HANDLER.finditer(ln):
            out["calls"].append((m.group(1).split(".")[-1], i))
    for m in _SCRIPT.finditer(text):
        if "src=" in m.group("a") or not m.group("b").strip():
            continue
        off = text.count("\n", 0, m.start("b"))
        sub = parse_js(m.group("b"))
        for s in sub["symbols"]:
            s["line"] += off; s["end"] += off
            out["symbols"].append(s)
        out["calls"] += [(c, l + off) for c, l in sub["calls"]]
        out["refs"] += [(c, l + off, k) for c, l, k in sub["refs"]]
        out["imports"] += [{**im, "line": im["line"] + off} for im in sub["imports"]]
    t = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    out["doc"] = (t.group(1).strip() if t else "")[:200]
    out["entry"] = bool(re.search(r"<html", text, re.I))
    return out


# ---------------- CSS ----------------
def parse_css(text):
    out = new()
    seen = set()
    for i, ln in enumerate(text.split("\n"), 1):
        if (m := re.match(r"""\s*@import\s+(?:url\()?["']?([^"')\s;]+)""", ln)):
            out["imports"].append({"spec": m.group(1), "line": i, "kind": "css-import", "optional": False})
        if (m := re.match(r"\s*(--[\w-]+)\s*:", ln)) and m.group(1) not in seen:
            seen.add(m.group(1)); _sym(out, m.group(1), "css-var", i)
        for v in re.findall(r"var\((--[\w-]+)", ln):
            out["refs"].append((v, i, "css-var"))
        head = ln.split("{")[0] if "{" in ln else ""
        if head and not head.strip().startswith(("@", "/*", "*")):
            for kind, rx in (("css-id", r"#([A-Za-z_][\w-]*)"), ("css-class", r"\.([A-Za-z_][\w-]*)")):
                for m in re.finditer(rx, head):
                    key = kind + m.group(1)
                    if key not in seen and len(seen) < 400:
                        seen.add(key); _sym(out, m.group(1), kind, i)
    return out


# ---------------- JSON ----------------
_PATHLIKE = re.compile(r"^\.{0,2}/?[\w@./-]+\.(?:js|mjs|ts|py|html|css|json|md|php)$")


def parse_json(text, name=""):
    out = new()
    try:
        data = json.loads(text)
    except Exception:
        return out
    if isinstance(data, dict):
        for i, k in enumerate(list(data)[:60]):
            _sym(out, str(k), "key", 1)
        if name.endswith("package.json"):
            for sec in ("dependencies", "devDependencies"):
                for dep in (data.get(sec) or {}):
                    out["imports"].append({"spec": dep, "line": 1, "kind": "package", "optional": False})
            for k in ("main", "module"):
                if isinstance(data.get(k), str):
                    out["imports"].append({"spec": "./" + data[k].lstrip("./"), "line": 1, "kind": "ref", "optional": True})
        out["doc"] = str(data.get("description") or data.get("name") or "")[:200]

    def walk(v, depth=0):
        if len(out["imports"]) > 50 or depth > 6:
            return
        if isinstance(v, str) and _PATHLIKE.match(v):
            out["imports"].append({"spec": v, "line": 1, "kind": "ref", "optional": True})
        elif isinstance(v, dict):
            for x in v.values(): walk(x, depth + 1)
        elif isinstance(v, list):
            for x in v: walk(x, depth + 1)
    walk(data)
    return out


# ---------------- PHP ----------------
def parse_php(text):
    out, lines = new(), text.split("\n")
    cls = None
    for i, ln in enumerate(lines):
        n = i + 1
        if (m := re.match(r"\s*use\s+([\w\\]+)", ln)):
            out["imports"].append({"spec": m.group(1), "line": n, "kind": "use", "optional": False})
        for m in re.finditer(r"""\b(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['"]([^'"]+)['"]""", ln):
            out["imports"].append({"spec": m.group(1).lstrip("/") if m.group(1).startswith("/") else "./" + m.group(1).lstrip("./"),
                                   "line": n, "kind": "include", "optional": False})
        if (m := re.match(r"\s*(?:abstract\s+|final\s+)?(class|interface|trait)\s+(\w+)", ln)):
            end = _brace_end(lines, i); cls = (m.group(2), end)
            _sym(out, m.group(2), "class", n, end)
        elif (m := re.match(r"\s*(?:(?:public|private|protected|static|abstract|final)\s+)*function\s+&?(\w+)\s*\(", ln)):
            if cls and n <= cls[1]:
                _sym(out, m.group(1), "method", n, _brace_end(lines, i), cls[0], ln.strip())
            else:
                _sym(out, m.group(1), "function", n, _brace_end(lines, i), "", ln.strip())
            continue
        for m in _CALL.finditer(_clean(ln)):
            if m.group(1) not in KW:
                out["calls"].append((m.group(1), n))
    out["entry"] = bool(re.search(r"^<\?php", text)) and not out["symbols"]
    return out


# ---------------- Markdown / texto ----------------
def parse_md(text):
    out = new()
    for i, ln in enumerate(text.split("\n"), 1):
        if (m := re.match(r"^\s{0,3}(#{1,3})\s+(.*\S)", ln)):
            _sym(out, m.group(2)[:100], "heading", i, parent=str(len(m.group(1))))
    out["doc"] = next((s["name"] for s in out["symbols"]), "")
    return out


PARSERS = {"javascript": parse_js, "typescript": parse_js, "python": parse_py, "html": parse_html,
           "css": parse_css, "php": parse_php, "markdown": parse_md}


def parse(lang, text, path=""):
    if lang == "json":
        return parse_json(text, path)
    fn = PARSERS.get(lang)
    return fn(text) if fn else new()
