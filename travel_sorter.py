#!/usr/bin/env python3
"""
Travel Sorter V2: The Extraction Enabler
- Based on v2b 2026.7
- ADDS: JSONL export of full email bodies for matched confirmations.
- Logic priority: Hotels match Lodging even if Trusted catch-all exists.
- Output:
    1. CSV with Confirmed Travel (Grouped by ID).
    2. JSONL with full bodies for those confirmed items.
"""

import sys
import os
import re
import csv
import json
import mailbox
import argparse
from email.header import decode_header
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

# --- CONFIGURATION ---

CATEGORIES = [
    "FLIGHT_CONFIRMATION", "LODGING_CONFIRMATION", "RAIL_CONFIRMATION",
    "BUS_FERRY_CONFIRMATION", "CAR_RENTAL_TRANSFER", "TOUR_ACTIVITY_TICKET",
    "TRAVEL_DOCUMENT_ADMIN", "TRAVEL_CHANGE_DISRUPTION",
    "TRAVEL_MARKETING_NEWSLETTER", "NON_TRAVEL"
]

TRUSTED_TRAVEL_DOMAINS = {
    "united.com", "delta.com", "aa.com", "southwest.com", "jetblue.com", "alaskaair.com",
    "aircanada.ca", "britishairways.com", "lufthansa.com", "airfrance.com", "klm.com",
    "ryanair.com", "easyjet.com", "emirates.com", "qatarairways.com", "turkishairlines.com",
    "vueling.com", "wizzair.com", "norwegian.com", "iberia.com", "tap.pt", "flytap.com",
    "booking.com", "expedia.com", "hotels.com", "airbnb.com", "agoda.com", "trip.com",
    "priceline.com", "kayak.com", "hoteltonight.com", "marriott.com", "hilton.com", "hyatt.com",
    "ihg.com", "accor.com", "h10hotels.com", "trainline.com", "eurostar.com", "renfe.com",
    "amtrak.com", "hertz.com", "avis.com", "enterprise.com", "sixt.com", "uber.com", "lyft.com",
    "sprucetoninn.com"
}

BLOCK_DOMAINS = {
    "linkedin.com", "substack.com", "beehiiv.com", "ccsend.com", "democrats.org",
    "amazon.com", "amazon.es", "amazon.co.uk", "soundcloud.com", "angellist.com",
    "proton.me", "hometalk.com", "ostrichpillow.com", "kickstarter.com", "shopifyemail.com",
    "wonderbly.com", "abchome.com", "bengsforsouthdakota.com", "debhaaland.com",
    "kathyhochul.com", "womensmarch.com", "statedemocrats.com", "colemanrg.com",
    "slack.com", "omnihotels.com", "temu.com", "flightschedulepro.com", "eaglecreek.com",
    "waterdropfilter.eu", "guitarcenter.com", "robinhood.com", "americanexpress.com",
    "teamtailor-mail.com", "wcs.org", "eat24.com"
}

BLOCK_SUBJECTS_RE = [
    r'Rewards', r'Deals', r'Win\s+tickets', r'Reward\s+nights', r'Blackout\s+dates',
    r'Choose\s+the\s+place', r'Flip\s+flops', r'Turn\s+your\s+travel\s+plans', r'Travel\s+recap',
    r'Milestones', r'Future\s+Flight\s+Credit', r'Honors\s+is\s+coming', r'Statement\s+period',
    r'Processing\s+your\s+order', r'Shipment\s+is\s+on\s+its\s+way', r'Order\s+receipt',
    r'NEW\s+routes', r'Seats\s+on\s+Sale', r'fares\s+before\s+they\'re\s+gone', r'adventure\s+starts',
    r'Christmas', r'wishes\s+come\s+true', r'Black\s+Days', r'Cyber\s+Monday', r'Last\s+call',
    r'stop\s+reminding\s+you', r'Forgot\s+to\s+book', r'Monthly\s+statement', r'weekly\s+account\s+snapshot',
    r'Individual\s+account\s+statement', r'Unlocked\s+Free\s+Express\s+Delivery', r'Holiday\s+Gift\s+Guide'
]

PNR_BLOCKLIST = {
    "FRIDAY", "MONDAY", "BUDGET", "SECURE", "STARTS", "MOMENT", "PLACES", "CHANGE",
    "POSSIBLE", "LISTEN", "PICKED", "LOOKED", "UPDATE", "SYSTEM", "TRAVEL", "SAMPLE",
    "SUNDAY", "TUESDAY", "FINISH", "BOOKING", "FUTURE", "MESSAGE", "ABOUT", "THROUGH",
    "COUNTRY", "LAWSUIT", "REQUIRE", "LIMITED", "OCTOBER", "BEYOND", "MATTHEW", "BAGGAGE",
    "CONNECT", "PASSED", "CLIENT", "NOTICE", "REPORT", "CONFIRMED", "DETAILED", "DETAILS",
    "RESERVATIONS", "FLIGHTS", "BOOKINGS", "TICKETS", "BARCELONA", "PASSENGER", "UPGRADE",
    "AVAILABLE", "ADVENTURE", "HOLIDAY", "WAITING", "SQUEEZE", "ORLANDO", "LIBERIA",
    "ANNUAL", "GOWILD", "HOTELS", "PLAINS", "WINTER", "FLIGHT", "TRIP", "ENJOY", "CREDIT",
    "DOCTYPE", "HTML", "PUBLIC"
}

BOOKING_KEYWORDS = [
    r'\bbooking\s*(?:ref|reference|code|number|id|#)\b',
    r'\bconfirmation\s*(?:number|id|code|ref|conf|#)\b',
    r'\breservation\s*(?:number|id|code|ref|conf|#)\b',
    r'\bpnr\b', r'\be-ticket\b', r'\bitinerary\b', r'\breserva\b', r'\blocalizador\b',
    r'\bRes\s*Id\b'
]

STRUCTURAL = {
    "FLIGHT": { "IATA_PAIR": r'\b[A-Z]{3}\s*[-–→>]\s*[A-Z]{3}\b' },
    "LODGING": { "DATE_PAIR": r'\bcheck-in\b.{1,200}\bcheck-out\b' }
}

AIRLINES = ["United", "American", "Delta", "Southwest", "Air Canada", "Alaska", "Spirit", "JetBlue", "Ryanair", "Lufthansa", "British Airways", "Iberia", "Air France", "KLM", "EasyJet", "Turkish Airlines", "Wizz Air", "Emirates", "Qatar Airways", "Vueling", "Norwegian", "TAP Air"]
HOTELS = ["Marriott", "Ritz-Carlton", "St. Regis", "Hilton", "DoubleTree", "IHG", "Holiday Inn", "Hyatt", "Wyndham", "Accor", "Aloft", "Kimpton", "Omni", "Arlo", "H10", "Spruceton Inn"]
PLATFORMS = ["Booking.com", "Expedia", "Hotels.com", "Airbnb", "Agoda", "Trip.com", "Priceline", "Kayak", "HotelTonight", "Trainline", "Eurostar"]

def make_reg(patterns): return [re.compile(p, re.I) for p in patterns]
def make_brand_reg(brands):
    joined = "|".join([re.escape(b) for b in sorted(brands, key=len, reverse=True)])
    return re.compile(fr"\b(?:{joined})\b", re.I)

class EmailParser:
    @staticmethod
    def decode_str(s: Any) -> str:
        if s is None: return ""
        s_str = str(s)
        try:
            decoded = decode_header(s_str); parts = []
            for part, encoding in decoded:
                if isinstance(part, bytes):
                    try: parts.append(part.decode(encoding or "utf-8", errors="ignore"))
                    except: parts.append(part.decode("iso-8859-1", errors="ignore"))
                else: parts.append(str(part))
            return " ".join("".join(parts).split())
        except: return s_str

    @staticmethod
    def extract_content(msg: mailbox.Message) -> Dict[str, Any]:
        subject = EmailParser.decode_str(msg.get("subject", ""))
        from_header = EmailParser.decode_str(msg.get("from", ""))
        date_header = EmailParser.decode_str(msg.get("date", ""))

        final_date = date_header
        try:
            dt = parsedate_to_datetime(date_header)
            if dt:
                 final_date = dt.isoformat()
        except:
             pass

        body_text = ""; html_content = ""
        if msg.is_multipart():
            for part, submsg in enumerate(msg.walk()):
                # multipart/alternative usually has text/plain and text/html
                if submsg.get_content_type() == "text/plain":
                    p = submsg.get_payload(decode=True)
                    if p: body_text += p.decode(errors="ignore")
                elif submsg.get_content_type() == "text/html":
                    p = submsg.get_payload(decode=True)
                    if p: html_content += p.decode(errors="ignore")
        else:
            p = msg.get_payload(decode=True)
            if p:
                if msg.get_content_type() == "text/html": html_content = p.decode(errors="ignore")
                else: body_text = p.decode(errors="ignore")

        # Fallback: If body_text is suspiciously short and we have HTML, extract text from HTML
        if html_content and len(body_text.strip()) < 20:
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                # Remove script and style elements
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()

                # Get text with better spacing
                html_text = soup.get_text(separator=" ", strip=True)
                if len(html_text) > len(body_text):
                    body_text = html_text
            except: pass

        return {"subject": subject, "from": from_header, "date": final_date, "body": body_text, "html": html_content}

class TravelClassifier:
    def __init__(self):
        self.struct_flight = {k: re.compile(v, re.I) for k, v in STRUCTURAL["FLIGHT"].items()}
        self.struct_lodging = {k: re.compile(v, re.I) for k, v in STRUCTURAL["LODGING"].items()}
        self.block_subjects = make_reg(BLOCK_SUBJECTS_RE)
        self.brands = {k: make_brand_reg(v) for k, v in {"AIRLINE": AIRLINES, "HOTEL": HOTELS, "PLATFORM": PLATFORMS}.items()}
        self.kw_regs = make_reg(BOOKING_KEYWORDS)

    def validate_conf(self, conf: str) -> bool:
        if not conf: return False
        if conf.islower() and not conf.isdigit(): return False
        if conf.isalpha() and not conf.isupper(): return False
        if conf.upper() in PNR_BLOCKLIST: return False
        if len(conf) < 5 or len(conf) > 15: return False
        if conf.isdigit() and (conf.startswith('0') or conf.startswith('44') or conf.startswith('34')): return False
        return True

    def extract_conf_number(self, text: str) -> Optional[str]:
        for kw_pat in self.kw_regs:
            for m_kw in kw_pat.finditer(text):
                window = text[m_kw.end():m_kw.end()+30]
                possible = re.findall(r'\b([A-Z0-9]{5,15})\b', window)
                for p in possible:
                    if self.validate_conf(p): return p
        return None

    def classify(self, data: Dict[str, Any]) -> Dict[str, Any]:
        text = f"{data['subject']} {data['body']}"
        subj_norm = " ".join(data['subject'].lower().split())
        sender = data['from'].lower()
        domain = ""
        m = re.search(r'@([\w.-]+)', sender)
        if m: domain = m.group(1).lower()

        if any(d in domain for d in BLOCK_DOMAINS) or any(r.search(subj_norm) for r in self.block_subjects):
            return {"category": "NON_TRAVEL", "is_travel": False, "confidence": 0.1, "confirmation": ""}

        conf_no = self.extract_conf_number(text[:10000])
        if not conf_no: return {"category": "NON_TRAVEL", "is_travel": False, "confidence": 0.1, "confirmation": ""}

        is_trusted = any(d in domain for d in TRUSTED_TRAVEL_DOMAINS)
        has_iata = self.struct_flight["IATA_PAIR"].search(text[:5000])
        has_dates = self.struct_lodging["DATE_PAIR"].search(text.lower())

        is_airline = self.brands["AIRLINE"].search(sender + " " + subj_norm)
        is_hotel = self.brands["HOTEL"].search(sender + " " + subj_norm)
        is_platform = self.brands["PLATFORM"].search(sender + " " + subj_norm)

        # Decision Logic Priority
        if has_dates or is_hotel or is_platform:
            return {"category": "LODGING_CONFIRMATION", "is_travel": True, "confidence": 1.0, "confirmation": conf_no}
        if has_iata or is_airline:
            return {"category": "FLIGHT_CONFIRMATION", "is_travel": True, "confidence": 1.0, "confirmation": conf_no}
        if is_trusted:
            return {"category": "FLIGHT_CONFIRMATION", "is_travel": True, "confidence": 0.9, "confirmation": conf_no}

        return {"category": "NON_TRAVEL", "is_travel": False, "confidence": 0.1, "confirmation": ""}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mbox", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--stop-after", type=int, default=None, help="Stop after finding N confirmed emails")
    args = parser.parse_args(); c = TravelClassifier(); ms = []

    # 1. Loading
    print("Loading messages...")
    if os.path.isdir(args.mbox):
        for r, _, fs in os.walk(args.mbox):
            for f in fs:
                if f.endswith('.eml'):
                    with open(os.path.join(r,f), 'rb') as fp: ms.append(mailbox.mboxMessage(fp.read()))
    else: ms = mailbox.mbox(args.mbox)

    processed = 0
    confirmed_entries = [] # List of Dicts

    # 2. Processing
    print(f"Processing messages...")
    for i, m in enumerate(ms):
        if args.limit and i >= args.limit: break
        try:
            d = EmailParser.extract_content(m); r = c.classify(d)
            # Filter Strategy: Only KEEP positive confirmation with a code
            if r["is_travel"] and r["confirmation"]:
                 entry = {
                     "date": d["date"],
                     "from": d["from"],
                     "subject": d["subject"],
                     "category": r["category"],
                     "confidence": r["confidence"],
                     "confirmation": r["confirmation"],
                     # Carry payload for next step
                     "body": d["body"],
                     "html": d.get("html", ""),
                     "sender_domain": d["from"] # Simplified, re-extract in next step if needed
                 }
                 print(f"  -> Found travel email: {d['subject'][:50]}...")
                 confirmed_entries.append(entry)
                 if args.stop_after and len(confirmed_entries) >= args.stop_after:
                     print(f"Reached limit of {args.stop_after} confirmed items. Stopping.")
                     break

            processed += 1
            if processed % 5000 == 0: print(f"Scanned {processed}...")
        except: pass

    print(f"Extraction complete. Found {len(confirmed_entries)} confirmed items. Grouping and sorting...")

    # 3. Grouping & Sorting
    # Group by confirmation code
    grouped = {}
    for entry in confirmed_entries:
        code = entry["confirmation"]
        if code not in grouped: grouped[code] = []
        grouped[code].append(entry)

    # Prepare list for sorting groups: (min_date, list_of_entries)
    sorted_groups = []
    for code, group in grouped.items():
        # Sort within the group by date
        # Note: ISO formatted dates sort correctly as strings
        group.sort(key=lambda x: x["date"] or "")

        # Determine group start date (first email in chain)
        start_date = group[0]["date"] or ""
        sorted_groups.append((start_date, group))

    # Sort groups by their start date
    sorted_groups.sort(key=lambda x: x[0])

    # Flatten for CSV output
    final_output = []
    for _, group in sorted_groups:
        final_output.extend(group)

    # 4. Writing CSV
    print(f"Writing {len(final_output)} sorted entries to {args.out}...")
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        # Exclude body/html from CSV to keep it clean, but include regular fields
        w = csv.DictWriter(f, fieldnames=["date", "from", "subject", "category", "confidence", "confirmation"])
        w.writeheader()
        for row in final_output:
            # Create a shallow copy for CSV writing to exclude body/html
            csv_row = {k:v for k,v in row.items() if k in ["date", "from", "subject", "category", "confidence", "confirmation"]}
            w.writerow(csv_row)

    # 5. Writing JSONL
    jsonl_out = args.out.rsplit('.', 1)[0] + '.jsonl'
    print(f"Writing {len(final_output)} detailed entries to {jsonl_out}...")
    with open(jsonl_out, 'w', encoding='utf-8') as f:
        for row in final_output:
            json.dump(row, f)
            f.write('\n')

    print("Done.")

if __name__ == "__main__": main()
