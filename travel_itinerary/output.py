"""Output formatters: CSV, JSON, and human-readable timeline."""

import csv
import json
import io
from datetime import date
from pathlib import Path
from typing import List

from travel_itinerary.models import CityVisit, Gap, TravelEvent


def _date_str(d) -> str:
    if d is None:
        return "?"
    if isinstance(d, date):
        return d.isoformat()
    return str(d)


# ---------------------------------------------------------------------------
# Human-readable timeline
# ---------------------------------------------------------------------------

def format_timeline(visits: List[CityVisit], gaps: List[Gap]) -> str:
    """Produce a human-readable line-by-line city itinerary."""
    lines = []
    lines.append("=" * 72)
    lines.append("  TRAVEL ITINERARY — City-by-City Timeline")
    lines.append("=" * 72)
    lines.append("")

    # Merge visits and gaps into one sorted list
    items = []
    for v in visits:
        sort_date = v.enter_date or v.exit_date
        if sort_date:
            items.append(("visit", sort_date, v))
    for g in gaps:
        if g.last_known_date:
            items.append(("gap", g.last_known_date, g))
    items.sort(key=lambda x: x[1])

    current_year = None

    for item_type, sort_date, item in items:
        # Year header
        if sort_date.year != current_year:
            current_year = sort_date.year
            lines.append(f"\n--- {current_year} {'─' * 58}")

        if item_type == "visit":
            v = item
            enter = _date_str(v.enter_date)
            exit_ = _date_str(v.exit_date)
            conf_str = f"  [{v.confidence:.0%}]" if v.confidence else ""

            lines.append(f"\n  {enter}  →  {exit_}  |  {v.city}{conf_str}")
            lines.append(f"    Enter: {v.enter_method}   Exit: {v.exit_method}")

            for acc in v.accommodations:
                checkin = _date_str(acc.check_in)
                checkout = _date_str(acc.check_out)
                lines.append(f"    🏨 {acc.name} ({checkin} → {checkout})")
                if acc.confirmation:
                    lines.append(f"       Ref: {acc.confirmation}")

            for act in v.activities:
                lines.append(f"    🎫 {act.name} ({_date_str(act.dt)})")

            for note in v.notes:
                lines.append(f"    ⚠ {note}")

        elif item_type == "gap":
            g = item
            lines.append(
                f"\n  ··· GAP: {g.duration_days} days "
                f"({_date_str(g.last_known_date)} → {_date_str(g.next_known_date)})"
            )
            lines.append(f"      Last seen: {g.last_known_city}  →  Next seen: {g.next_known_city}")
            if g.note:
                lines.append(f"      Note: {g.note}")

    lines.append(f"\n{'=' * 72}")
    lines.append(f"  Total: {len(visits)} city visits, {len(gaps)} gaps")
    lines.append("=" * 72)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def visits_to_csv(visits: List[CityVisit], path: Path):
    """Write city visits to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "city", "enter_date", "exit_date", "enter_method", "exit_method",
            "accommodations", "activities", "confidence", "notes",
        ])
        for v in visits:
            accs = "; ".join(
                f"{a.name} ({_date_str(a.check_in)}→{_date_str(a.check_out)})"
                for a in v.accommodations
            )
            acts = "; ".join(
                f"{a.name} ({_date_str(a.dt)})" for a in v.activities
            )
            notes = "; ".join(v.notes)
            writer.writerow([
                v.city, _date_str(v.enter_date), _date_str(v.exit_date),
                v.enter_method, v.exit_method, accs, acts,
                f"{v.confidence:.2f}", notes,
            ])


def events_to_csv(events: List[TravelEvent], path: Path):
    """Write raw events to CSV for debugging."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "event_type", "start_date", "end_date", "origin", "destination",
            "confirmation", "provider", "property_name", "activity_name",
            "source_subject", "confidence",
        ])
        for ev in events:
            writer.writerow([
                ev.event_type.value,
                _date_str(ev.start_date), _date_str(ev.end_date),
                ev.origin.city if ev.origin else "",
                ev.destination.city if ev.destination else "",
                ev.confirmation_number, ev.provider,
                ev.property_name, ev.activity_name,
                ev.source_subject, f"{ev.extraction_confidence:.2f}",
            ])


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _visit_to_dict(v: CityVisit) -> dict:
    return {
        "city": v.city,
        "enter_date": _date_str(v.enter_date),
        "exit_date": _date_str(v.exit_date),
        "enter_method": v.enter_method,
        "exit_method": v.exit_method,
        "accommodations": [
            {
                "name": a.name,
                "provider": a.provider,
                "check_in": _date_str(a.check_in),
                "check_out": _date_str(a.check_out),
                "confirmation": a.confirmation,
            }
            for a in v.accommodations
        ],
        "activities": [
            {
                "name": a.name,
                "provider": a.provider,
                "date": _date_str(a.dt),
                "confirmation": a.confirmation,
            }
            for a in v.activities
        ],
        "confidence": v.confidence,
        "notes": v.notes,
    }


def _gap_to_dict(g: Gap) -> dict:
    return {
        "last_known_city": g.last_known_city,
        "last_known_date": _date_str(g.last_known_date),
        "next_known_city": g.next_known_city,
        "next_known_date": _date_str(g.next_known_date),
        "duration_days": g.duration_days,
        "note": g.note,
    }


def to_json(visits: List[CityVisit], gaps: List[Gap], path: Path):
    """Write full itinerary as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "visits": [_visit_to_dict(v) for v in visits],
        "gaps": [_gap_to_dict(g) for g in gaps],
        "summary": {
            "total_visits": len(visits),
            "total_gaps": len(gaps),
            "cities_visited": sorted(set(v.city for v in visits if v.city)),
        },
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
