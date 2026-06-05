"""
payee_normalizer.py

Hybrid payee normalisation engine for bank/YNAB-style transactions.

Strategy:
    1. Handle special classes first (PIRB, ATM, fees, transfers).
    2. Strip payment processor / POS prefixes (Zettle, SumUp, SQ, SP, etc.).
    3. Apply a canonical-name dictionary using a simplified key.
    4. Fallback: tidy whitespace / obvious artefacts, return cleaned name.

Extend by:
    - Adding new patterns in STRIP_PREFIX_PATTERNS.
    - Adding entries to CANONICAL_MAP.
"""

from __future__ import annotations
import re
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# 1. Canonical map (simplified-key -> canonical name)
#    Keys are generated with `simplify_key` (lowercased, punctuation stripped).
#    Add to this as you discover more useful groupings.
# ---------------------------------------------------------------------------

CANONICAL_MAP: Dict[str, str] = {
    # --- Supermarkets & general retail ---
    "tesco": "Tesco",
    "sainsburys": "Sainsbury's",
    "sainsburys smkt": "Sainsbury's",
    "sainsburys supermarket": "Sainsbury's",
    "sainsburyscouk": "Sainsbury's",
    "asda": "Asda",
    "aldi": "Aldi",
    "lidl": "Lidl",
    "morrisons": "Morrisons",
    "wm morrisons petrol": "Morrisons Petrol Station",
    "wm morrisons petrol station": "Morrisons Petrol Station",
    "morrisons petrol": "Morrisons Petrol Station",
    "morr woking": "Morrisons",
    "co op": "Co-op",
    "coop": "Co-op",
    "spar": "Spar",
    "iceland": "Iceland",
    "whsmith": "WHSmith",
    "wh smith": "WHSmith",
    "waterstones": "Waterstones",
    "boots": "Boots",
    "superdrug": "Superdrug",
    "poundland": "Poundland",
    "home bargains": "Home Bargains",
    "b m": "B&M",
    "b&m": "B&M",

    # --- Online / marketplaces ---
    "amazon": "Amazon",
    "amznmktplace": "Amazon",
    "amazoncouk": "Amazon",
    "amazon prime video": "Amazon Prime Video",
    "abebooks": "AbeBooks",
    "abe books": "AbeBooks",
    "sp worldofbookscom": "Wob (World of Books)",
    "worldofbookscom": "Wob (World of Books)",
    "wob": "Wob (World of Books)",
    "ebay": "eBay",
    "back market": "Back Market",
    "livecareer": "LiveCareer",
    "datmanje": "Datman",
    "ynab": "You Need A Budget",
    "you need a budget": "You Need A Budget",
    "youneedabudgetcom": "You Need A Budget",

    # --- Coffee / cafes & chains ---
    "costa coffee": "Costa Coffee",
    "costacoffee 43011185": "Costa Coffee",
    "pret a manger": "Pret A Manger",
    "caffe nero": "Caffè Nero",
    "starbucks": "Starbucks",
    "black sheep coffee": "Black Sheep Coffee",
    "benugo": "Benugo",
    "upper crust": "Upper Crust",

    # --- Food & restaurants (just a few common ones; extend as needed) ---
    "mcdonalds": "McDonald's",
    "mcdonald's": "McDonald's",
    "kfc": "KFC",
    "brewers fayre": "Brewers Fayre",
    "whataburger 1134": "Whataburger",
    "burger buzz": "Burger Buzz",
    "pho cue": "Pho Cue",
    "bep viet": "Bep Viet",
    "waffle station limited": "Waffle Station",
    "sumup waffle station": "Waffle Station",

    # --- Petrol / EV charging / transport services ---
    "esso": "Esso",
    "shell": "Shell",
    "esso shrewsbury sstn": "Esso",
    "octopus energy": "Octopus Energy",
    "octopus electroverse": "Octopus Electroverse",
    "connected kerb": "Connected Kerb",
    "mer charging uk": "Mer Charging UK",
    "pod point": "Pod Point",

    # --- Rail / transport operators ---
    "trainline": "Trainline",
    "avanti west coast": "Avanti West Coast",
    "www avantiwestcoast co": "Avanti West Coast",
    "great western railway": "Great Western Railway",
    "greate western trai": "Great Western Railway",
    "south western railway": "South Western Railway",
    "sw railway app": "South Western Railway",
    "transport for wales": "Transport for Wales",
    "crosscountry": "CrossCountry",
    "northern rail": "Northern Rail",
    "eurostar international li": "Eurostar",
    "www avivantiwestcoast co": "Avanti West Coast",

    # --- Parking & road tolls ---
    "yourparkingspace": "YourParkingSpace",
    "ringgo": "RingGo",
    "parkingeye": "ParkingEye",
    "apcoa parking": "APCOA Parking",
    "apcoa hal ss t4": "APCOA Parking",
    "justpark": "JustPark",

    # --- Subscriptions & media ---
    "chatgpt subscription": "ChatGPT Subscription",
    "netflix": "Netflix",
    "dazn limited": "DAZN",
    "times newspapers ltd": "The Times",
    "times newspapers": "The Times",
    "spotify": "Spotify",
    "betterme fasting": "BetterMe Fasting",
    "impactsuite healthapps": "Impact Suite (Health Apps)",
    "ihealthproco": "iHealthPro",
    "muscle boosterio": "Muscle Booster",
    "microsoft": "Microsoft",
    "microsoft microsoft 365 f": "Microsoft 365 Family",
    "microsoft microsoft 365": "Microsoft 365",
    "microsoft*microsof 365 f": "Microsoft 365 Family",
    "chatgpt subscription": "ChatGPT Subscription",

    # --- Charities / donations ---
    "unicef uk": "Unicef UK",
    "cancer research": "Cancer Research UK",
    "scripture union": "Scripture Union",
    "world health organ": "World Health Organization",
    "wikimedia": "Wikimedia Foundation",
    "british heart foundation": "British Heart Foundation",

    # --- National Trust / heritage / museums ---
    "national trust": "National Trust",
    "national trust ham house and garden": "National Trust (Ham House & Garden)",
    "science industry museum r": "Science and Industry Museum",
    "the potteries museum": "The Potteries Museum & Art Gallery",
    "chatsworth house": "Chatsworth House",
    "chatsworthorg": "Chatsworth House",
    "the forbidden corner": "The Forbidden Corner",

    # --- Education / exam boards / universities ---
    "abrsm": "ABRSM",
    "abrsmorg": "ABRSM",
    "abrsml org": "ABRSM",
    "abrsmt": "ABRSM",
    "hm passport office": "HM Passport Office",
    "university of sussex do": "University of Sussex",
    "university of sussex th": "University of Sussex",
    "university of sussex ea": "University of Sussex",
    "univ of glasgow": "University of Glasgow",

    # --- Banking & cashback items ---
    "nationwide cashback feb": "Nationwide Cashback",
    "nationwide cashback mar": "Nationwide Cashback",
    "nationwide cashback apr": "Nationwide Cashback",
    "nationwide fairer share payment": "Nationwide Fairer Share Payment",
    "the big nationwide thank you": "The Big Nationwide Thank You",

    # --- Councils / utilities (sample) ---
    "abta": "ABTA",
    "octopus energy": "Octopus Energy",
    "affinity water": "Affinity Water",
    "bath north east somerset council": "Bath & North East Somerset Council",
    "torbaycouncil": "Torbay Council",

    # --- Misc / other common merchants in your data ---
    "waterfront cafe": "Waterfront Cafe",
    "waterfront caf": "Waterfront Cafe",
    "waterfront caf": "Waterfront Cafe",
    "waterfront cafes": "Waterfront Cafe",
    "st peters hospital multi storey car park": "St. Peter's Hospital Car Park",
    "school photography co": "School Photography Company",
    "gear4music limited": "Gear4music",
    "sportsbikeshop ltd": "SPORTSBIKESHOP",
    "military mart": "Military Mart",
    "minerva fabrics ltd": "Minerva Fabrics",
    "minerva fabrics": "Minerva Fabrics",
    "www minervacrafts com": "Minerva Crafts",
    "www sewdirect com": "Sew Direct",
    "omaze uk": "Omaze",
    "omaze": "Omaze",
}


# ---------------------------------------------------------------------------
# 2. Helper functions
# ---------------------------------------------------------------------------

def simplify_key(name: str) -> str:
    """
    Create a normalised key for dictionary lookup:
      - lowercase
      - remove non-alphanumeric -> spaces
      - collapse spaces
    """
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_payment_prefixes(name: str) -> str:
    """
    Remove payment processor / POS prefixes that wrap the real merchant.
    Applies repeatedly until no change.
    """
    patterns = [
        r"^ZETTLE[_\s\*]+",          # ZETTLE_*CHILDREN S TOY
        r"^ZETTLE\*[_\s]*",          # ZETTLE_*ULTIMATE HEATI
        r"^ZETTLE\s*\*",             # ZETTLE_*FIRST COFFEE LTD
        r"^ZETTLE\s*",               # Zettle
        r"^ZETTLE_",                 # ZETTLE_*FOO
        r"^SUMUP\s*\*",              # SUMUP *WAFFLE STATION LI
        r"^SUMUP\s+",                # SUMUP foo
        r"^SUMUP_",                  # SUMUP_*FOO
        r"^SP\s*\*?",                # SP ATTIRECO / SP*ATTIRECO
        r"^NY[AX]\s*\*",             # NYA* / NYX*
        r"^WP\*",                    # WP*Woking Gymnastics C
        r"^EB\s*\*",                 # EB *UK PANDEMIC SCIENC
        r"^PAYPAL\s*\*",             # PAYPAL *JD MUSIC
        r"^VMS\*",                   # VMS*iPayimpact.co.uk
        r"^STP\*V\*",                # STP*V*theliven com
    ]
    changed = True
    s = name
    while changed:
        changed = False
        for pat in patterns:
            new_s = re.sub(pat, "", s, flags=re.IGNORECASE).lstrip()
            if new_s != s:
                s = new_s
                changed = True
    return s


def normalise_transfer_like(name: str) -> Optional[str]:
    """
    Normalise 'Payment to ...' and 'Transfer to/from ...' formats.

    Example:
        'Payment to SURREY FLOORS & DO 2024-02-09'
        -> 'Transfer – Surrey Floors & Do'
    """
    # Generic "Payment to"/"Transfer to"/"Transfer from"
    m = re.match(
        r"^(payment to|transfer to|transfer from)\s+(.+?)\s*(\d{2,}-\d{2,}-\d{2,}.*|\d{2,}\s+\d{2,}.*)?$",
        name,
        flags=re.IGNORECASE,
    )
    if m:
        raw_name = m.group(2)
        cleaned = tidy_text(raw_name)
        if cleaned:
            return f"Transfer \u2013 {cleaned}"

    # 'Transfer to 071520 67650231' (no name) – leave as-is
    return None


def tidy_text(name: str) -> str:
    """
    Final cleanup pass:
      - replace stray ? from encoding with apostrophe or remove
      - collapse whitespace
      - strip trailing commas/periods
    """
    s = name.replace(" ?", "'")  # simple heuristic for mis-encoded apostrophes
    s = re.sub(r"\s+", " ", s).strip()
    s = s.rstrip(",.")
    return s


# ---------------------------------------------------------------------------
# 3. Main entry point
# ---------------------------------------------------------------------------

def normalize_payee(raw_name: str) -> str:
    """
    Normalise a single payee / merchant string into a canonical form.

    This is intentionally conservative: if we don't recognise the pattern,
    we just return a tidied version of the input.
    """
    if raw_name is None:
        return ""

    original = raw_name
    s = raw_name.strip()
    if not s:
        return ""

    # -----------------------------
    # ABSOLUTE FIRST: Square (SQ) prefix removal
    # -----------------------------
    s0 = s.lstrip("\ufeff\u200b")  # BOM / zero-width safety

    if s0[:2].upper() == "SQ":
        # Handles: "SQ *FOO", "SQ*FOO", "SQ  *  FOO", "SQ FOO"
        if "*" in s0:
            s = s0.split("*", 1)[1].strip()
        else:
            s = s0[2:].strip(" -")

    # -----------------------------
    # 3.1 Hard-coded special cases
    # -----------------------------

    lower = s.lower()

    # ATM withdrawals
    if lower.startswith("atm withdrawal"):
        return "ATM Withdrawal"

    # Generic cash / cheque indicators
    if lower.startswith("cheque "):
        # e.g. 'Cheque 800023'
        return "Cheque"

    # Non-sterling / FX fees
    if "non-sterling transaction fee" in lower or "foreign currency transaction fee" in lower:
        return "Non-Sterling Fee"

    # The Pirbright Institute (all PIRB codes etc.)
    if re.search(r"(?:^|\d)\d*\s*the\s+pirb\b", lower):
        return "The Pirbright Institute"

    # Nationwide cashback / fairer share
    if lower.startswith("nationwide cashback"):
        return "Nationwide Cashback"
    if "fairer share payment" in lower:
        return "Nationwide Fairer Share Payment"

    # Generic 'Nationwide cashback XXX' (month code)
    if re.match(r"^nationwide cashback\b", lower):
        return "Nationwide Cashback"

    # -----------------------------
    # 3.2 Transfers / payments
    # -----------------------------
    transfer_name = normalise_transfer_like(s)
    if transfer_name is not None:
        return transfer_name

    # -----------------------------
    # 3.3 Strip payment processor prefixes
    # -----------------------------
    s = strip_payment_prefixes(s)

    # -----------------------------
    # 3.4 Simple obvious clean-ups
    # -----------------------------
    s = tidy_text(s)
    lower = s.lower()

    # WEBSITE style things where we prefer the brand
    if lower.startswith("www.") and " " not in lower:
        # www.sewdirect.com -> sewdirect.com
        domain = lower[4:]
        brand = domain.split(".")[0]
        s = brand

    # -----------------------------
    # Strip trailing location noise
    # -----------------------------
    LOCATION_TOKENS = {"gb", "uk"}

    # Words that are valid merchant name components, not locations
    PROTECTED_WORDS = {
        "AND",
        "MORE",
        "THE",
        "OF",
        "CO",
        "COOP",
    }

    tokens = s.split()
    lower_tokens = [t.lower() for t in tokens]

    # Only attempt aggressive stripping if country code present
    if any(t in LOCATION_TOKENS for t in lower_tokens):
        while tokens:
            last = tokens[-1]

            # Remove country codes
            if last.lower() in LOCATION_TOKENS:
                tokens.pop()
                continue

            # Remove ALL-CAPS location names, but protect brand words
            if (
                    last.isupper()
                    and len(last) > 3
                    and last not in PROTECTED_WORDS
            ):
                tokens.pop()
                continue

            break

    s = " ".join(tokens)

    # -----------------------------
    # 3.5 Dictionary-based canonical mapping
    # -----------------------------
    key = simplify_key(s)
    if key in CANONICAL_MAP:
        val = CANONICAL_MAP[key]
        if key.startswith("amzn"):
            return "Amazon AMZN"
        return val

    # Fallback: if the simplified key matches a known variant that
    # we want to collapse but we didn't explicitly list, we can add
    # small heuristics here if needed.

    # -----------------------------
    # 3.6 Final tidy and return
    # -----------------------------
    s = tidy_text(s)

    # Ensure we don’t accidentally return empty after normalisation
    if not s:
        return tidy_text(original)

    return s


# ---------------------------------------------------------------------------
# 4. Batch helper (optional)
# ---------------------------------------------------------------------------

def normalize_payees(names: list[str]) -> list[str]:
    """Normalise a list of payee strings."""
    return [normalize_payee(n) for n in names]