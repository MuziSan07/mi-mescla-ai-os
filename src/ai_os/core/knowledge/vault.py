"""
AI-OS Obsidian Vault (Phase 5) — the shared brain as markdown notes.

An Obsidian vault is just a folder of markdown files (with optional YAML
frontmatter, #tags and [[wikilinks]]). This module lets agents and the API
read/write those notes and search them — so research and docs the agents produce
land in a real vault you can also open in Obsidian.

Search is keyword-based by default (works fully offline, no models/services).
Semantic recall (embeddings / Qdrant) is a documented optional upgrade.

Config:
  AIOS_VAULT   vault directory (default: /opt/aios/vault or ./vault)
"""

import os
import re
import glob
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[a-z0-9]+")
_TAG = re.compile(r"(?:^|\s)#([a-zA-Z0-9_/-]+)")
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_STOP = set("the a an and or of to in is are for on with as at by be this that it from".split())


def _vault_root() -> str:
    return os.getenv(
        "AIOS_VAULT",
        "/opt/aios/vault" if os.path.isdir("/opt/aios") else "vault",
    )


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip()).strip("-").lower()
    return (slug or "note") + ".md"


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1]


@dataclass
class Note:
    path: str                       # relative, e.g. "decisions/schema.md"
    content: str = ""
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "content": self.content,
            "frontmatter": self.frontmatter,
            "tags": self.tags,
            "links": self.links,
        }


class ObsidianVault:
    """Markdown-note CRUD + keyword search over a vault directory."""

    def __init__(self) -> None:
        self.root = _vault_root()
        self._index = None  # lazily-built inverted index (Phase 8 hot-path opt)

    def _get_index(self):
        from ai_os.core.knowledge.index import VaultIndex
        if self._index is None:
            self._index = VaultIndex().build(self.root)
        return self._index

    # -- paths --------------------------------------------------------------
    def _safe(self, rel: str) -> Optional[str]:
        rel = rel.strip().lstrip("/\\")
        if not rel or ".." in rel.replace("\\", "/").split("/"):
            return None
        if not rel.endswith(".md"):
            rel += ".md"
        full = os.path.normpath(os.path.join(self.root, rel))
        root_abs = os.path.abspath(self.root)
        if os.path.commonpath([os.path.abspath(full), root_abs]) != root_abs:
            return None
        return full

    # -- parsing ------------------------------------------------------------
    @staticmethod
    def _parse(text: str) -> Dict[str, Any]:
        fm: Dict[str, Any] = {}
        body = text
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                block = text[3:end].strip()
                body = text[end + 4:].lstrip("\n")
                for line in block.splitlines():
                    if ":" in line:
                        k, _, v = line.partition(":")
                        fm[k.strip()] = v.strip()
        tags = sorted(set(_TAG.findall(text)))
        if "tags" in fm and isinstance(fm["tags"], str):
            tags = sorted(set(tags) | {t.strip() for t in re.split(r"[,\s]+", fm["tags"]) if t.strip()})
        links = sorted(set(_WIKILINK.findall(text)))
        return {"frontmatter": fm, "body": body, "tags": tags, "links": links}

    # -- CRUD ---------------------------------------------------------------
    def write_note(self, title_or_path: str, content: str,
                   tags: Optional[List[str]] = None) -> Note:
        rel = title_or_path if title_or_path.endswith(".md") else _slugify(title_or_path)
        full = self._safe(rel)
        if not full:
            raise ValueError(f"Unsafe note path: {title_or_path}")
        os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)

        fm_lines = ["---", f"created: {datetime.utcnow().isoformat()}"]
        if tags:
            fm_lines.append(f"tags: {', '.join(tags)}")
        fm_lines.append("---\n")
        doc = "\n".join(fm_lines) + content.rstrip() + "\n"
        with open(full, "w", encoding="utf-8") as f:
            f.write(doc)
        note = self.read_note(os.path.relpath(full, self.root))
        if self._index is not None:  # keep the index fresh without a full rebuild
            self._index.add(note.path, note.content, note.tags)
        return note

    def read_note(self, rel: str) -> Note:
        full = self._safe(rel)
        if not full or not os.path.isfile(full):
            raise FileNotFoundError(rel)
        with open(full, encoding="utf-8", errors="replace") as f:
            text = f.read()
        p = self._parse(text)
        relpath = os.path.relpath(full, self.root).replace("\\", "/")
        return Note(path=relpath, content=p["body"], frontmatter=p["frontmatter"],
                    tags=p["tags"], links=p["links"])

    def delete_note(self, rel: str) -> bool:
        full = self._safe(rel)
        if not full or not os.path.isfile(full):
            return False
        os.remove(full)
        rel_norm = os.path.relpath(full, self.root).replace("\\", "/")
        if self._index is not None:
            self._index.remove(rel_norm)
        return True

    def list_notes(self) -> List[str]:
        if not os.path.isdir(self.root):
            return []
        out = []
        for f in glob.glob(os.path.join(self.root, "**", "*.md"), recursive=True):
            out.append(os.path.relpath(f, self.root).replace("\\", "/"))
        return sorted(out)

    # -- search (indexed keyword, offline) ---------------------------------
    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Rank notes via the inverted index; read only the top-k for snippets."""
        q_terms = set(_tokens(query))
        if not q_terms:
            return []
        ranked = self._get_index().search(query, k=k)
        results = []
        for r in ranked:  # only the top-k notes are re-read, for snippets
            try:
                note = self.read_note(r["path"])
            except Exception:
                continue
            results.append({
                "path": r["path"],
                "score": r["score"],
                "snippet": self._snippet(note.content, q_terms),
                "tags": r["tags"],
            })
        return results

    @staticmethod
    def _snippet(content: str, q_terms: set, width: int = 240) -> str:
        low = content.lower()
        pos = -1
        for t in q_terms:
            pos = low.find(t)
            if pos != -1:
                break
        if pos == -1:
            return content[:width].strip()
        start = max(0, pos - width // 3)
        return ("…" if start else "") + content[start:start + width].strip() + "…"

    def stats(self) -> Dict[str, Any]:
        notes = self.list_notes()
        return {"vault": os.path.abspath(self.root), "notes": len(notes)}


_vault: Optional[ObsidianVault] = None


def get_vault() -> ObsidianVault:
    global _vault
    if _vault is None:
        _vault = ObsidianVault()
    return _vault
