# delete_pdf_duplicates.py
# Put this next to your sorter script (in the folder that contains PDFs).
#
# Run:
#   python3 delete_pdf_duplicates.py
#
# What it does:
# - Finds PDFs in the current folder (and optionally subfolders)
# - Detects exact duplicates by SHA-256 (same bytes)
# - Keeps ONE copy (oldest by mtime), deletes the rest (or moves to _DUPLICATES/)

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Dict, List


# =========================
# SETTINGS
# =========================

# If True: permanently deletes duplicates.
# If False: moves duplicates into _DUPLICATES/ folder in the root.
DELETE_DUPLICATES = True

# If True: scan PDFs recursively (subfolders too).
# If False: scan only PDFs directly inside the root folder.
RECURSIVE = False

# Folder name used when DELETE_DUPLICATES = False
DUP_FOLDER_NAME = "_DUPLICATES"


# =========================
# HASHING
# =========================


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name

    # avoid overwrite if same name already exists in dup folder
    if dst.exists() and dst.resolve() != src.resolve():
        stem, suf = src.stem, src.suffix
        i = 2
        while True:
            cand = dst_dir / f"{stem} ({i}){suf}"
            if not cand.exists():
                dst = cand
                break
            i += 1

    shutil.move(str(src), str(dst))
    return dst


# =========================
# DUPLICATE REMOVAL
# =========================


def remove_duplicates(pdfs: List[Path], root: Path) -> List[Path]:
    """
    Detect exact duplicate PDFs (same bytes) and delete/move duplicates.
    Keeps ONE copy per hash: the oldest by mtime (then by name).
    """
    # Group by file size first (fast pre-filter)
    by_size: Dict[int, List[Path]] = {}
    for p in pdfs:
        try:
            by_size.setdefault(p.stat().st_size, []).append(p)
        except FileNotFoundError:
            continue

    kept: List[Path] = []
    deleted = 0
    moved = 0
    failed = 0

    dup_dir = root / DUP_FOLDER_NAME

    for size, group in by_size.items():
        if len(group) == 1:
            kept.append(group[0])
            continue

        # For same-size files, hash to confirm true duplicates
        by_hash: Dict[str, List[Path]] = {}
        for p in group:
            try:
                digest = sha256_file(p)
                by_hash.setdefault(digest, []).append(p)
            except Exception as e:
                # safer to keep if hashing fails
                kept.append(p)
                print(f"[WARN] Could not hash {p.name}: {e}")

        for digest, hgroup in by_hash.items():
            if len(hgroup) == 1:
                kept.append(hgroup[0])
                continue

            # keep the oldest
            hgroup_sorted = sorted(hgroup, key=lambda x: (x.stat().st_mtime, x.name))
            keeper = hgroup_sorted[0]
            kept.append(keeper)

            for dup in hgroup_sorted[1:]:
                if not dup.exists():
                    continue
                try:
                    if DELETE_DUPLICATES:
                        dup.unlink()
                        deleted += 1
                        print(f"[DUP] deleted: {dup.name}  == kept: {keeper.name}")
                    else:
                        safe_move(dup, dup_dir)
                        moved += 1
                        print(
                            f"[DUP] moved:   {dup.name}  -> {DUP_FOLDER_NAME}/ (kept {keeper.name})"
                        )
                except Exception as e:
                    failed += 1
                    kept.append(dup)  # keep it if we couldn't remove
                    print(f"[FAIL] Could not remove {dup.name}: {e}")

    print("\n===== SUMMARY =====")
    print(f"Scanned PDFs: {len(pdfs)}")
    if DELETE_DUPLICATES:
        print(f"Deleted duplicates: {deleted}")
    else:
        print(f"Moved duplicates:   {moved}  (to {DUP_FOLDER_NAME}/)")
    print(f"Failed removals:    {failed}")
    print(f"Kept PDFs:          {len(set(kept))}")
    print("===================\n")

    # De-dup kept list itself (just in case)
    seen = set()
    unique_kept: List[Path] = []
    for p in kept:
        rp = str(p.resolve())
        if rp not in seen and p.exists():
            seen.add(rp)
            unique_kept.append(p)
    return unique_kept


def main():
    root = Path.cwd()

    if RECURSIVE:
        pdfs = [p for p in root.rglob("*.pdf") if p.is_file()]
    else:
        pdfs = [p for p in root.glob("*.pdf") if p.is_file()]

    if not pdfs:
        print("No PDFs found.")
        return

    remove_duplicates(pdfs, root)


if __name__ == "__main__":
    main()
