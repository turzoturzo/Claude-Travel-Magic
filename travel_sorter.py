#!/usr/bin/env python3
"""
Travel Sorter: Local, Offline MECE Classification for Travel Emails
Supports English, Spanish, French, German, Italian, and Portuguese.
"""

import sys
import os
import re
import csv
import json
import mailbox
import argparse
from datetime import datetime
from email.header import decode_header
from typing import List, Dict, Any, Tuple, Optional
from bs4 import BeautifulSoup

# --- CONFIGURATION & TAXONOMY ---

CATEGORIES = [
    "FLIGHT_CONFIRMATION",
    "LODGING_CONFIRMATION",
    "RAIL_CONFIRMATION",
    "BUS_FERRY_CONFIRMATION",
    "CAR_RENTAL_TRANSFER",
    "TOUR_ACTIVITY_TICKET",
    "TRAVEL_DOCUMENT_ADMIN",
    "TRAVEL_CHANGE_DISRUPTION",
    "TRAVEL_MARKETING_NEWSLETTER",
    "NON_TRAVEL"
]

CATEGORY_PRIORITY = {cat: i for i, cat in enumerate(CATEGORIES)}

# --- MULTI-LANGUAGE PATTERNS ---

# High-signal booking identifiers (PNR, Confirmation numbers)
BOOKING_REF_PATTERNS = [
    r'booking\s+(?:ref|reference|code|number)',
    r'confirmation\s+(?:number|id|code|ref)',
    r'reservation\s+(?:number|id|code|ref)',
    r'record\s+locator',
    r'pnr\b',
    r'e-ticket',
    r'itinerary\s+number',
    # ES
    r'número\s+de\s+reserva',
    r'código\s+de\s+reserva',
    r'nº\s+de\s+reserva',
    r'localizador\b',
    # FR
    r'numéro\s+de\s+réservation',
    r'code\s+de\s+réservation',
    r'dossier\s+numéro',
    # DE
    r'buchungsnummer',
    r'reservierungsnummer',
    r'buchungscode',
    # IT
    r'numero\s+di\s+prenotazione',
    r'codice\s+prenotazione',
    # PT
    r'número\s+da\s+reserva',
    r'código\s+da\s+reserva'
]

# Category-specific signals
SIGNALS = {
    "FLIGHT_CONFIRMATION": {
        "high": [
            r'\b(?:boarding\s+pass|gate|terminal|seat)\b',
            r'\b(?:vuelo|vol|voo|flug|volo)\b\s*[A-Z]{2}\s?\d{2,4}',  # Flight number patterns
            r'\b(?:iata|e-ticket|e-ticket|itinerary\s+receipt)\b',
            r'\b[A-Z]{3}\s*[-–→>]\s*[A-Z]{3}\b'  # IATA pairs like BCN-VIE
        ],
        "med": [
            r'flight', r'airline', r'airport', r'airline', r'airways', 
            r'vuelo', r'vol', r'volo', r'voo', r'flug'
        ]
    },
    "LODGING_CONFIRMATION": {
        "high": [
            r'check-in\s+date', r'check-out\s+date', r'hotel\s+reservation',
            r'\bnights\b', r'\bnoches\b', r'\bnuits\b', r'\bnächte\b', r'\bnotti\b', r'\bnoites\b',
            r'reservation\s+confirmed'
        ],
        "med": [
            r'hotel', r'resort', r'apartment', r'airbnb', r'hostel', r'lodging', r'stay',
            r'colazione', r'breakfast'
        ]
    },
    "RAIL_CONFIRMATION": {
        "high": [
            r'\bcarriage\b', r'\bcoach\b', r'\bplatform\b', r'\btrack\s+\d+\b', r'seat\s+reservation',
            r'amtrak', r'eurostar', r'trenitalia', r'sncf', r'renfe', r'db\s+bahn', r'öbb', r'sbb', r'thalys'
        ],
        "med": [
            r'train', r'rail', r'station', r'tren', r'gare', r'hauptbahnhof', r'sants', r'stazione', r'estação'
        ]
    },
    "BUS_FERRY_CONFIRMATION": {
        "high": [
            r'bus\s+station', r'ferry', r'boat', r'boarding\s+gate', r'coach\s+station',
            r'flixbus', r'greyhound', r'balearia', r'fred\s+olsen', r'moby'
        ],
        "med": [
            r'autobus', r'ferry', r'barco', r'schiff', r'traghetto'
        ]
    },
    "CAR_RENTAL_TRANSFER": {
        "high": [
            r'pick-up', r'drop-off', r'rental\s+agreement', r'rental\s+car', r'hertz', r'avis', r'sixt', r'europcar', r'enterprise', r'budget'
        ],
        "med": [
            r'car\s+rental', r'alquiler\s+de\s+coches', r'location\s+de\s+voitures', r'autovermietung', r'noleggio\s+auto', r'aluguel\s+de\s+carros'
        ]
    },
    "TOUR_ACTIVITY_TICKET": {
        "high": [
            r'tour\s+booking', r'ticket\s+confirmation', r'admittance', r'voucher\s+code', r'meeting\s+point', r'time\s+slot',
            r'viator', r'getyourguide', r'klook', r'tiqets'
        ],
        "med": [
            r'activity', r'tour', r'excursion', r'attraction', r'experience', r'museum', r'concerto', r'visita'
        ]
    },
    "TRAVEL_DOCUMENT_ADMIN": {
        "high": [
            r'visa\b', r'\bETA\b', r'electronic\s+travel\s+authorization', r'insurance\s+policy', r'parking\s+reservation', 
            r'airport\s+parking', r'lounge\s+access',
            r'health\s+declaration', r'passenger\s+locator\s+form'
        ],
        "med": [
            r'travel\s+document', r'travel\s+policy', r'insurance', r'parking'
        ]
    },
    "TRAVEL_CHANGE_DISRUPTION": {
        "high": [
            r'schedule\s+change', r'cancellation\s+notice', r'cancelled', r'rebooked', r'flight\s+delay',
            r'refund\s+confirmation', r'modified\s+booking'
        ],
        "med": [
            r'changed', r'cancelado', r'annulé', r'storniert', r'cancellato', r'delay', r'update'
        ]
    },
    "TRAVEL_MARKETING_NEWSLETTER": {
        "high": [
            r'special\s+offer', r'vacation\s+deals', r'low\s+fares', r'book\s+now\s+and\s+save', r'where\s+to\s+go\s+next',
            r'exclusive\s+deals', r'bonus\s+points', r'miles\s+offer'
        ],
        "med": [
            r'newsletter', r'marketing', r'promotion', r'sale', r'inspiration', r'travel\s+guide'
        ]
    }
}

# Negative signals - common false positives (e-commerce, generic receipts, marketing)
NEGATIVE_SIGNALS = [
    r'shipped\b', r'tracking\s+number', r'order\s+shipped',
    r'enviado\b', r'expédié\b', r'versandt\b',
    r'password\s+reset', r'verify\s+email', r'subscription\s+confirmed',
    r'receipt\s+for\s+your\s+payment\s+to\s+spotify',
    r'amazon\s+order', r'apple\s+receipt',
    r'paperless\s+enrollment', r'credit\s+journey', r'point\s+transfer',
    r'special\s+offer', r'exclusive\s+deal', r'win\s+a\s+trip', r'giveaway',
    r'limited\s+time\s+offer', r'save\s+up\s+to', r'book\s+now\b',
    r'newsletter', r'promotional', r'opt-out', r'unsubscribe'
]

# Admin and Support signals (High signal for NOT being a travel confirmation)
ADMIN_AUTH_SIGNALS = [
    r'secure\s+sign\s+in\s+code', r'your\s+otp', r'verification\s+code',
    r'support\s+ticket', r'customer\s+support', r'help\s+desk', r'zendesk',
    r'password\s+change', r'account\s+access', r'update\s+my\s+email',
    r'credit\s+limit\s+increase', r'application\s+received', r'insufficient\s+funds'
]

# --- HELPER CLASSES ---

class EmailParser:
    @staticmethod
    def decode_str(s: str) -> str:
        if not s:
            return ""
        decoded = decode_header(s)
        parts = []
        for part, encoding in decoded:
            if isinstance(part, bytes):
                try:
                    parts.append(part.decode(encoding or "utf-8", errors="ignore"))
                except:
                    parts.append(part.decode("utf-8", errors="ignore"))
            else:
                parts.append(str(part))
        return "".join(parts)

    @staticmethod
    def get_text_from_html(html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator=" ", strip=True)

    @staticmethod
    def extract_content(msg: mailbox.Message) -> Dict[str, Any]:
        subject = EmailParser.decode_str(msg.get("subject", ""))
        from_header = EmailParser.decode_str(msg.get("from", ""))
        to_header = EmailParser.decode_str(msg.get("to", ""))
        date_header = msg.get("date", "")
        message_id = msg.get("Message-ID", "")

        body_text = ""
        html_content = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                filename = part.get_filename()

                if filename:
                    attachments.append({"name": filename, "type": content_type})

                if "attachment" in disposition:
                    continue

                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text += payload.decode(errors="ignore")
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        html_content += payload.decode(errors="ignore")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                if msg.get_content_type() == "text/html":
                    html_content = payload.decode(errors="ignore")
                else:
                    body_text = payload.decode(errors="ignore")

        # If we only have HTML, convert to text
        if html_content and not body_text:
            body_text = EmailParser.get_text_from_html(html_content)

        return {
            "message_id": message_id,
            "subject": subject,
            "from": from_header,
            "to": to_header,
            "date": date_header,
            "body": body_text,
            "attachments": attachments
        }

class TravelClassifier:
    def __init__(self):
        self.booking_ref_regex = [re.compile(p, re.I) for p in BOOKING_REF_PATTERNS]
        self.negative_regex = [re.compile(p, re.I) for p in NEGATIVE_SIGNALS]
        self.admin_auth_regex = [re.compile(p, re.I) for p in ADMIN_AUTH_SIGNALS]
        
        self.category_regex = {}
        for cat, patterns in SIGNALS.items():
            self.category_regex[cat] = {
                "high": [re.compile(p, re.I) for p in patterns["high"]],
                "med": [re.compile(p, re.I) for p in patterns["med"]]
            }

    def classify(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        full_text = f"{email_data['subject']} {email_data['body']}"
        cat_scores = {}
        matched_features = []
        
        matches = []
        
        # 1. PNR / Booking Ref (High signal)
        for reg in self.booking_ref_regex:
            match = reg.search(full_text)
            if match:
                matched_features.append("BOOKING_REF")
                matches.append(match.group(0))
                break

        # 2. IATA Pairs (BCN-VIE, etc.)
        iata_pair_reg = re.compile(r'\b([A-Z]{3})\s*[-–→>]\s*([A-Z]{3})\b')
        iata_pairs = iata_pair_reg.findall(full_text)
        if iata_pairs:
            matched_features.append("IATA_PAIR")
            for pair in iata_pairs:
                matches.append(f"{pair[0]}-{pair[1]}")

        # 3. Flight Numbers ([A-Z]{2}\s?\d{2,4})
        flight_num_reg = re.compile(r'\b([A-Z]{2})\s?(\d{2,4})\b')
        flight_nums = flight_num_reg.findall(full_text)
        if flight_nums:
            matched_features.append("FLIGHT_NUM")
            for fn in flight_nums:
                matches.append(f"{fn[0]}{fn[1]}")

        # 4. Dates & Check-in/out patterns
        date_patterns = [
            r'check-in', r'check-out', r'checkin', r'checkout',
            r'fecha\s+de\s+entrada', r'fecha\s+de\s+salida',
            r'date\s+d\'arrivée', r'date\s+de\s+départ',
            r'anreise', r'abreise'
        ]
        for dp in date_patterns:
            if re.search(dp, full_text, re.I):
                matched_features.append("CHECKIN_OUT")
                break

        # Check Admin/Auth signals (High penalty)
        has_admin = False
        for reg in self.admin_auth_regex:
            if reg.search(full_text):
                has_admin = True
                matched_features.append(f"ADMIN_{reg.pattern}")
                break

        # Check negative/marketing signals
        has_negative = False
        for reg in self.negative_regex:
            if reg.search(full_text):
                has_negative = True
                matched_features.append(f"NEG_{reg.pattern}")
                break

        # Marketing Subject detection (Look for ?, !, or "Win", "Limited")
        subject = email_data['subject']
        if re.search(r'[?!]{2,}', subject) or re.search(r'\b(win|bonus|limited|last\s+chance|sale)\b', subject, re.I):
            matched_features.append("MKTG_SUBJECT")

        # Scoring each category
        for cat in SIGNALS.keys():
            score = 0.0
            cat_matches = []
            
            # Subject matching booster (0.2 extra for high signal in subject)
            subject_lower = email_data['subject'].lower()
            subject_hit = False

            # High signals (0.4 each)
            for reg in self.category_regex[cat]["high"]:
                if reg.search(full_text):
                    score += 0.4
                    cat_matches.append(reg.pattern)
                    if reg.search(subject_lower):
                        score += 0.2
                        subject_hit = True

            # Medium signals (0.15 each)
            for reg in self.category_regex[cat]["med"]:
                if reg.search(full_text):
                    score += 0.15
                    cat_matches.append(reg.pattern)
                    if not subject_hit and reg.search(subject_lower):
                        score += 0.1

            # Contextual boosters
            if score > 0 and "BOOKING_REF" in matched_features:
                score += 0.25
            
            if cat == "FLIGHT_CONFIRMATION" and ("IATA_PAIR" in matched_features or "FLIGHT_NUM" in matched_features):
                score += 0.35
            
            if cat == "LODGING_CONFIRMATION" and "CHECKIN_OUT" in matched_features:
                score += 0.35

            cat_scores[cat] = min(1.0, score)
            if score > 0:
                matched_features.extend([f"{cat}:{m}" for m in cat_matches])

        # Apply penalties
        if has_admin:
            for cat in cat_scores:
                if cat not in ["NON_TRAVEL"]:
                    cat_scores[cat] -= 0.8 # Severe penalty for account admin
        elif has_negative:
            for cat in cat_scores:
                if cat not in ["TRAVEL_MARKETING_NEWSLETTER", "NON_TRAVEL"]:
                    cat_scores[cat] -= 0.5
        
        if "MKTG_SUBJECT" in matched_features:
            for cat in cat_scores:
                if cat not in ["TRAVEL_MARKETING_NEWSLETTER", "NON_TRAVEL"]:
                    cat_scores[cat] -= 0.3

        # Deciding the winner (MECE)
        best_cat = "NON_TRAVEL"
        max_score = 0.0

        # Journey Data Check: For a travel confirmation, we ideally want high-signal journey data
        has_journey_data = any(feat in matched_features for feat in ["BOOKING_REF", "IATA_PAIR", "FLIGHT_NUM", "CHECKIN_OUT"])

        # Filter categories that pass threshold
        candidates = [(cat, score) for cat, score in cat_scores.items() if score >= 0.4]
        
        if candidates:
            # Sort by score descending, then by priority ascending
            candidates.sort(key=lambda x: (-x[1], CATEGORY_PRIORITY[x[0]]))
            best_cat = candidates[0][0]
            max_score = candidates[0][1]

        # Final sanity check: If it's a travel category but has NO journey data and NO high patterns, demote
        if best_cat not in ["NON_TRAVEL", "TRAVEL_MARKETING_NEWSLETTER"]:
            if not has_journey_data:
                # If it's just based on a few med keywords, it's likely noise
                if max_score < 0.6:
                    best_cat = "NON_TRAVEL"
                    max_score = 0.2

        # Final score set for NON_TRAVEL
        if best_cat == "NON_TRAVEL" and max_score < 0.4:
            max_score = max(0.1, max_score)

        is_travel = best_cat not in ["NON_TRAVEL", "TRAVEL_MARKETING_NEWSLETTER"]

        return {
            "category": best_cat,
            "is_travel": is_travel,
            "confidence": round(max_score, 2),
            "reasons": "; ".join(list(set(matched_features[:15]))),
            "top_tokens": ", ".join(list(set(matches[:10]))),
            "all_scores": cat_scores
        }

# --- MAIN RUNNER ---

def main():
    parser = argparse.ArgumentParser(description="Multi-language Travel Email Sorter")
    parser.add_argument("--mbox", required=True, help="Path to input .mbox file or directory of .eml files")
    parser.add_argument("--out", required=True, help="Output filename (CSV)")
    parser.add_argument("--debug", type=int, default=0, help="Print debug info for N messages")
    args = parser.parse_args()

    classifier = TravelClassifier()
    records = []
    
    # Process input
    iter_messages = []
    if os.path.isdir(args.mbox):
        print(f"Processing directory of .eml files: {args.mbox}...")
        for root, _, files in os.walk(args.mbox):
            for file in files:
                if file.lower().endswith('.eml'):
                    path = os.path.join(root, file)
                    with open(path, 'rb') as f:
                        msg = mailbox.mboxMessage(f.read())
                        iter_messages.append(msg)
    else:
        try:
            iter_messages = mailbox.mbox(args.mbox)
            print(f"Processing mailbox: {args.mbox}...")
        except Exception as e:
            print(f"Error opening mbox: {e}")
            sys.exit(1)

    count = 0
    cat_counts = {cat: 0 for cat in CATEGORIES}
    conf_dist = {"high": 0, "likely": 0, "possible": 0, "unlikely": 0}

    with open(args.out, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            "message_id", "date", "from", "subject", "category", 
            "is_travel", "confidence", "reasons", "top_tokens", "attachment_types"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        jsonl_path = args.out.replace(".csv", ".jsonl")
        with open(jsonl_path, 'w', encoding='utf-8') as jsonl_file:
            for i, msg in enumerate(iter_messages):
                try:
                    email_data = EmailParser.extract_content(msg)
                    result = classifier.classify(email_data)
                    
                    # Attachment types
                    att_types = ",".join([a["type"] for a in email_data["attachments"]])

                    # Update stats
                    cat_counts[result["category"]] += 1
                    conf = result["confidence"]
                    if conf >= 0.9: conf_dist["high"] += 1
                    elif conf >= 0.7: conf_dist["likely"] += 1
                    elif conf >= 0.4: conf_dist["possible"] += 1
                    else: conf_dist["unlikely"] += 1

                    row = {
                        "message_id": email_data["message_id"],
                        "date": email_data["date"],
                        "from": email_data["from"],
                        "subject": email_data["subject"],
                        "category": result["category"],
                        "is_travel": result["is_travel"],
                        "confidence": conf,
                        "reasons": result["reasons"],
                        "top_tokens": result["top_tokens"],
                        "attachment_types": att_types
                    }
                    
                    writer.writerow(row)
                    jsonl_file.write(json.dumps(row) + "\n")
                    
                    if args.debug > 0 and i < args.debug:
                        print(f"\n--- DEBUG MESSAGE {i} ---")
                        print(f"Subject: {email_data['subject']}")
                        print(f"From: {email_data['from']}")
                        print(f"Category: {result['category']} (Conf: {conf})")
                        print(f"Reasons: {result['reasons']}")
                        print(f"All Scores: {json.dumps(result['all_scores'], indent=2)}")

                    count += 1
                    if count % 100 == 0:
                        print(f"  Processed {count} messages...")

                except Exception as e:
                    print(f"Error processing message {i}: {e}")

    # Summary Output
    summary_path = args.out.replace(".csv", ".summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f"Travel Sorter Summary\n")
        f.write(f"=====================\n")
        f.write(f"Total processed: {count}\n\n")
        f.write(f"Categories:\n")
        for cat in CATEGORIES:
            pct = (cat_counts[cat] / count * 100) if count > 0 else 0
            f.write(f"  {cat:30}: {cat_counts[cat]:5} ({pct:5.1f}%)\n")
        
        f.write(f"\nConfidence Distribution:\n")
        f.write(f"  High (0.9-1.0):      {conf_dist['high']}\n")
        f.write(f"  Likely (0.7-0.9):    {conf_dist['likely']}\n")
        f.write(f"  Possible (0.4-0.7):  {conf_dist['possible']}\n")
        f.write(f"  Unlikely (0.0-0.4):  {conf_dist['unlikely']}\n")

    print(f"\nDone! Processed {count} messages.")
    print(f"Results saved to:")
    print(f"  - {args.out}")
    print(f"  - {jsonl_path}")
    print(f"  - {summary_path}")

if __name__ == "__main__":
    main()
