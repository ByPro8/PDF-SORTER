# delete_pdf_duplicates.py
# Remove duplicates inside a target directory (recursively).
# Dedupe keys:
#  1) sha256(bytes)  -> exact duplicates
#  2) sha256(normalized_text_layer) -> "same content, different PDF bytes"
#  3) (optional) sha256(normalized_ocr_text) -> only if OCR libs are installed

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader


def _sha256_bytes(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _normalize_text(s: str) -> str:
    t = (s or "").casefold().replace("\u0307", "")
    tr = str.maketrans({"ı": "i", "ö": "o", "ü": "u", "ş": "s", "ğ": "g", "ç": "c"})
    t = t.translate(tr)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _extract_text_layer(pdf_path: Path, max_pages: int = 2) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        parts: List[str] = []
        for page in reader.pages[:max_pages]:
            parts.append(page.extract_text() or "")
        return _normalize_text("\n".join(parts))
    except Exception:
        return ""


def _ocr_first_page(pdf_path: Path) -> str:
    # Only works if user installed OCR deps
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except Exception:
        return ""

    try:
        images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=350)
        if not images:
            return ""
        return _normalize_text(pytesseract.image_to_string(images[0]) or "")
    except Exception:
        return ""


def remove_duplicates_in_dir(target_dir: Path, delete_duplicates: bool = True) -> int:
    """
    Keeps ONE copy per detected fingerprint (oldest by mtime, then name).
    Returns number removed.
    """
    target_dir = Path(target_dir)
    dup_dir = target_dir / "_DUPLICATES"
    removed = 0

    pdfs = [p for p in target_dir.rglob("*.pdf") if p.is_file()]

    # Each file can generate multiple fingerprints; if ANY fingerprint matches, we treat as duplicate.
    # Map fingerprint -> list[Path]
    groups: Dict[Tuple[str, str], List[Path]] = {}  # (kind, digest) -> files

    for p in pdfs:
        try:
            b = _sha256_bytes(p)
            groups.setdefault(("bytes", b), []).append(p)
        except Exception:
            pass

        text = _extract_text_layer(p)
        if len(text) >= 40:
            th = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
            groups.setdefault(("text", th), []).append(p)
        else:
            # No useful text-layer: try OCR (if available)
            o = _ocr_first_page(p)
            if len(o) >= 40:
                oh = hashlib.sha256(o.encode("utf-8", errors="ignore")).hexdigest()
                groups.setdefault(("ocr", oh), []).append(p)

    # Build a "duplicate set" by merging all keys. We'll remove extras per key,
    # but to avoid double-removing, track what we've already deleted.
    deleted_paths: set[str] = set()

    for (kind, digest), files in groups.items():
        if len(files) <= 1:
            continue

        # Filter already deleted
        files = [
            f for f in files if str(f.resolve()) not in deleted_paths and f.exists()
        ]
        if len(files) <= 1:
            continue

        files_sorted = sorted(files, key=lambda x: (x.stat().st_mtime, x.name))
        keeper = files_sorted[0]

        for dup in files_sorted[1:]:
            if not dup.exists():
                continue
            try:
                if delete_duplicates:
                    dup.unlink()
                    removed += 1
                    deleted_paths.add(str(dup.resolve()))
                    print(f"DUP REMOVED ({kind}): {dup.name}  (kept {keeper.name})")
                else:
                    dup_dir.mkdir(parents=True, exist_ok=True)
                    dest = _unique_dest(dup_dir, dup.name)
                    dup.replace(dest)
                    removed += 1
                    deleted_paths.add(str(dest.resolve()))
                    print(
                        f"DUP MOVED ({kind}): {dup.name} -> _DUPLICATES/{dest.name} (kept {keeper.name})"
                    )
            except Exception as e:
                print(f"[FAIL] Could not remove {dup.name}: {e}")

    return removed


def _unique_dest(dst_dir: Path, filename: str) -> Path:
    dst = dst_dir / filename
    if not dst.exists():
        return dst
    stem = dst.stem
    suf = dst.suffix
    i = 2
    while True:
        cand = dst_dir / f"{stem} ({i}){suf}"
        if not cand.exists():
            return cand
        i += 1


if __name__ == "__main__":
    removed = remove_duplicates_in_dir(Path.cwd() / "all-pdfs", delete_duplicates=True)
    print(f"\nRemoved duplicates: {removed}")
