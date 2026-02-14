"""Deduplicate travel events — same booking generates 5-15 emails."""

from collections import defaultdict
from datetime import timedelta
from typing import List, Optional

from travel_itinerary.config import DEDUP_DATE_WINDOW_DAYS
from travel_itinerary.models import TravelEvent


def _richness_score(event: TravelEvent) -> int:
    """Count non-null useful fields — higher = more complete extraction."""
    score = 0
    if event.start_date:
        score += 2
    if event.end_date:
        score += 2
    if event.origin and event.origin.city:
        score += 1
    if event.destination and event.destination.city:
        score += 1
    if event.confirmation_number:
        score += 1
    if event.provider:
        score += 1
    if event.property_name:
        score += 1
    if event.activity_name:
        score += 1
    if event.legs:
        score += len(event.legs)
    return score


def _merge_pair(primary: TravelEvent, secondary: TravelEvent) -> TravelEvent:
    """Merge secondary's non-null fields into primary."""
    if not primary.start_date and secondary.start_date:
        primary.start_date = secondary.start_date
    if not primary.end_date and secondary.end_date:
        primary.end_date = secondary.end_date
    if not primary.origin and secondary.origin:
        primary.origin = secondary.origin
    elif primary.origin and secondary.origin and not primary.origin.city and secondary.origin.city:
        primary.origin = secondary.origin
    if not primary.destination and secondary.destination:
        primary.destination = secondary.destination
    elif primary.destination and secondary.destination and not primary.destination.city and secondary.destination.city:
        primary.destination = secondary.destination
    if not primary.confirmation_number and secondary.confirmation_number:
        primary.confirmation_number = secondary.confirmation_number
    if not primary.provider and secondary.provider:
        primary.provider = secondary.provider
    if not primary.property_name and secondary.property_name:
        primary.property_name = secondary.property_name
    if not primary.activity_name and secondary.activity_name:
        primary.activity_name = secondary.activity_name
    if not primary.legs and secondary.legs:
        primary.legs = secondary.legs
    return primary


def _events_match_by_date(a: TravelEvent, b: TravelEvent) -> bool:
    """Check if two events without confirmation numbers are likely the same booking."""
    if a.event_type != b.event_type:
        return False

    # Need at least one date on each to compare
    a_date = a.start_date or a.end_date
    b_date = b.start_date or b.end_date
    if not a_date or not b_date:
        return False

    if abs((a_date - b_date).days) > DEDUP_DATE_WINDOW_DAYS:
        return False

    # Same destination city?
    a_dest = (a.destination.city if a.destination else "").lower()
    b_dest = (b.destination.city if b.destination else "").lower()
    if a_dest and b_dest and a_dest == b_dest:
        return True

    # Same provider?
    if a.provider and b.provider and a.provider.lower() == b.provider.lower():
        return True

    return False


def deduplicate(events: List[TravelEvent]) -> List[TravelEvent]:
    """Deduplicate events. Returns a new list with merged unique events."""
    if not events:
        return []

    # Phase 1: Group by confirmation number
    by_conf: defaultdict[str, List[TravelEvent]] = defaultdict(list)
    no_conf: List[TravelEvent] = []

    for ev in events:
        conf = ev.confirmation_number.strip() if ev.confirmation_number else ""
        if conf:
            by_conf[conf].append(ev)
        else:
            no_conf.append(ev)

    merged: List[TravelEvent] = []

    # Merge within each confirmation group
    for conf, group in by_conf.items():
        group.sort(key=_richness_score, reverse=True)
        primary = group[0]
        for secondary in group[1:]:
            primary = _merge_pair(primary, secondary)
        merged.append(primary)

    # Phase 2: For events without confirmation numbers, group by type+city+date window
    used = set()
    for i, ev_a in enumerate(no_conf):
        if i in used:
            continue
        group = [ev_a]
        for j, ev_b in enumerate(no_conf[i + 1:], start=i + 1):
            if j in used:
                continue
            if _events_match_by_date(ev_a, ev_b):
                group.append(ev_b)
                used.add(j)
        used.add(i)

        group.sort(key=_richness_score, reverse=True)
        primary = group[0]
        for secondary in group[1:]:
            primary = _merge_pair(primary, secondary)
        merged.append(primary)

    return merged
