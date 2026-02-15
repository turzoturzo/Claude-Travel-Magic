"""Orchestrates the full pipeline: classify → extract → normalize → assemble."""

import mailbox
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from travel_itinerary.config import BATCH_SIZE, DEFAULT_TRAVELER_NAME, MBOX_PATH
from travel_itinerary.models import (
    CityVisit,
    EventType,
    FlightLeg,
    Gap,
    Location,
    TravelEvent,
)
from travel_itinerary.extract.email_parser import email_hash, extract_content
from travel_itinerary.extract.cache import ExtractionCache
from travel_itinerary.extract.llm_extractor import extract_with_fallback
from travel_itinerary.normalize.city_resolver import resolve_city
from travel_itinerary.normalize.date_parser import parse_date, parse_date_with_context
from travel_itinerary.normalize.iata import iata_to_city
from travel_itinerary.assemble.dedup import deduplicate
from travel_itinerary.assemble.timeline import build_timeline
from travel_itinerary.assemble.gap_detector import detect_gaps

# Import the existing classifier
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from travel_sorter import TravelClassifier, EmailParser as LegacyEmailParser  # noqa: E402


# Categories from travel_sorter that represent actual bookings (not marketing/admin)
_BOOKING_CATEGORIES = {
    "FLIGHT_CONFIRMATION",
    "LODGING_CONFIRMATION",
    "RAIL_CONFIRMATION",
    "BUS_FERRY_CONFIRMATION",
    "CAR_RENTAL_TRANSFER",
    "TOUR_ACTIVITY_TICKET",
}


def _classify_emails(mbox_path: str) -> Tuple[List[Dict], List[Dict]]:
    """Run the existing classifier. Returns (travel_emails, all_emails)."""
    classifier = TravelClassifier()
    mb = mailbox.mbox(mbox_path)

    travel_emails = []
    all_emails = []

    for msg in mb:
        try:
            content = extract_content(msg)
            all_emails.append(content)

            # Use the legacy classifier
            legacy_content = LegacyEmailParser.extract_content(msg)
            result = classifier.classify(legacy_content)

            if result["category"] in _BOOKING_CATEGORIES:
                content["_category"] = result["category"]
                content["_confidence"] = result["confidence"]
                travel_emails.append(content)
        except Exception:
            continue

    return travel_emails, all_emails


def _normalize_extraction(raw: Dict, email_date: str = "") -> Optional[TravelEvent]:
    """Convert raw LLM extraction dict into a normalized TravelEvent."""
    event_type_str = raw.get("event_type")
    if not event_type_str:
        return None

    try:
        event_type = EventType(event_type_str.lower())
    except ValueError:
        return None

    # Resolve locations
    origin = None
    dest = None

    origin_city = raw.get("origin_city") or ""
    origin_iata = raw.get("origin_iata") or ""
    if origin_city or origin_iata:
        resolved = resolve_city(origin_city) if origin_city else ""
        if not resolved and origin_iata:
            resolved = iata_to_city(origin_iata) or origin_iata
        origin = Location(city=resolved, raw=origin_city, iata=origin_iata)

    dest_city = raw.get("destination_city") or ""
    dest_iata = raw.get("destination_iata") or ""
    if dest_city or dest_iata:
        resolved = resolve_city(dest_city) if dest_city else ""
        if not resolved and dest_iata:
            resolved = iata_to_city(dest_iata) or dest_iata
        dest = Location(city=resolved, raw=dest_city, iata=dest_iata)

    # Parse dates
    start_date = parse_date_with_context(raw.get("start_date") or "", email_date)
    end_date = parse_date_with_context(raw.get("end_date") or "", email_date)

    # Parse legs
    legs = []
    for leg_raw in raw.get("legs") or []:
        o_city = resolve_city(leg_raw.get("origin_city") or "")
        o_iata = leg_raw.get("origin_iata") or ""
        if not o_city and o_iata:
            o_city = iata_to_city(o_iata) or o_iata
        d_city = resolve_city(leg_raw.get("destination_city") or "")
        d_iata = leg_raw.get("destination_iata") or ""
        if not d_city and d_iata:
            d_city = iata_to_city(d_iata) or d_iata

        legs.append(FlightLeg(
            origin=Location(city=o_city, iata=o_iata),
            destination=Location(city=d_city, iata=d_iata),
            departure_date=parse_date(leg_raw.get("departure_date") or ""),
            flight_number=leg_raw.get("flight_number") or "",
            carrier=leg_raw.get("carrier") or "",
        ))

    return TravelEvent(
        event_type=event_type,
        start_date=start_date,
        end_date=end_date,
        origin=origin,
        destination=dest,
        confirmation_number=raw.get("confirmation_number") or "",
        provider=raw.get("provider") or "",
        property_name=raw.get("property_name") or "",
        activity_name=raw.get("activity_name") or "",
        traveler_name=raw.get("traveler_name") or "",
        legs=legs,
        extraction_confidence=raw.get("confidence", 0.0),
        raw_extraction=raw,
    )


_FIRST_NAME_VARIANTS = {
    "matthew": {"matt", "matthew", "mat"},
}


def _normalize_first(name: str) -> set[str]:
    """Return a set of recognized variants for a first name."""
    low = name.lower()
    for canonical, variants in _FIRST_NAME_VARIANTS.items():
        if low in variants:
            return variants
    return {low}


def _is_traveler_match(event: TravelEvent, traveler_name: str) -> bool:
    """Check if event belongs to the given traveler (first + last name match)."""
    name = event.traveler_name.strip()
    if not name:
        return True  # no traveler info → assume it's ours (backward compat with cache)
    event_parts = name.lower().split()
    target_parts = traveler_name.lower().split()
    if not event_parts or not target_parts:
        return True
    # Last name must match
    if event_parts[-1] != target_parts[-1]:
        return False
    # First name must match (with variant handling for Matt/Matthew)
    event_first_variants = _normalize_first(event_parts[0])
    target_first_variants = _normalize_first(target_parts[0])
    return bool(event_first_variants & target_first_variants)


def run_pipeline(
    mbox_path: Optional[str] = None,
    skip_classify: bool = False,
    verbose: bool = True,
    traveler_name: Optional[str] = None,
) -> Tuple[List[CityVisit], List[Gap], List[TravelEvent]]:
    """Run the full pipeline end to end.

    Args:
        mbox_path: Path to the mbox file. Defaults to config.
        skip_classify: If True, extract from ALL emails (not just travel-classified).
        verbose: Print progress to stderr.
        traveler_name: Filter events to this traveler. Defaults to config DEFAULT_TRAVELER_NAME.

    Returns:
        (city_visits, gaps, deduped_events)
    """
    traveler_name = traveler_name or DEFAULT_TRAVELER_NAME
    mbox_path = mbox_path or MBOX_PATH
    cache = ExtractionCache()

    def log(msg):
        if verbose:
            print(msg, file=sys.stderr)

    # Step 1: Classify
    log(f"Loading mbox: {mbox_path}")
    travel_emails, all_emails = _classify_emails(mbox_path)
    log(f"  Total emails: {len(all_emails)}")
    log(f"  Travel-classified: {len(travel_emails)}")

    emails_to_extract = all_emails if skip_classify else travel_emails

    # Filter out cancellation emails
    cancellation_patterns = re.compile(
        r'cancel(?:led|lation|ed)|refund(?:ed)?|trip\s+cancelled|'
        r'successfully\s+cancelled|your\s+(?:trip|booking|reservation)\s+(?:has\s+been\s+)?cancel',
        re.I,
    )
    before_cancel_filter = len(emails_to_extract)
    emails_to_extract = [
        e for e in emails_to_extract
        if not cancellation_patterns.search(e.get("subject", ""))
    ]
    cancelled_count = before_cancel_filter - len(emails_to_extract)
    if cancelled_count:
        log(f"  Filtered out {cancelled_count} cancellation emails")

    # Step 2: Extract via LLM (with caching)
    events: List[TravelEvent] = []
    api_calls = 0
    cache_hits = 0

    for i, email_content in enumerate(emails_to_extract):
        if verbose and (i + 1) % BATCH_SIZE == 0:
            log(f"  Extracting {i + 1}/{len(emails_to_extract)} (API: {api_calls}, cached: {cache_hits})")

        eh = email_hash(email_content)

        # Check cache
        cached = cache.get(eh)
        if cached:
            cache_hits += 1
            raw = cached
        else:
            try:
                raw = extract_with_fallback(email_content)
                cache.put(eh, raw)
                api_calls += 1
            except Exception as e:
                log(f"  ERROR extracting: {e}")
                continue

        # Normalize
        event = _normalize_extraction(raw, email_content.get("date", ""))
        if event:
            event.source_email_id = email_content.get("message_id", "")
            event.source_subject = email_content.get("subject", "")
            events.append(event)

    log(f"  Extracted {len(events)} events (API calls: {api_calls}, cache hits: {cache_hits})")

    # Step 3: Filter by traveler name
    before_filter = len(events)
    events = [e for e in events if _is_traveler_match(e, traveler_name)]
    filtered_count = before_filter - len(events)
    if filtered_count:
        log(f"  Filtered out {filtered_count} events for other travelers (keeping: {traveler_name})")

    # Step 4: Deduplicate
    deduped = deduplicate(events)
    log(f"  After dedup: {len(deduped)} unique events")

    # Step 5: Build timeline
    visits = build_timeline(deduped)
    log(f"  Assembled {len(visits)} city visits")

    # Step 6: Detect gaps
    visits, gaps = detect_gaps(visits)
    log(f"  Detected {len(gaps)} gaps (>{__import__('travel_itinerary.config', fromlist=['GAP_THRESHOLD_DAYS']).GAP_THRESHOLD_DAYS} days)")

    return visits, gaps, deduped
