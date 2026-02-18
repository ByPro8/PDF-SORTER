# process_new_pdfs.py
# One command pipeline:
# 1) Move PDFs from new-pdfs/ -> all-pdfs/ (renaming on collisions)
# 2) Remove exact duplicates inside all-pdfs/ (SHA256)
# 3) Sort all-pdfs/ into sorted-pdfs/Bank/Variant/
#
# Run:
#   python3 process_new_pdfs.py

from __future__ import annotations

from pathlib import Path
from typing import List

from delete_pdf_duplicates import remove_duplicates_in_dir
from sort_pdfs_by_bank import sort_pdfs


ROOT = Path.cwd()
ALL_PDFS = ROOT / "all-pdfs"
NEW_PDFS = ROOT / "new-pdfs"
SORTED = ROOT / "sorted-pdfs"


def ensure_dirs() -> None:
    ALL_PDFS.mkdir(parents=True, exist_ok=True)
    NEW_PDFS.mkdir(parents=True, exist_ok=True)
    SORTED.mkdir(parents=True, exist_ok=True)


def list_pdfs(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return [p for p in folder.rglob("*.pdf") if p.is_file()]


def unique_dest_path(dst_dir: Path, filename: str) -> Path:
    """
    If <dst_dir>/<filename> exists, returns <stem> (2).pdf, (3).pdf, etc.
    """
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


def move_new_into_all() -> int:
    """
    Moves PDFs from NEW_PDFS into ALL_PDFS.
    Keeps only PDFs, preserves nothing else.
    If names collide, rename incoming.
    """
    moved = 0
    pdfs = list_pdfs(NEW_PDFS)
    if not pdfs:
        print("No PDFs found in new-pdfs/.")
        return 0

    for p in pdfs:
        dest = unique_dest_path(ALL_PDFS, p.name)
        try:
            p.replace(dest)  # atomic move on same disk
            moved += 1
        except Exception:
            # fallback: try move via rename through filesystem
            dest.write_bytes(p.read_bytes())
            p.unlink()
            moved += 1

        print(f"MOVED: {p.name}  ->  all-pdfs/{dest.name}")

    return moved


def main() -> None:
    ensure_dirs()

    print("\n=== STEP 1: Move new PDFs into all-pdfs ===")
    moved = move_new_into_all()
    print(f"Moved {moved} PDFs.\n")

    print("=== STEP 2: Remove duplicates inside all-pdfs ===")
    removed = remove_duplicates_in_dir(ALL_PDFS, delete_duplicates=True)
    print(f"Duplicates removed: {removed}\n")

    print("=== STEP 3: Sort all-pdfs into sorted-pdfs ===")
    sorted_count = sort_pdfs(input_dir=ALL_PDFS, output_dir=SORTED)
    print(f"Sorted PDFs processed: {sorted_count}\n")

    print("DONE.")


if __name__ == "__main__":
    main()
