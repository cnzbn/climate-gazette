import base64
import json
import re
import uuid
from pathlib import Path

HR = re.compile(r'^ {0,3}(-[ \t]*){3,}$')
DATA_URI = re.compile(r'data:image/([a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)')
H1 = re.compile(r'^#\s+(.+?)\s*#*\s*$')
H2 = re.compile(r'^##\s+(.+?)\s*#*\s*$')
SKIP = {".ipynb_checkpoints", "_site", ".quarto", ".venv", "venv", "node_modules"}
COVERS = Path("images/covers")


def join(src):
    return "".join(src) if isinstance(src, list) else src


def fix(src: str) -> str:
    out, in_fence = [], False
    for line in src.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        if not in_fence and HR.match(line):
            if out and out[-1].strip():
                out.append("")
            out.append("***")
        else:
            out.append(line)
    return "\n".join(out)


def save(stem, subtype, data):
    ext = subtype.split("+")[0].replace("jpeg", "jpg")
    COVERS.mkdir(parents=True, exist_ok=True)
    out = COVERS / f"{stem}.{ext}"
    raw = base64.b64decode(re.sub(r"\s", "", join(data)))
    if not out.exists() or out.read_bytes() != raw:
        out.write_bytes(raw)
    return out.as_posix()


def extract_cover(nb, stem):
    for cell in nb.get("cells", []):
        for bundle in (cell.get("attachments") or {}).values():
            for mime, data in bundle.items():
                if mime in ("image/png", "image/jpeg", "image/gif", "image/webp"):
                    return save(stem, mime.split("/")[1], data)
        if cell.get("cell_type") == "markdown":
            m = DATA_URI.search(join(cell["source"]))
            if m:
                return save(stem, m.group(1), m.group(2))
        for o in cell.get("outputs", []):
            for mime, data in (o.get("data") or {}).items():
                if mime in ("image/png", "image/jpeg"):
                    return save(stem, mime.split("/")[1], data)
    return None


def is_front_matter(cell):
    return cell.get("cell_type") in ("raw", "markdown") and join(cell["source"]).lstrip().startswith("---")


def pop_headings(cells, skip):
    for cell in cells:
        if cell is skip or cell.get("cell_type") != "markdown":
            continue
        src = cell["source"]
        lines = join(src).split("\n")
        for i, line in enumerate(lines):
            m = H1.match(line)
            if not m:
                continue
            title, sub, end = m.group(1), None, i
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                m2 = H2.match(lines[j])
                if m2:
                    sub, end = m2.group(1), j
            rest = lines[:i] + lines[end + 1:]
            new = "\n".join(rest).strip("\n")
            cell["source"] = new.splitlines(keepends=True) if isinstance(src, list) else new
            return title, sub
    return None, None


def q(s):
    return json.dumps(s, ensure_ascii=False)


def ensure_front_matter(nb, cover):
    cells = nb.setdefault("cells", [])
    fm = cells[0] if cells and is_front_matter(cells[0]) else None
    text = join(fm["source"]) if fm else ""
    add = []

    if not re.search(r"^title:", text, re.M):
        title, sub = pop_headings(cells, fm)
        if title:
            add.append(f"title: {q(title)}")
        if sub and not re.search(r"^description:", text, re.M):
            add.append(f"description: {q(sub)}")
    if cover and not re.search(r"^image:", text, re.M):
        add.append(f"image: {cover}")

    changed = bool(add)
    if fm is None:
        if add:
            body = "---\n" + "\n".join(add) + "\n---"
            new_cell = {"cell_type": "raw", "metadata": {}, "source": body.splitlines(keepends=True)}
            if nb.get("nbformat_minor", 0) >= 5:
                new_cell["id"] = uuid.uuid4().hex[:8]
            cells.insert(0, new_cell)
    else:
        if add:
            text = text.replace("---", "---\n" + "\n".join(add), 1)
        if fm["cell_type"] != "raw":
            fm["cell_type"] = "raw"
            for k in ("attachments", "outputs", "execution_count"):
                fm.pop(k, None)
            changed = True
        if changed:
            fm["source"] = text.splitlines(keepends=True)
    return changed


for path in Path(".").rglob("*.ipynb"):
    if SKIP & set(path.parts):
        continue
    nb = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    cover = extract_cover(nb, path.stem)
    if ensure_front_matter(nb, cover):
        changed = True

    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        src = cell["source"]
        text = join(src)
        new = fix(text)
        if new != text:
            cell["source"] = new.splitlines(keepends=True) if isinstance(src, list) else new
            changed = True

    first = nb["cells"][0] if nb.get("cells") else {}
    fm_text = join(first["source"]) if first else ""
    print(
        f"fix_hr: {path.name}: "
        f"title={'yes' if re.search(r'^title:', fm_text, re.M) else 'NO'}, "
        f"description={'yes' if re.search(r'^description:', fm_text, re.M) else 'no (optional)'}, "
        f"image={'yes' if re.search(r'^image:', fm_text, re.M) else 'NO'}"
    )
    if changed:
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"fix_hr: updated {path}")