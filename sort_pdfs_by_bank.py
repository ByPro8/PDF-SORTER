# sort_pdfs_by_type.py
# Put this file in the folder that contains your PDFs, then run:
#
#   python3 -m venv .venv
#   source .venv/bin/activate
#   python3 -m pip install --upgrade pip
#   python3 -m pip install pypdf
#
# OPTIONAL (OCR fallback for image/vector PDFs like Deniz):
#   brew install tesseract poppler
#   python3 -m pip install pytesseract pillow pdf2image
#
# Run:
#   python3 sort_pdfs_by_type.py

import re
import shutil
from pathlib import Path
from typing import Callable, List, Tuple

from pypdf import PdfReader


# =========================
# TEXT HELPERS
# =========================
def normalize_text(s: str) -> str:
    if not s:
        return ""

    s = s.casefold()

    tr_map = str.maketrans(
        {
            "ı": "i",
            "İ": "i",
            "ö": "o",
            "Ö": "o",
            "ü": "u",
            "Ü": "u",
            "ş": "s",
            "Ş": "s",
            "ğ": "g",
            "Ğ": "g",
            "ç": "c",
            "Ç": "c",
        }
    )

    s = s.translate(tr_map)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_pdf_text(pdf_path: Path, max_pages: int = 2) -> str:
    """
    Fast: PDF text layer extraction.
    """
    try:
        reader = PdfReader(str(pdf_path))
        parts = []
        for page in reader.pages[:max_pages]:
            parts.append(page.extract_text() or "")
        return normalize_text("\n".join(parts))
    except Exception:
        return ""


def ocr_pdf_text(pdf_path: Path, max_pages: int = 1, dpi: int = 400) -> str:
    """
    Slow: render PDF -> OCR (works even if content is vector / not selectable).
    Runs ONLY after fast checks fail.

    Requires (one-time):
      brew install tesseract poppler
      python3 -m pip install pytesseract pillow pdf2image
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(
            str(pdf_path),
            first_page=1,
            last_page=max_pages,
            dpi=dpi,
        )

        parts = []
        for img in images:
            parts.append(pytesseract.image_to_string(img, lang="tur+eng"))

        return normalize_text("\n".join(parts))
    except Exception:
        return ""


# =========================
# BANK+TYPE DETECTORS
# =========================
# --- ZIRAAT (2 types) ---
def is_ziraat_fast(text: str) -> bool:
    return ("ziraatbank.com.tr" in text) and (
        ("hesaptan fast" in text) or ("fast mesaj kodu" in text)
    )


def is_ziraat_havale(text: str) -> bool:
    return ("ziraatbank.com.tr" in text) and (
        ("hesaptan hesaba havale" in text) or ("havale tutari" in text)
    )


# --- YAPI KREDI (2 types) ---
def is_yapi_kredi_edekont(text: str) -> bool:
    return ("yapikredi.com.tr" in text) and (
        ("e-dekont" in text) and ("elektronik ortamda uretilmistir" in text)
    )


def is_yapi_kredi_bilgi(text: str) -> bool:
    return ("yapikredi.com.tr" in text) and (
        ("bilgi dekontu" in text) and ("e-dekont yerine gecmez" in text)
    )


# --- KUVEYT TURK (2 variants: EN + TR) ---
def is_kuveyt_turk_en(text: str) -> bool:
    """
    English template example has:
      "kuveyt turk participation bank"
      "money transfer to iban"
      and the site
    """
    return ("kuveytturk.com.tr" in text) and (
        ("kuveyt turk participation bank" in text)
        or ("money transfer to iban" in text)
        or ("outgoing" in text)
    )


def is_kuveyt_turk_tr(text: str) -> bool:
    """
    Turkish template example has:
      "kuveyt turk katilim bankasi"
      "iban'a para transferi (giden)"
      and the site
    """
    return ("kuveytturk.com.tr" in text) and (
        ("kuveyt turk katilim bankasi" in text)
        or ("iban'a para transferi" in text)
        or ("mobil sube" in text)
        or ("aciklama" in text)
        or ("tutar" in text and "tl" in text)
    )


# --- Other banks (website-only) ---
def is_akbank(text: str) -> bool:
    return "akbank.com" in text


def is_denizbank(text: str) -> bool:
    return "denizbank.com" in text


def is_enpara(text: str) -> bool:
    return "enpara.com" in text


def is_garanti(text: str) -> bool:
    return "garantibbva.com.tr" in text


def is_vakifbank(text: str) -> bool:
    return "vakifbank.com.tr" in text


def is_vakif_katilim(text: str) -> bool:
    return "vakifkatilim.com.tr" in text


def is_teb(text: str) -> bool:
    return "teb.com.tr" in text


def is_ing(text: str) -> bool:
    return "ing.com.tr" in text


def is_turkiye_finans(text: str) -> bool:
    return "turkiyefinans.com.tr" in text


def is_isbank(text: str) -> bool:
    return "isbank.com.tr" in text


def is_halkbank(text: str) -> bool:
    return "halkbank.com.tr" in text


def is_qnb(text: str) -> bool:
    return "qnb.com.tr" in text


def is_pttbank(text: str) -> bool:
    return "pttbank.ptt.gov.tr" in text


def is_tombank(text: str) -> bool:
    return "tombank.com.tr" in text


# =========================
# OUTPUT FOLDERS
# =========================
FOLDERS = {
    # Ziraat (2)
    "ZIRAAT_FAST": "Ziraat - FAST",
    "ZIRAAT_HAVALE": "Ziraat - Havale",
    # Yapi (2)
    "YAPI_EDEKONT": "YapiKredi - e-Dekont",
    "YAPI_BILGI": "YapiKredi - Bilgi Dekontu",
    # KuveytTurk (2 variants under one parent folder)
    "KUVEYT_TURK_EN": "KuveytTurk/English",
    "KUVEYT_TURK_TR": "KuveytTurk/Turkish",
    # others
    "AKBANK": "Akbank",
    "DENIZBANK": "DenizBank",
    "ENPARA": "Enpara",
    "GARANTI": "Garanti",
    "VAKIFBANK": "VakifBank",
    "VAKIF_KATILIM": "VakifKatilim",
    "TEB": "TEB",
    "ING": "ING",
    "TURKIYE_FINANS": "TurkiyeFinans",
    "ISBANK": "TurkiyeIsBankasi",
    "HALKBANK": "Halkbank",
    "QNB": "QNB",
    "PTTBANK": "PttBank",
    "TOMBANK": "TOM Bank",
    "OTHER": "Other",
}

# Order matters: subtype checks + lookalikes first
DETECTORS_FAST: List[Tuple[str, Callable[[str], bool]]] = [
    # Ziraat subtypes first
    ("ZIRAAT_FAST", is_ziraat_fast),
    ("ZIRAAT_HAVALE", is_ziraat_havale),
    # Yapi subtypes first
    ("YAPI_BILGI", is_yapi_kredi_bilgi),
    ("YAPI_EDEKONT", is_yapi_kredi_edekont),
    # KuveytTurk variants (EN before TR)
    ("KUVEYT_TURK_EN", is_kuveyt_turk_en),
    ("KUVEYT_TURK_TR", is_kuveyt_turk_tr),
    # Vakif Katilim before VakifBank
    ("VAKIF_KATILIM", is_vakif_katilim),
    ("VAKIFBANK", is_vakifbank),
    # Then other banks
    ("AKBANK", is_akbank),
    ("DENIZBANK", is_denizbank),
    ("ENPARA", is_enpara),
    ("GARANTI", is_garanti),
    ("TEB", is_teb),
    ("ING", is_ing),
    ("TURKIYE_FINANS", is_turkiye_finans),
    ("ISBANK", is_isbank),
    ("HALKBANK", is_halkbank),
    ("QNB", is_qnb),
    ("PTTBANK", is_pttbank),
    ("TOMBANK", is_tombank),
]

# If True: re-scan already sorted PDFs
RESCAN_EXISTING = False


# =========================
# SORTING CORE
# =========================
def detect_from_list(text: str, detectors) -> str:
    for key, fn in detectors:
        if fn(text):
            return key
    return "OTHER"


def detect_type(pdf_path: Path) -> str:
    """
    Optimization path:
    1) Extract text layer -> FAST checks (no OCR)
    2) If no match -> OCR render first page (slow)
       Then run same checks again (Deniz/image PDFs become detectable)
    """
    text = extract_pdf_text(pdf_path, max_pages=2)
    kind = detect_from_list(text, DETECTORS_FAST)
    if kind != "OTHER":
        return kind

    ocr_text = ocr_pdf_text(pdf_path, max_pages=1, dpi=400)
    if not ocr_text:
        return "OTHER"

    return detect_from_list(ocr_text, DETECTORS_FAST)


def safe_move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name

    # avoid overwrite
    if dst.exists() and dst.resolve() != src.resolve():
        stem, suf = src.stem, src.suffix
        i = 2
        while True:
            cand = dst_dir / f"{stem} ({i}){suf}"
            if not cand.exists():
                dst = cand
                break
            i += 1

    if src.resolve() != dst.resolve():
        shutil.move(str(src), str(dst))

    return dst


def is_inside_output_folder(p: Path, output_names: set) -> bool:
    return any(parent.as_posix() in output_names for parent in p.parents)


def main():
    root = Path.cwd()

    # IMPORTANT: include nested output folders too (KuveytTurk/English, KuveytTurk/Turkish)
    output_names = set(Path(v).as_posix() for v in FOLDERS.values())

    pdfs = [p for p in root.rglob("*") if p.is_file() and p.suffix.casefold() == ".pdf"]

    moved = 0
    for idx, pdf in enumerate(pdfs, start=1):
        if not RESCAN_EXISTING and is_inside_output_folder(pdf, output_names):
            continue

        kind = detect_type(pdf)
        folder = FOLDERS[kind]

        safe_move(pdf, root / folder)
        moved += 1
        print(f"{idx}/{len(pdfs)}  [{kind}]  {pdf.name}  ->  {folder}")

    print(f"\nDone. Moved {moved} PDFs.")
    print(f"Unmatched PDFs are in: {FOLDERS['OTHER']}/")


if __name__ == "__main__":
    main()
