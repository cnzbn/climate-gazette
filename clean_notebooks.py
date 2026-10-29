# scripts/clean_notebooks.py
import json, glob

def is_commented(cell):
    if cell["cell_type"] != "code":
        return False
    lines = [l.strip() for l in "".join(cell["source"]).splitlines() if l.strip()]
    return bool(lines) and all(l.startswith("#") for l in lines)

def is_readonly(cell):
    meta = cell.get("metadata", {})
    return meta.get("editable") is False   # adjust to match your files

for path in glob.glob("**/*.ipynb", recursive=True):
    with open(path, encoding="utf-8") as f:
        nb = json.load(f)
    before = len(nb["cells"])
    nb["cells"] = [c for c in nb["cells"] if not (is_commented(c) or is_readonly(c))]
    if len(nb["cells"]) != before:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)