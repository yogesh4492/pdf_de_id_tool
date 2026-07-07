#!/usr/bin/env python3
"""De-identify PDFs by redacting names, emails, mobile numbers, and company names.

Accepts configuration parameters dynamically via a JSON file to customize manual overrides
and categories to redact.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

try:
    import fitz
except ImportError:
    fitz = None # Fallback if not fully installed yet

# We import fitz lazily inside functions so the script can compile and load even before PyMuPDF is fully installed.

# ═══════════════════════════════════════════════════════════════════════════════
#   DEFAULT CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_MANUAL_PERSONS: list[str] = [
    "Akash Verma",
    "Mr. Suresh Nair",
    "Mr. Upadhyay",
    "Proconnect",
    "Rohit Bhat at Anand",
    "Anand",
]

DEFAULT_MANUAL_COMPANIES: list[str] = [
    "Khaitan & Co",
    "Yebhi AI Training",
    "VP Legal and Company Secretary",
    "Trux App",
    "Truxapp",
    "TRUCKSAPP",
    "Emaar",
    "Deloitte",
    "Fidelity",
    "QUALCOMM",
    "HDFC",
    "DHL",
    "Nexus",
    "Fiedelity",
    "Walmart",
    "Quancomn",
    "Godrej",
    "Marico",
    "Pepfuels",
    "Microsoft 365",
    "Microsoft",
    "-HDFC-",
    "Simpson Thacher",
    "Cayman",
    "Nestle",
    "MS365",
    "Google",
    "Sequoia",
    "trucks"
]

DEFAULT_MANUAL_CIN_NO: list[str] = [
    "CIN: U72900DL2014PTC281355",
    "CIN: U74999DL2018PTC335XXX",
    "HDFC Current Account No. XXXX XXXX 4872 (IFSC:HDFC0001234)",
    "CIN: U74999DL2018PTC335XXX, GST: 07AAECP8388Q1Z5)",
]

DEFAULT_MANUAL_VEHICLES: list[str] = [
    "DL-1C-AB-7234",
    "MH-04-XYZ-1456",
]

DEFAULT_MANUAL_BAR_COUNCILS: list[str] = [
    "Bar Council Registration D/560/2009",
    "Bar No. IP/DEL/2014/0342",
]

DEFAULT_MANUAL_EMAILS: list[str] = []
DEFAULT_MANUAL_PHONES: list[str] = []
DEFAULT_MANUAL_BARS: list[str] = []

STOPWORD_EXCEPTIONS: set[str] = {
    "initially developed by"
}

# ─────────────────────────────────────────────────────────────
#  REDACTION APPEARANCE
# ─────────────────────────────────────────────────────────────
REDACT_LABEL: dict[str, str] = {
    "person":      "[NAME]",
    "company":     "[COMPANY]",
    "email":       "[EMAIL]",
    "phone":       "[PHONE]",
    "cin":         "[CIN]",
    "gst":         "[GST]",
    "ifsc":        "[IFSC]",
    "account":     "[ACCOUNT]",
    "vehicle":     "[VEHICLE]",
    "bar_council": "[BAR_COUNCIL]",
    "bar":         "[BAR]",
}
REDACT_FILL: dict[str, tuple] = {
    "person":      (0.85, 0.92, 1.0),   # light blue
    "company":     (0.85, 1.0,  0.88),  # light green
    "email":       (1.0,  0.95, 0.75),  # light amber
    "phone":       (0.95, 0.85, 1.0),   # light purple
    "cin":         (1.0,  0.88, 0.88),  # light red
    "gst":         (1.0,  0.93, 0.80),  # light orange
    "ifsc":        (0.88, 0.95, 1.0),   # light cyan
    "account":     (0.93, 0.88, 1.0),   # light violet
    "vehicle":     (0.95, 1.0,  0.80),  # light lime
    "bar_council": (1.0,  0.90, 0.95),  # light pink
    "bar":         (1.0,  0.75, 0.30),  # custom Gold/Orange
}
LABEL_TEXT_COLOR = (0.10, 0.10, 0.10)


# ─────────────────────────────────────────────────────────────
#  STOPWORDS
# ─────────────────────────────────────────────────────────────
_BASE_HARD_BANNED: set[str] = {
    "this", "investment", "invest", "fund", "company",
}
HARD_BANNED: set[str] = _BASE_HARD_BANNED - {w.lower() for w in STOPWORD_EXCEPTIONS}

_BASE_SOFT_BANNED: set[str] = _BASE_HARD_BANNED | {
    "a", "an", "and", "the",
    "best", "date", "from", "legal", "mobile",
    "regards", "report", "subject", "thanks", "team", "to",
    "business", "express", "global", "indian", "international",
    "limited", "national", "new", "pvt", "services", "solutions",
    "united", "attachment", "document", "draft", "email",
    "message", "note", "allocation", "policy", "strategy",
    "returns", "guarantee", "below",
}
SOFT_BANNED: set[str] = _BASE_SOFT_BANNED - {w.lower() for w in STOPWORD_EXCEPTIONS}

ALIAS_BLOCKED: set[str] = HARD_BANNED | {
    "a", "an", "and", "the", "pvt", "new", "global",
    "international", "national", "indian", "united",
}

PUBLIC_EMAIL_DOMAINS: set[str] = {
    "aol", "gmail", "hotmail", "icloud", "live", "msn", "outlook", "yahoo",
}


def _is_banned(term: str) -> bool:
    tokens = term.lower().split()
    if not tokens:
        return True
    if any(t in HARD_BANNED for t in tokens):
        return True
    if all(t in SOFT_BANNED for t in tokens):
        return True
    return False


# ─────────────────────────────────────────────────────────────
#  REGEX PATTERNS
# ─────────────────────────────────────────────────────────────
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

URL_DOMAIN_RE = re.compile(
    r"\b(?:https?://)?(?:www\.)?([A-Za-z0-9-]+)\.[A-Za-z]{2,}(?:/[^\s]*)?\b", re.I
)

PHONE_LABEL_RE = re.compile(
    r"(?i)\b(?:mobile|mob|phone|tel|telephone|cell|contact|whatsapp)"
    r"\b[:\s-]*([+\d][\d\s().-]{7,}\d)"
)
PHONE_MASK_RE = re.compile(
    r"(?i)(?<!\w)"
    r"(?:\+?\d[\d\s().-]*[xX]{6,}\d*|\+?\d[\d\s().-]*x{2,}\d{2,})"
    r"(?!\w)"
)

FIELD_LABEL_RE = re.compile(
    r"(?i)^\s*(from|to|cc|bcc|company|investor|client|vendor|counterparty|buyer|seller|"
    r"contact|prepared\s+by|signed\s+by|signatory|author|owner|attn)\s*:\s*(.*)$"
)

SIGNATURE_ROLE_RE = re.compile(
    r"(?i)\b(?:ceo|cto|cfo|co-founder|cofounder|founder|director|partner|advocate|"
    r"agent|counsel|manager|head|lead|associate|officer|coordinator|controller|"
    r"president|vp|vice\s+president)\b"
)

ORG_SUFFIX_RE = re.compile(
    r"\b(?:"
    r"[A-Z][\w&.'/-]+(?:\s+[A-Z][\w&.'/-]+){0,8}\s+"
    r"(?:Pvt\.?\s*Ltd|Private\s+Limited|LLP|Inc\.?|Corp\.?|Corporation|"
    r"Technologies|Technology|Ventures|Industries|Logistics|"
    r"Foods|Holdings|Capital|Lombard|Insurance|Motors|"
    r"Retail|Commerce|Fuels|Freight|Systems|Software|Digital|Labs)"
    r")\b"
)

PERSON_TITLE_RE = re.compile(
    r"(?i)\b(?:mr|mrs|ms|miss|dr|shri|smt|prof|adv|advocate)\.?\s+"
)
PERSON_CANDIDATE_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b")

CONTEXT_PERSON_PATTERNS = [
    re.compile(
        r"(?i)\b(?:contact|driver|attn|prepared\s+by|signed\s+by|coordinator|counsel|"
        r"advocate|manager|head|owner|author|rm|treasury)\s*:\s*"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})"
    ),
    re.compile(
        r"(?i)\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*\("
        r"(?:[^)]*\b(?:RM|SME|Treasury|Driver|Coordinator|Advocate|Counsel|CFO|"
        r"CEO|CTO|Founder|Manager|Head|Agent|Partner|Director|Officer)\b[^)]*)\)"
    ),
    re.compile(r"(?i)\b(?:dear|hi|hello)\s+([A-Z][a-z]{2,})\b"),
    re.compile(
        r"(?i)^(?:best|regards|thanks|sincerely|warm\s+regards|cheers),?\s+"
        r"([A-Z][a-z]{2,})\s*$"
    ),
]

COMMON_FIRST_NAMES: set[str] = {
    "Amit", "Akshay", "Aditya", "Ankit", "Deepak", "Manmohan",
    "Nikhil", "Priya", "Radhika", "Rohan", "Sandeep", "Srikant",
    "Varun", "Vaibhav", "Vikram", "Yogesh",
}

GENERIC_STOPWORDS_NAME: set[str] = {
    "And", "Best", "Date", "From", "Legal", "Mobile", "Regards",
    "Report", "Subject", "Thanks", "Team", "To", "This",
}

# ─────────────────────────────────────────────────────────────
#  CIN / GST / IFSC / ACCOUNT auto-detection regexes
# ─────────────────────────────────────────────────────────────
AUTO_CIN_RE  = re.compile(r"\bCIN\s*[:\-]?\s*[A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b", re.I)
AUTO_GST_RE  = re.compile(r"\bGST(?:IN|No\.?)?\s*[:\-]?\s*\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]\b", re.I)
AUTO_IFSC_RE = re.compile(r"\bIFSC\s*[:\-]?\s*[A-Z]{4}0[A-Z0-9]{6}\b", re.I)
AUTO_ACCT_RE = re.compile(
    r"\b(?:Account\s*No\.?|Acc(?:ount)?\s*No\.?|A/C)\s*[:\-]?\s*[\dXx*\s]{8,25}\b", re.I
)

# ─────────────────────────────────────────────────────────────
#  VEHICLE NUMBER auto-detection regex
# ─────────────────────────────────────────────────────────────
AUTO_VEHICLE_RE = re.compile(
    r"\b(?:"
    r"[A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{1,4}"
    r")\b",
    re.I,
)

# ─────────────────────────────────────────────────────────────
#  BAR COUNCIL NUMBER auto-detection regex
# ─────────────────────────────────────────────────────────────
AUTO_BAR_COUNCIL_RE = re.compile(
    r"(?i)\b(?:"
    r"Bar\s+Council(?:\s+(?:Registration|Reg\.?|No\.?|Number|Enrolment|Enrollment))?"
    r"|BCI(?:\s+(?:No\.?|Reg\.?|Number))?"
    r")\s*[:\-]?\s*"
    r"([A-Z]{1,4}[/\-]\d{1,6}(?:[/\-]\d{2,4})?)"
)


# ─────────────────────────────────────────────────────────────
#  HELPERS: parse manual entries into (value, kind) pairs
# ─────────────────────────────────────────────────────────────
_CIN_NO_PREFIX_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)^CIN\s*[:\-]?\s*"),        "cin"),
    (re.compile(r"(?i)^GST(?:IN|No\.?)?\s*[:\-]?\s*"), "gst"),
    (re.compile(r"(?i)^IFSC\s*[:\-]?\s*"),        "ifsc"),
    (re.compile(r"(?i)^(?:Account\s*No\.?|Acc(?:ount)?\s*No\.?|A/C)\s*[:\-]?\s*"), "account"),
    (re.compile(r"(?i)^(?:Vehicle\s*(?:No\.?|Number|Reg(?:istration)?\.?))\s*[:\-]?\s*"), "vehicle"),
    (re.compile(r"(?i)^(?:Bar\s+Council(?:\s+(?:Registration|Reg\.?|No\.?|Number|Enrolment|Enrollment))?|BCI(?:\s+(?:No\.?|Reg\.?))?)\s*[:\-]?\s*"), "bar_council"),
]

_INLINE_FRAGMENT_RES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\bCIN\s*[:\-]?\s*([A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b"),          "cin"),
    (re.compile(r"(?i)\bGST(?:IN|No\.?)?\s*[:\-]?\s*(\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9])\b"), "gst"),
    (re.compile(r"(?i)\bIFSC\s*[:\-]?\s*([A-Z]{4}0[A-Z0-9]{6})\b"),                           "ifsc"),
    (re.compile(r"(?i)\b(?:Account\s*No\.?|Acc(?:ount)?\s*No\.?|A/C)\s*[:\-]?\s*([\dXx*\s]{8,25})"), "account"),
    (re.compile(r"(?i)\bBar\s+Council(?:\s+(?:Registration|Reg\.?|No\.?|Number|Enrolment|Enrollment))?\s*[:\-]?\s*([A-Z]{1,4}[/\-]\d{1,6}(?:[/\-]\d{2,4})?)"), "bar_council"),
]


def _is_vehicle_number(text: str) -> bool:
    return bool(AUTO_VEHICLE_RE.fullmatch(text.strip()))


def _parse_cin_no_entry(raw: str) -> list[tuple[str, str]]:
    entry = raw.strip().strip("()")
    results: list[tuple[str, str]] = []
    seen_values: set[str] = set()

    def _add(text: str, kind: str) -> None:
        text = re.sub(r"\s+", " ", text).strip()
        if text and text not in seen_values:
            seen_values.add(text)
            results.append((text, kind))

    if _is_vehicle_number(entry):
        _add(entry, "vehicle")
        return results

    for pattern, kind in _INLINE_FRAGMENT_RES:
        for m in pattern.finditer(entry):
            _add(m.group(0).strip(), kind)
            _add(m.group(1).strip(), kind)

    if results:
        return results

    for prefix_re, kind in _CIN_NO_PREFIX_MAP:
        m = prefix_re.match(entry)
        if m:
            value = entry[m.end():].strip().strip("()")
            value = re.sub(r"\s+", " ", value)
            _add(entry, kind)
            _add(value, kind)
            return results

    _add(entry, "account")
    return results


# ─────────────────────────────────────────────────────────────
#  DATA CLASS
# ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Entity:
    value: str
    kind: str   # person | company | email | phone | cin | gst | ifsc | account | vehicle | bar_council | bar


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean(value: str) -> str:
    return normalize_ws(value).strip(" .;,:")


def split_recipients(value: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\s*;\s*", value) if p.strip()]
    result: list[str] = []
    for part in parts:
        part = normalize_ws(part).split("(", 1)[0].strip()
        if "," in part:
            first, rest = [s.strip() for s in part.split(",", 1)]
            if first and rest and not SIGNATURE_ROLE_RE.search(rest):
                part = first
        part = PERSON_TITLE_RE.sub("", part).strip()
        if part:
            result.append(part)
    return result


def _is_company_candidate(candidate: str) -> bool:
    candidate = _clean(candidate)
    if not candidate or _is_banned(candidate):
        return False
    tokens = candidate.split()
    if len(tokens) == 1:
        tok = tokens[0]
        if tok.lower() in SOFT_BANNED:
            return False
        if tok.isupper() and len(tok) >= 2:
            return True
        if re.search(r"[A-Z].*[a-z]|[a-z].*[A-Z]|\d", tok):
            return True
        return False
    if tokens[0].lower() in SOFT_BANNED:
        return False
    return True


# ─────────────────────────────────────────────────────────────
#  ENTITY EXTRACTION
# ─────────────────────────────────────────────────────────────
def extract_entities_from_text(
    text: str,
    manual_persons: list[str],
    manual_companies: list[str],
    manual_vehicles: list[str],
    manual_bar_councils: list[str],
    manual_emails: list[str],
    manual_phones: list[str],
    manual_cin_no: list[str],
    manual_bars: list[str],
    manual_cins: list[str] | None = None,
    manual_gsts: list[str] | None = None,
    manual_ifscs: list[str] | None = None,
    manual_accounts: list[str] | None = None,
) -> list[Entity]:
    entities: list[Entity] = []
    seen: set[tuple[str, str]] = set()

    def add(raw: str, kind: str) -> None:
        value = _clean(raw)
        if not value or _is_banned(value):
            return
        key = (value, kind)
        if key not in seen:
            seen.add(key)
            entities.append(Entity(value=value, kind=kind))

    def add_manual(raw: str, kind: str) -> None:
        value = _clean(raw)
        if not value:
            return
        key = (value, kind)
        if key not in seen:
            seen.add(key)
            entities.append(Entity(value=value, kind=kind))

    # ── Manual overrides (using dynamically provided ones or defaults) ──
    for entry in manual_persons:
        add_manual(entry, "person")

    for entry in manual_companies:
        add_manual(entry, "company")

    for entry in manual_emails:
        add_manual(entry, "email")

    for entry in manual_phones:
        add_manual(entry, "phone")

    for entry in manual_bars:
        add_manual(entry, "bar")

    for entry in manual_vehicles:
        add_manual(entry, "vehicle")

    for entry in manual_bar_councils:
        for t, kind in _parse_cin_no_entry(entry):
            add_manual(t, "bar_council")

    for entry in manual_cin_no:
        for t, kind in _parse_cin_no_entry(entry):
            add_manual(t, kind)

    if manual_cins:
        for entry in manual_cins:
            add_manual(entry, "cin")

    if manual_gsts:
        for entry in manual_gsts:
            add_manual(entry, "gst")

    if manual_ifscs:
        for entry in manual_ifscs:
            add_manual(entry, "ifsc")

    if manual_accounts:
        for entry in manual_accounts:
            add_manual(entry, "account")

    # ── Auto-detect CIN / GST / IFSC / Account ────────────────
    for pattern, kind in [
        (AUTO_CIN_RE,  "cin"),
        (AUTO_GST_RE,  "gst"),
        (AUTO_IFSC_RE, "ifsc"),
        (AUTO_ACCT_RE, "account"),
    ]:
        for m in pattern.finditer(text):
            add_manual(normalize_ws(m.group(0)), kind)

    # ── Auto-detect Vehicle Numbers ──────────────────────
    for m in AUTO_VEHICLE_RE.finditer(text):
        candidate = normalize_ws(m.group(0))
        if len(re.sub(r"\D", "", candidate)) >= 1 and len(candidate) >= 5:
            add_manual(candidate, "vehicle")

    # ── Auto-detect Bar Council Numbers ──────────────────
    for m in AUTO_BAR_COUNCIL_RE.finditer(text):
        full_match = normalize_ws(m.group(0))
        value_only = normalize_ws(m.group(1))
        add_manual(full_match, "bar_council")
        add_manual(value_only, "bar_council")

    # ── Emails ────────────────────────────────────────────────
    for email in EMAIL_RE.findall(text):
        add(email, "email")
        domain_part = email.split("@", 1)[1].split(".", 1)[0].lower()
        if (
            domain_part
            and domain_part not in PUBLIC_EMAIL_DOMAINS
            and len(domain_part) >= 4
            and domain_part not in SOFT_BANNED
        ):
            add(domain_part, "company")

    # ── URL domains ───────────────────────────────────────────
    for domain in URL_DOMAIN_RE.findall(text):
        domain = domain.lower()
        if domain and domain not in PUBLIC_EMAIL_DOMAINS and domain != "www" and len(domain) >= 4:
            add(domain, "company")

    # ── Phone via labels ──────────────────────────────────────
    for match in PHONE_LABEL_RE.finditer(text):
        candidate = normalize_ws(match.group(1))
        if 8 <= len(re.sub(r"\D", "", candidate)) <= 15:
            add(candidate, "phone")

    for match in PHONE_MASK_RE.finditer(text):
        candidate = normalize_ws(match.group(0))
        add(candidate, "phone")

    # ── Line-by-line structure ────────────────────────────────
    for raw_line in text.splitlines():
        line = normalize_ws(raw_line)
        if not line:
            continue

        m = FIELD_LABEL_RE.match(line)
        if m:
            label = m.group(1).lower().replace(" ", "_")
            value = m.group(2).strip()

            if label in {
                "from", "to", "cc", "bcc", "contact", "attn",
                "prepared_by", "signed_by", "signatory", "author", "owner",
            }:
                for item in split_recipients(value):
                    add(item, "person")

            elif label in {
                "company", "investor", "client", "vendor",
                "counterparty", "buyer", "seller",
            }:
                candidate = _clean(value.split("(", 1)[0].split(",", 1)[0])
                if _is_company_candidate(candidate):
                    add(candidate, "company")

        for match in ORG_SUFFIX_RE.finditer(line):
            candidate = match.group(0)
            if _is_company_candidate(candidate):
                add(candidate, "company")

        for match in PERSON_CANDIDATE_RE.finditer(line):
            candidate = match.group(0)
            if candidate.split()[0] in COMMON_FIRST_NAMES:
                add(candidate, "person")

        for pattern in CONTEXT_PERSON_PATTERNS:
            for match in pattern.finditer(line):
                candidate = match.group(1)
                if candidate and candidate not in GENERIC_STOPWORDS_NAME:
                    add(candidate, "person")

        sig_m = re.match(
            r"(?i)^(?:best|regards|thanks|sincerely|warm\s+regards|cheers),?\s+"
            r"([A-Z][a-z]{2,})\s*$",
            line,
        )
        if sig_m:
            token = sig_m.group(1)
            if token not in GENERIC_STOPWORDS_NAME:
                add(token, "person")

        # Dynamic scanner checks
        for entry in manual_persons:
            if entry.lower() in line.lower():
                add_manual(entry, "person")

        for entry in manual_companies:
            if entry.lower() in line.lower():
                add_manual(entry, "company")

        for entry in manual_bars:
            if entry.lower() in line.lower():
                add_manual(entry, "bar")

        for entry in manual_vehicles:
            if entry.lower() in line.lower():
                add_manual(entry, "vehicle")

        for entry in manual_bar_councils:
            if entry.lower() in line.lower():
                for t, kind in _parse_cin_no_entry(entry):
                    add_manual(t, "bar_council")

        for entry in manual_cin_no:
            for t, kind in _parse_cin_no_entry(entry):
                if t.lower() in line.lower():
                    add_manual(t, kind)

        for mv in AUTO_VEHICLE_RE.finditer(line):
            candidate = normalize_ws(mv.group(0))
            if len(re.sub(r"\D", "", candidate)) >= 1 and len(candidate) >= 5:
                add_manual(candidate, "vehicle")

        for mb in AUTO_BAR_COUNCIL_RE.finditer(line):
            add_manual(normalize_ws(mb.group(0)), "bar_council")
            add_manual(normalize_ws(mb.group(1)), "bar_council")

    return entities


def entity_aliases(entity: Entity) -> list[str]:
    aliases = [entity.value]

    if entity.kind == "person":
        tokens = entity.value.split()
        if len(tokens) >= 2:
            first = tokens[0]
            if first not in GENERIC_STOPWORDS_NAME and first.lower() not in ALIAS_BLOCKED:
                aliases.append(first)

    if entity.kind == "company":
        tokens = entity.value.split()
        if tokens:
            first = tokens[0]
            if (
                len(first) >= 3
                and first.lower() not in ALIAS_BLOCKED
                and not _is_banned(first)
            ):
                aliases.append(first)
        if entity.value.endswith(".com"):
            aliases.append(entity.value[:-4])

    return aliases


# ─────────────────────────────────────────────────────────────
#  WORD-LEVEL RECT SEARCH  (fallback)
# ─────────────────────────────────────────────────────────────
def _norm_word(word: str) -> str:
    return word.strip(" \t\r\n.,;:()[]{}<>|\"'`").replace("\u2019", "'")


def word_sequence_rects(page: fitz.Page, term: str) -> list[fitz.Rect]:
    import fitz
    term_tokens = [_norm_word(t) for t in term.split() if _norm_word(t)]
    if not term_tokens:
        return []

    page_words = [
        (_norm_word(w).lower(), fitz.Rect(x0, y0, x1, y1))
        for x0, y0, x1, y1, w, *_ in page.get_text("words")
        if _norm_word(w)
    ]
    if not page_words:
        return []

    target = [t.lower() for t in term_tokens]
    n = len(target)
    rects: list[fitz.Rect] = []
    for i in range(len(page_words) - n + 1):
        window = page_words[i: i + n]
        if [tok for tok, _ in window] == target:
            rect = window[0][1]
            for _, r in window[1:]:
                rect |= r
            rects.append(rect)
    return rects


# ─────────────────────────────────────────────────────────────
#  OVERLAP RESOLUTION
# ─────────────────────────────────────────────────────────────
def _rects_overlap(a: fitz.Rect, b: fitz.Rect, tol: float = 2.0) -> bool:
    return (
        a.x0 < b.x1 + tol and a.x1 > b.x0 - tol and
        a.y0 < b.y1 + tol and a.y1 > b.y0 - tol
    )


def _merge_hits(
    hits: list[tuple[fitz.Rect, str]]
) -> list[tuple[fitz.Rect, str]]:
    if not hits:
        return []

    merged: list[tuple[fitz.Rect, str]] = []
    for rect, kind in hits:
        absorbed = False
        for i, (existing_rect, existing_kind) in enumerate(merged):
            if _rects_overlap(existing_rect, rect):
                merged[i] = (existing_rect | rect, existing_kind)
                absorbed = True
                break
        if not absorbed:
            merged.append((rect, kind))

    return merged


# ─────────────────────────────────────────────────────────────
#  REDACTION APPLICATION
# ─────────────────────────────────────────────────────────────
def _apply_redaction(page: fitz.Page, rect: fitz.Rect, kind: str) -> None:
    label = REDACT_LABEL.get(kind, "[REDACTED]")
    fill  = REDACT_FILL.get(kind, (0.9, 0.9, 0.9))
    page.add_redact_annot(
        rect,
        text=label,
        fontsize=7,
        fontname="helv",
        text_color=LABEL_TEXT_COLOR,
        fill=fill,
        align=fitz.TEXT_ALIGN_CENTER,
    )


def redact_pdf(
    input_path: Path,
    output_path: Path,
    config: dict,
    *,
    min_term_length: int = 2,
) -> tuple[Counter, list[dict[str, str]], str, str]:
    import fitz
    
    # Load settings from dynamic config
    manual_persons = config.get("manual_persons", DEFAULT_MANUAL_PERSONS)
    manual_companies = config.get("manual_companies", DEFAULT_MANUAL_COMPANIES)
    manual_vehicles = config.get("manual_vehicles", DEFAULT_MANUAL_VEHICLES)
    manual_bar_councils = config.get("manual_bar_councils", DEFAULT_MANUAL_BAR_COUNCILS)
    manual_emails = config.get("manual_emails", DEFAULT_MANUAL_EMAILS)
    manual_phones = config.get("manual_phones", DEFAULT_MANUAL_PHONES)
    manual_cin_no = config.get("manual_cin_no", DEFAULT_MANUAL_CIN_NO)
    manual_bars = config.get("manual_bars", DEFAULT_MANUAL_BARS)
    manual_cins = config.get("manual_cins", [])
    manual_gsts = config.get("manual_gsts", [])
    manual_ifscs = config.get("manual_ifscs", [])
    manual_accounts = config.get("manual_accounts", [])
    
    # Selected PII categories to redact (all by default)
    redact_categories = set(config.get("redact_categories", list(REDACT_LABEL.keys())))

    doc = fitz.open(input_path)
    all_text = "\n".join(page.get_text("text") for page in doc)

    # Extract all entities from document text
    extracted_entities = extract_entities_from_text(
        all_text,
        manual_persons,
        manual_companies,
        manual_vehicles,
        manual_bar_councils,
        manual_emails,
        manual_phones,
        manual_cin_no,
        manual_bars,
        manual_cins=manual_cins,
        manual_gsts=manual_gsts,
        manual_ifscs=manual_ifscs,
        manual_accounts=manual_accounts
    )
    
    term_kind: dict[str, str] = {}
    for entity in extracted_entities:
        for alias in entity_aliases(entity):
            alias = normalize_ws(alias)
            if len(alias) >= min_term_length and not _is_banned(alias):
                if alias not in term_kind:
                    term_kind[alias] = entity.kind

    # Force-inject manual overrides
    for entry in manual_persons:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "person"

    for entry in manual_companies:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "company"

    for entry in manual_emails:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "email"

    for entry in manual_phones:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "phone"

    for entry in manual_bars:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "bar"

    for entry in manual_vehicles:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "vehicle"

    for raw_entry in manual_bar_councils:
        for text, kind in _parse_cin_no_entry(raw_entry):
            text = normalize_ws(text)
            if text and len(text) >= min_term_length:
                term_kind[text] = "bar_council"

    for raw_entry in manual_cin_no:
        for text, kind in _parse_cin_no_entry(raw_entry):
            text = normalize_ws(text)
            if text and len(text) >= min_term_length:
                term_kind[text] = kind

    for entry in manual_cins:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "cin"

    for entry in manual_gsts:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "gst"

    for entry in manual_ifscs:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "ifsc"

    for entry in manual_accounts:
        entry = normalize_ws(entry)
        if entry and len(entry) >= min_term_length:
            term_kind[entry] = "account"

    sorted_terms = sorted(term_kind.items(), key=lambda kv: -len(kv[0]))
    counters: Counter = Counter()

    for page in doc:
        page_text = page.get_text("text")
        raw_hits: list[tuple[fitz.Rect, str]] = []

        for term, kind in sorted_terms:
            # Check if this category should be redacted
            if kind not in redact_categories:
                continue
            rects = page.search_for(term)
            if not rects:
                rects = word_sequence_rects(page, term)
            for rect in rects:
                raw_hits.append((rect, kind))

        # Phone number pass
        if "phone" in redact_categories:
            for match in PHONE_LABEL_RE.finditer(page_text):
                candidate = normalize_ws(match.group(1))
                if 8 <= len(re.sub(r"\D", "", candidate)) <= 15:
                    rects = page.search_for(candidate) or word_sequence_rects(page, candidate)
                    for rect in rects:
                        raw_hits.append((rect, "phone"))

            for match in PHONE_MASK_RE.finditer(page_text):
                candidate = normalize_ws(match.group(0))
                rects = page.search_for(candidate) or word_sequence_rects(page, candidate)
                for rect in rects:
                    raw_hits.append((rect, "phone"))

        # CIN / GST / IFSC / Account pass
        for pattern, kind in [
            (AUTO_CIN_RE,  "cin"),
            (AUTO_GST_RE,  "gst"),
            (AUTO_IFSC_RE, "ifsc"),
            (AUTO_ACCT_RE, "account"),
        ]:
            if kind in redact_categories:
                for m in pattern.finditer(page_text):
                    candidate = normalize_ws(m.group(0))
                    rects = page.search_for(candidate) or word_sequence_rects(page, candidate)
                    for rect in rects:
                        raw_hits.append((rect, kind))

        # Vehicle Number pass
        if "vehicle" in redact_categories:
            for m in AUTO_VEHICLE_RE.finditer(page_text):
                candidate = normalize_ws(m.group(0))
                if len(re.sub(r"\D", "", candidate)) >= 1 and len(candidate) >= 5:
                    rects = page.search_for(candidate) or word_sequence_rects(page, candidate)
                    for rect in rects:
                        raw_hits.append((rect, "vehicle"))

        # Bar Council Number pass
        if "bar_council" in redact_categories:
            for m in AUTO_BAR_COUNCIL_RE.finditer(page_text):
                for candidate in (normalize_ws(m.group(0)), normalize_ws(m.group(1))):
                    rects = page.search_for(candidate) or word_sequence_rects(page, candidate)
                    for rect in rects:
                        raw_hits.append((rect, "bar_council"))

        raw_hits.sort(key=lambda h: -(h[0].width * h[0].height))
        merged = _merge_hits(raw_hits)

        for rect, kind in merged:
            _apply_redaction(page, rect, kind)
            counters[kind] += 1

        page.apply_redactions(images=2, graphics=1, text=0)

    # Save to output path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path, deflate=True, garbage=4)
    doc.close()

    # Create sorted list of unique extracted entities to return for UI display
    unique_entities = []
    seen_unique = set()
    for ent in extracted_entities:
        k = (ent.value, ent.kind)
        if k not in seen_unique:
            seen_unique.add(k)
            unique_entities.append({"value": ent.value, "kind": ent.kind})

    # Prepare redacted version of plain text for side-by-side view
    redacted_text = all_text
    # We replace longer terms first to prevent partial redactions
    for term, kind in sorted(term_kind.items(), key=lambda kv: -len(kv[0])):
        if kind in redact_categories:
            label = REDACT_LABEL.get(kind, "[REDACTED]")
            # Escape term for safe regex replacement with boundaries or exact matches
            escaped_term = re.escape(term)
            redacted_text = re.sub(rf"(?i)\b{escaped_term}\b", label, redacted_text)
            # Also fall back to general replacement if word boundaries fail (for accounts / emails, etc.)
            if "@" in term or "/" in term or "-" in term or ":" in term:
                redacted_text = redacted_text.replace(term, label)

    return counters, unique_entities, all_text, redacted_text


# ─────────────────────────────────────────────────────────────
#  MAIN ENTRY
# ─────────────────────────────────────────────────────────────
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input PDF file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output PDF file")
    parser.add_argument("-c", "--config", type=Path, help="Path to config JSON file")
    args = parser.parse_args(argv)

    input_path: Path = args.input
    output_path: Path = args.output
    config_path: Path | None = args.config

    config = {}
    if config_path and config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"Failed to parse config: {str(e)}"}))
            return 1

    try:
        import fitz
    except ImportError:
        print(json.dumps({
            "status": "error", 
            "message": "PyMuPDF (fitz) is not installed. Please run: pip install pymupdf"
        }))
        return 1

    if not input_path.exists() or not input_path.is_file():
        print(json.dumps({"status": "error", "message": f"Input file does not exist: {input_path}"}))
        return 1

    try:
        counters, entities, raw_text, redacted_text = redact_pdf(input_path, output_path, config)
        
        # Output result metadata to stdout as JSON
        print(json.dumps({
            "status": "success",
            "counts": dict(counters),
            "entities": entities,
            "raw_text": raw_text[:50000],  # cap at 50k characters for safe JSON transport
            "redacted_text": redacted_text[:50000]
        }, ensure_ascii=False))
        return 0
    except Exception as e:
        import traceback
        print(json.dumps({
            "status": "error", 
            "message": f"Redaction failed: {str(e)}",
            "traceback": traceback.format_exc()
        }))
        return 1


if __name__ == "__main__":
    sys.exit(main())
