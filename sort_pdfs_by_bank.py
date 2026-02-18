# sort_pdfs_by_bank.py
# Sort PDFs from an input folder into bank folders in an output folder.
# - Rebuilds sorted-pdfs from scratch each run
# - Copies PDFs as numbered files per bank: 1.pdf, 2.pdf, 3.pdf ...
# - NO variant folders

from __future__ import annotations

import shutil
from pathlib import Path

from bank_detect import detect_bank_variant


def target_folder_for(det: dict) -> Path:
    if det.get("key") == "UNKNOWN":
        return Path("Unknown")
    bank = det.get("bank") or "Unknown"
    return Path(bank)


def rebuild_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def sort_pdfs(input_dir: Path, output_dir: Path) -> int:
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    # IMPORTANT: rebuild output each run so you don't accumulate duplicates in sorted-pdfs
    rebuild_dir(output_dir)

    pdfs = sorted(
        [p for p in input_dir.rglob("*.pdf") if p.is_file()],
        key=lambda p: str(p).casefold(),
    )
    if not pdfs:
        print(f"No PDFs found in {input_dir}.")
        return 0

    # counters per bank folder: {"ING": 12, "Ziraat": 55, ...}
    counters: dict[str, int] = {}

    processed = 0
    for idx, pdf in enumerate(pdfs, start=1):
        det = detect_bank_variant(pdf)
        out_rel = target_folder_for(det)
        out_dir = output_dir / out_rel
        out_dir.mkdir(parents=True, exist_ok=True)

        key = out_rel.as_posix()
        counters.setdefault(key, 0)
        counters[key] += 1

        dst = out_dir / f"{counters[key]}.pdf"
        # safety: if something exists, find next free number
        while dst.exists():
            counters[key] += 1
            dst = out_dir / f"{counters[key]}.pdf"

        shutil.copy2(str(pdf), str(dst))
        processed += 1

        print(
            f"{idx}/{len(pdfs)}  "
            f"BANK={det.get('bank')}  KEY={det.get('key')}  "
            f"METHOD={det.get('method')}  "
            f"-> sorted-pdfs/{out_rel.as_posix()}/{dst.name}"
        )

    return processed


if __name__ == "__main__":
    root = Path.cwd()
    sort_pdfs(root / "all-pdfs", root / "sorted-pdfs")
