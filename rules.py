import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from ocr_utils import ocr_first_page_text
from text_layer import has_domain, normalize_text


BANK_DOMAINS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "PTTBANK": ("PttBank", ("pttbank.ptt.gov.tr",)),
    "HALKBANK": ("Halkbank", ("halkbank.com.tr",)),
    "TOMBANK": ("TOM Bank", ("tombank.com.tr",)),
    "ISBANK": ("Isbank", ("isbank.com.tr",)),
    "TURKIYE_FINANS": ("TurkiyeFinans", ("turkiyefinans.com.tr",)),
    "ING": ("ING", ("ing.com.tr",)),
    "TEB": ("TEB", ("teb.com.tr",)),
    "VAKIF_KATILIM": ("VakifKatilim", ("vakifkatilim.com.tr",)),
    "VAKIFBANK": ("VakifBank", ("vakifbank.com.tr",)),
    "QNB": ("QNB", ("qnb.com.tr",)),
    "ZIRAAT": ("Ziraat", ("ziraatbank.com.tr",)),
    "KUVEYT_TURK": ("KuveytTurk", ("kuveytturk.com.tr",)),
    "GARANTI": ("Garanti", ("garantibbva.com.tr",)),
    "ENPARA": ("Enpara", ("enpara.com",)),
    "AKBANK": ("Akbank", ("akbank.com",)),
    "YAPIKREDI": ("YapiKredi", ("yapikredi.com.tr",)),
    "DENIZBANK": ("DenizBank", ("denizbank.com.tr", "denizbank.com")),
    "FIBABANKA": ("Fibabanka", ("fibabanka.com.tr",)),
    "UPT": ("UPT", ("upt.com.tr", "uption.com.tr")),
    "ZIRAATKATILIM": ("ZiraatKatilim", ("ziraatkatilim.com.tr",)),
    "ALBARAKA": ("Albaraka", ("albaraka.com.tr",)),
}

# OCR allowlist (only these may be detected by OCR)
OCR_DOMAIN_BANKS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "DENIZBANK": ("DenizBank", ("denizbank.com.tr", "denizbank.com")),
    "ZIRAATKATILIM": ("ZiraatKatilim", ("ziraatkatilim.com.tr",)),
    "ALBARAKA": ("Albaraka", ("albaraka.com.tr",)),
}

DENIZ_TEXT_MARKERS = (
    "denizbank a.s",
    "denizbank a.ş",
    "denizbank",
    "mobildeniz",
)


def detect_bank_by_text_domains(text_norm: str) -> Optional[dict]:
    for key, (bank_name, domains) in BANK_DOMAINS.items():
        for dom in domains:
            if has_domain(text_norm, dom):
                return {
                    "key": key,
                    "bank": bank_name,
                    "variant": None,
                    "method": "text-domain",
                }
    return None


def detect_deniz_by_text_name(text_norm: str) -> Optional[dict]:
    # Only used if NO domain found
    if any(m in text_norm for m in DENIZ_TEXT_MARKERS):
        return {
            "key": "DENIZBANK",
            "bank": "DenizBank",
            "variant": None,
            "method": "text-name",
        }
    return None


def _has_domain_ocr(text_norm: str, domain: str) -> bool:
    """
    OCR-tolerant matcher.
    Only used inside OCR allowlist flow.
    """
    if not text_norm or not domain:
        return False

    # First try normal matcher
    if has_domain(text_norm, domain):
        return True

    dom = (domain or "").casefold().strip()
    t = text_norm

    # Special-case: ziraatkatilim.com.tr often OCRs weirdly
    if dom == "ziraatkatilim.com.tr":
        pat = (
            r"(?:www\s*)?"
            r"z\s*i\s*r\s*a\s*(?:a|e)\s*t\s*"
            r"k\s*a\s*t\s*i\s*(?:l\s*)?(?:i|l)?\s*m\s*"
            r"(?:\s*\.?\s*)?"
            r"c\s*o\s*m\s*\.?\s*t\s*r"
        )
        if re.search(pat, t, flags=re.I):
            return True

        core = re.sub(r"[^a-z0-9]", "", t)
        return ("ziraatkatilimcomtr" in core) or ("ziraetkatiimcomtr" in core)

    return False


def detect_bank_by_ocr_domains(pdf_path: Path) -> Optional[dict]:
    raw = ocr_first_page_text(pdf_path)
    if not raw:
        return None

    t = normalize_text(raw)
    for key, (bank_name, domains) in OCR_DOMAIN_BANKS.items():
        for dom in domains:
            if _has_domain_ocr(t, dom):
                return {
                    "key": key,
                    "bank": bank_name,
                    "variant": None,
                    "method": "ocr-domain",
                }
    return None


def _variant_deniz(text_norm: str) -> Tuple[str, str]:
    if re.search(r"\bfast\b", text_norm):
        return "DENIZBANK", "FAST"
    return "DENIZBANK", "UNKNOWN"


def _variant_albaraka(text_norm: str) -> Tuple[str, str]:
    if re.search(r"\bfast\b", text_norm) or "fast sorgu numarasi" in text_norm:
        return "ALBARAKA", "FAST"
    return "ALBARAKA", "UNKNOWN"


VARIANT_AFTER_BANK = {
    "DENIZBANK": _variant_deniz,
    "ALBARAKA": _variant_albaraka,
}


def apply_variant(bank_key: str, text_norm: str) -> Tuple[str, Optional[str]]:
    fn = VARIANT_AFTER_BANK.get(bank_key)
    if not fn:
        return bank_key, None
    proposed_key, variant = fn(text_norm)
    return proposed_key, variant
