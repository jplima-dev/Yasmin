"""Documentação gerada a partir do índice (camada humana; o índice continua sendo a fonte da verdade)."""
from . import query


def generate(conn, nb, project):
    ov, mods, fl = query.overview(conn, nb), query.modules(conn, nb), query.flows(conn, nb)
    files = conn.execute("SELECT path, lang, lines, doc FROM code_files WHERE notebook_id=? ORDER BY path", (nb,)).fetchall()
    langs = ", ".join(f"{k} ({v})" for k, v in ov["languages"].items())
    docs = {}
    docs["estrutura.md"] = f"# Estrutura — {project}\n\n{ov['files']} arquivos · {ov['folders']} pastas · {ov['lines']} linhas\n\nLinguagens: {langs}\n\n## Arquivos\n\n" + \
        "\n".join(f"- `{f['path']}` ({f['lang']}, {f['lines']} linhas)" + (f" — {f['doc']}" if f["doc"] else "") for f in files) + "\n"
    docs["arquitetura.md"] = f"# Arquitetura — {project}\n\n_Gerado automaticamente a partir do índice; descreve apenas relações detectadas._\n\n" \
        f"## Pontos de entrada\n\n" + ("\n".join(f"- `{e['path']}`" + (f" — {e['doc']}" if e['doc'] else "") for e in ov["entry_points"]) or "Nenhum detectado.") + \
        "\n\n## Arquivos mais usados\n\n" + ("\n".join(f"- `{h['path']}` — usado por {h['n']} arquivo(s)" for h in ov["hubs"]) or "Nenhuma relação detectada.") + "\n"
    docs["modulos.md"] = f"# Módulos — {project}\n\n" + "\n\n".join(
        f"## `{m['module']}`\n\n{m['files']} arquivos · {m['symbols']} funções/classes" + (" · tem `ink-module.json`" if m["manifest"] else "") +
        (f"\n\n{m['doc']}" if m["doc"] else "") + "\n\nExemplos: " + ", ".join(f"`{s}`" for s in m["sample"]) for m in mods) + "\n"
    ext = "\n".join(f"- `{n}` ({c} importações)" for n, c in ov["external"]) or "Nenhuma."
    docs["dependencias.md"] = f"# Dependências — {project}\n\n## Mais importados\n\n" + ("\n".join(f"- `{h['path']}` ← {h['n']} arquivo(s)" for h in ov["hubs"]) or "—") + f"\n\n## Bibliotecas externas\n\n{ext}\n"
    docs["fluxos.md"] = f"# Fluxos — {project}\n\nCadeias de dependência a partir dos pontos de entrada.\n\n" + ("\n\n".join(
        f"## `{f['entry']}`\n\n" + "\n".join(f"{'  ' * (s['depth'] - 1)}- `{s['path']}` ({s['via']})" for s in f["steps"]) for f in fl) or "Nenhum fluxo detectado.") + "\n"
    manifests = [m for m in mods if m["manifest"]]
    ex = manifests[:3] or [m for m in mods if m["module"] != "(raiz)"][:3]
    loaders = conn.execute("SELECT path FROM code_files WHERE notebook_id=? AND (path LIKE '%module%loader%' OR path LIKE '%registry%' OR path LIKE '%module%bootstrap%') LIMIT 6", (nb,)).fetchall()
    docs["como-adicionar-modulo.md"] = f"# Como adicionar um módulo — {project}\n\n_Inferido do índice: confirme com o README do projeto._\n\n" + \
        ("## Arquivos que parecem registrar/carregar módulos\n\n" + "\n".join(f"- `{r['path']}`" for r in loaders) + "\n\n" if loaders else "") + \
        ("## Módulos existentes para usar como modelo\n\n" + "\n".join(f"- `{m['module']}` — exemplos: " + ", ".join(f"`{s}`" for s in m["sample"][:3]) for m in ex) if ex else "Não encontrei módulos no índice.") + "\n"
    return docs
