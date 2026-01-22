from .base import Platform, ParsedOrder, ParsedInvoice, parse_european_number
from .deliveroo import parse_deliveroo_invoice
from .glovo import parse_glovo_invoice
from .justeat import parse_justeat_invoice
from datetime import datetime


def detect_platform(filepath: str, content_sample: str = None) -> Platform:
    filename = filepath.lower()

    if "deliveroo" in filename or "statement" in filename or "pfood" in filename:
        return Platform.DELIVEROO
    if "glovo" in filename or "bill_" in filename:
        return Platform.GLOVO
    if "justeat" in filename or "just_eat" in filename or "je_" in filename or "fattura" in filename:
        return Platform.JUSTEAT

    if content_sample:
        if "Deliveroo" in content_sample or "Nome del ristorante" in content_sample:
            return Platform.DELIVEROO
        if "Glovo Code" in content_sample or "Glovo platform fee" in content_sample:
            return Platform.GLOVO
        if "Just Eat" in content_sample or "JUST EAT" in content_sample:
            return Platform.JUSTEAT

    return Platform.UNKNOWN


def parse_invoice(filepath: str) -> ParsedInvoice:
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            sample = f.read(2000)
    except:
        sample = ""

    platform = detect_platform(filepath, sample)

    if platform == Platform.DELIVEROO:
        return parse_deliveroo_invoice(filepath)
    elif platform == Platform.GLOVO:
        return parse_glovo_invoice(filepath)
    elif platform == Platform.JUSTEAT:
        return parse_justeat_invoice(filepath)
    else:
        result = ParsedInvoice(
            platform=Platform.UNKNOWN,
            filename=filepath,
            parse_date=datetime.now()
        )
        result.errors.append("Could not detect platform format")
        return result
