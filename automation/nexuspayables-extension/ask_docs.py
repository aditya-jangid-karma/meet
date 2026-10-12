#!/usr/bin/env python3
"""
Let a local Ollama model "read" Word/text files.

Ollama models cannot open files on your PC by path - they only see the text you send. This script
extracts the text from .docx / .txt / .md / .csv files, puts it in the prompt, and raises the context
window so the text is not cut off (Ollama's default is only 2-4k tokens).

Usage:
  python ask_docs.py "Report_1.docx" "Report_2.docx" -q "Summarise both and say what we can automate"
  python ask_docs.py a.docx b.docx -q "..." --model qwen3:4b --ctx 16384 --no-think
  python ask_docs.py a.docx -q-file question.txt
Only the standard library is needed (no python-docx).
"""
import argparse
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    lines = []
    body = root.find(W + "body")
    for el in body if body is not None else []:   # top-level paragraphs and tables only (no double reads)
        if el.tag == W + "p":
            txt = "".join(t.text or "" for t in el.iter(W + "t"))
            style = el.find(f"{W}pPr/{W}pStyle")
            if style is not None and style.get(W + "val", "").lower().startswith("heading") and txt.strip():
                txt = "## " + txt
            lines.append(txt)
        elif el.tag == W + "tbl":  # each row -> "a | b | c"
            for tr in el.findall(W + "tr"):
                cells = ["".join(t.text or "" for t in tc.iter(W + "t")).strip() for tc in tr.findall(W + "tc")]
                lines.append(" | ".join(cells))
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def read_any(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-q", "--question", default="")
    ap.add_argument("--q-file", help="Read the question from a text file")
    ap.add_argument("--model", default="qwen3:4b")
    ap.add_argument("--ctx", type=int, default=0, help="Context window in tokens (default: auto from text size)")
    ap.add_argument("--no-think", action="store_true", help="Hide qwen3's long 'Thinking...' section")
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--dump", action="store_true", help="Only print the extracted text (no model call)")
    a = ap.parse_args()

    q = Path(a.q_file).read_text(encoding="utf-8") if a.q_file else a.question
    parts = []
    for i, f in enumerate(a.files, 1):
        p = Path(f)
        if not p.exists():
            sys.exit(f"File not found: {p}")
        txt = read_any(p)
        print(f"[read] {p.name}: {len(txt):,} characters", file=sys.stderr)
        parts.append(f"=== DOCUMENT {i}: {p.name} ===\n{txt}")
    prompt = "\n\n".join(parts) + f"\n\n=== TASK ===\n{q}\n"
    if a.dump:
        print(prompt)
        return

    est_tokens = int(len(prompt) / 3.2) + 1500          # + room for the answer
    ctx = a.ctx or min(max(4096, 1 << (est_tokens - 1).bit_length()), 32768)
    print(f"[ollama] model={a.model}  ~{est_tokens:,} tokens needed  num_ctx={ctx}", file=sys.stderr)
    if est_tokens > ctx:
        print(f"[warn] text is larger than the context window ({ctx}); the start of it will be cut. "
              "Raise --ctx (needs more RAM) or use a bigger/longer-context model.", file=sys.stderr)

    body = {"model": a.model, "stream": True, "messages": [{"role": "user", "content": prompt}],
            "options": {"num_ctx": ctx}}
    if a.no_think:
        body["think"] = False
    req = urllib.request.Request(a.host + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        for line in r:
            if not line.strip():
                continue
            m = json.loads(line)
            if m.get("error"):
                sys.exit(f"Ollama error: {m['error']}")
            msg = m.get("message", {})
            if msg.get("thinking") and not a.no_think:
                print(msg["thinking"], end="", flush=True)
            print(msg.get("content", ""), end="", flush=True)
    print()


if __name__ == "__main__":
    main()
