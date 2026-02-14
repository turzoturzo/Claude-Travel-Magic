"""Core signal-based timeline assembly: TravelEvents → CityVisits."""

from datetime import date, timedelta
from typing import List, Optional

from travel_itinerary.models import (
    Accommodation,
    Activity,
    CitySignal,
    CityVisit,
    EventType,
    SignalType,
    TravelEvent,
)


# ---------------------------------------------------------------------------
# Step 1: Convert TravelEvents into CitySignals
# ---------------------------------------------------------------------------

def _signals_from_flight(ev: TravelEvent) -> List[CitySignal]:
    signals = []

    if ev.legs:
        for leg in ev.legs:
            dep_date = leg.departure_date or ev.start_date
            arr_date = leg.arrival_date or leg.departure_date or ev.start_date
            if leg.origin and leg.origin.city and dep_date:
                signals.append(CitySignal(
                    signal_type=SignalType.EXIT,
                    city=leg.origin.city,
                    dt=dep_date,
                    strength=1.0,
                    source_event=ev,
                    method="flight_departure",
                ))
            if leg.destination and leg.destination.city and arr_date:
                signals.append(CitySignal(
                    signal_type=SignalType.ENTER,
                    city=leg.destination.city,
                    dt=arr_date,
                    strength=1.0,
                    source_event=ev,
                    method="flight_arrival",
                ))
    else:
        if ev.origin and ev.origin.city and ev.start_date:
            signals.append(CitySignal(
                signal_type=SignalType.EXIT,
                city=ev.origin.city,
                dt=ev.start_date,
                strength=1.0,
                source_event=ev,
                method="flight_departure",
            ))
        if ev.destination and ev.destination.city:
            arr_date = ev.end_date or ev.start_date
            if arr_date:
                signals.append(CitySignal(
                    signal_type=SignalType.ENTER,
                    city=ev.destination.city,
                    dt=arr_date,
                    strength=1.0,
                    source_event=ev,
                    method="flight_arrival",
                ))

    return signals


def _signals_from_hotel(ev: TravelEvent) -> List[CitySignal]:
    signals = []
    city = ev.destination.city if ev.destination else ""
    if not city:
        return signals

    if ev.start_date:
        signals.append(CitySignal(
            signal_type=SignalType.ENTER,
            city=city,
            dt=ev.start_date,
            strength=0.8,
            source_event=ev,
            method="hotel_checkin",
        ))
    if ev.end_date:
        signals.append(CitySignal(
            signal_type=SignalType.EXIT,
            city=city,
            dt=ev.end_date,
            strength=0.8,
            source_event=ev,
            method="hotel_checkout",
        ))
    # PRESENT for each night
    if ev.start_date and ev.end_date:
        d = ev.start_date
        while d < ev.end_date:
            signals.append(CitySignal(
                signal_type=SignalType.PRESENT,
                city=city,
                dt=d,
                strength=0.9,
                source_event=ev,
                method="hotel_stay",
            ))
            d += timedelta(days=1)
    elif ev.start_date:
        signals.append(CitySignal(
            signal_type=SignalType.PRESENT,
            city=city,
            dt=ev.start_date,
            strength=0.9,
            source_event=ev,
            method="hotel_stay",
        ))

    return signals


def _signals_from_rail_bus(ev: TravelEvent) -> List[CitySignal]:
    signals = []
    if ev.origin and ev.origin.city and ev.start_date:
        signals.append(CitySignal(
            signal_type=SignalType.EXIT,
            city=ev.origin.city,
            dt=ev.start_date,
            strength=1.0,
            source_event=ev,
            method=f"{ev.event_type.value}_departure",
        ))
    if ev.destination and ev.destination.city:
        arr_date = ev.end_date or ev.start_date
        if arr_date:
            signals.append(CitySignal(
                signal_type=SignalType.ENTER,
                city=ev.destination.city,
                dt=arr_date,
                strength=1.0,
                source_event=ev,
                method=f"{ev.event_type.value}_arrival",
            ))
    return signals


def _signals_from_car_rental(ev: TravelEvent) -> List[CitySignal]:
    signals = []
    if ev.origin and ev.origin.city and ev.start_date:
        signals.append(CitySignal(
            signal_type=SignalType.PRESENT,
            city=ev.origin.city,
            dt=ev.start_date,
            strength=0.5,
            source_event=ev,
            method="car_rental_pickup",
        ))
    if ev.destination and ev.destination.city and ev.end_date:
        signals.append(CitySignal(
            signal_type=SignalType.PRESENT,
            city=ev.destination.city,
            dt=ev.end_date,
            strength=0.5,
            source_event=ev,
            method="car_rental_return",
        ))
    return signals


def _signals_from_tour(ev: TravelEvent) -> List[CitySignal]:
    signals = []
    city = ev.destination.city if ev.destination else ""
    if city and ev.start_date:
        signals.append(CitySignal(
            signal_type=SignalType.PRESENT,
            city=city,
            dt=ev.start_date,
            strength=0.7,
            source_event=ev,
            method="tour_activity",
        ))
    return signals


def events_to_signals(events: List[TravelEvent]) -> List[CitySignal]:
    """Convert all TravelEvents into flat list of CitySignals."""
    signals = []
    for ev in events:
        if ev.event_type == EventType.FLIGHT:
            signals.extend(_signals_from_flight(ev))
        elif ev.event_type == EventType.HOTEL:
            signals.extend(_signals_from_hotel(ev))
        elif ev.event_type in (EventType.RAIL, EventType.BUS_FERRY):
            signals.extend(_signals_from_rail_bus(ev))
        elif ev.event_type == EventType.CAR_RENTAL:
            signals.extend(_signals_from_car_rental(ev))
        elif ev.event_type == EventType.TOUR:
            signals.extend(_signals_from_tour(ev))
    return signals


# ---------------------------------------------------------------------------
# Step 2: Sort signals — EXIT before ENTER on same day
# ---------------------------------------------------------------------------

_SIGNAL_ORDER = {SignalType.EXIT: 0, SignalType.PRESENT: 1, SignalType.ENTER: 2}


def sort_signals(signals: List[CitySignal]) -> List[CitySignal]:
    return sorted(signals, key=lambda s: (s.dt, _SIGNAL_ORDER[s.signal_type]))


# ---------------------------------------------------------------------------
# Step 3: Walk signals to build CityVisits
# ---------------------------------------------------------------------------

def _collect_accommodations(events: List[TravelEvent]) -> List[Accommodation]:
    accs = []
    for ev in events:
        if ev.event_type == EventType.HOTEL and (ev.property_name or ev.provider):
            accs.append(Accommodation(
                name=ev.property_name or ev.provider or "Unknown hotel",
                provider=ev.provider,
                check_in=ev.start_date,
                check_out=ev.end_date,
                confirmation=ev.confirmation_number,
            ))
    return accs


def _collect_activities(events: List[TravelEvent]) -> List[Activity]:
    acts = []
    for ev in events:
        if ev.event_type == EventType.TOUR and ev.activity_name:
            acts.append(Activity(
                name=ev.activity_name,
                provider=ev.provider,
                dt=ev.start_date,
                confirmation=ev.confirmation_number,
            ))
    return acts


def assemble_visits(signals: List[CitySignal]) -> List[CityVisit]:
    """Walk through sorted signals and produce a list of CityVisits."""
    if not signals:
        return []

    signals = sort_signals(signals)
    visits: List[CityVisit] = []
    current: Optional[CityVisit] = None

    for sig in signals:
        if sig.signal_type == SignalType.ENTER:
            # Close previous visit if open
            if current is not None:
                if not current.exit_date:
                    current.exit_date = sig.dt
                    current.exit_method = "inferred_from_next_arrival"
                    current.notes.append(f"Exit inferred from arrival in {sig.city}")
                visits.append(current)

            # Open new visit
            current = CityVisit(
                city=sig.city,
                enter_date=sig.dt,
                enter_method=sig.method,
            )
            if sig.source_event:
                current.supporting_events.append(sig.source_event)

        elif sig.signal_type == SignalType.EXIT:
            if current is not None and current.city.lower() == sig.city.lower():
                # Explicit exit from current city
                current.exit_date = sig.dt
                current.exit_method = sig.method
                if sig.source_event:
                    current.supporting_events.append(sig.source_event)
                visits.append(current)
                current = None
            elif current is not None:
                # EXIT from a different city — close current, record departure-only
                if not current.exit_date:
                    current.exit_date = sig.dt
                    current.exit_method = "inferred_unknown"
                    current.notes.append(f"Closed: EXIT signal from {sig.city}")
                visits.append(current)
                current = None
                # Don't open a new visit — we just know they left this city
            else:
                # No current visit open — this is a departure without prior arrival
                dep_visit = CityVisit(
                    city=sig.city,
                    enter_date=None,
                    enter_method="inferred",
                    exit_date=sig.dt,
                    exit_method=sig.method,
                    notes=["Departure only — no arrival evidence"],
                )
                if sig.source_event:
                    dep_visit.supporting_events.append(sig.source_event)
                visits.append(dep_visit)

        elif sig.signal_type == SignalType.PRESENT:
            if current is not None and current.city.lower() == sig.city.lower():
                # Strengthen existing visit
                if sig.source_event and sig.source_event not in current.supporting_events:
                    current.supporting_events.append(sig.source_event)
            elif current is not None:
                # PRESENT in a different city — don't override strong visit with weak signal
                if sig.strength >= 0.7:
                    # Strong enough to close current and start new
                    if not current.exit_date:
                        current.exit_date = sig.dt
                        current.exit_method = "inferred_from_presence_elsewhere"
                        current.notes.append(f"Exit inferred from presence in {sig.city}")
                    visits.append(current)
                    current = CityVisit(
                        city=sig.city,
                        enter_date=sig.dt,
                        enter_method=sig.method,
                    )
                    if sig.source_event:
                        current.supporting_events.append(sig.source_event)
                # Weak signals (car rental) — just ignore
            else:
                # No current visit — start a weak one
                current = CityVisit(
                    city=sig.city,
                    enter_date=sig.dt,
                    enter_method=sig.method,
                    notes=["Started from PRESENT signal only"],
                )
                if sig.source_event:
                    current.supporting_events.append(sig.source_event)

    # Close any remaining visit
    if current is not None:
        if not current.exit_date:
            current.notes.append("No exit evidence — visit may still be ongoing or exit unknown")
        visits.append(current)

    # Post-process: attach accommodations and activities, score confidence
    for visit in visits:
        visit.accommodations = _collect_accommodations(visit.supporting_events)
        visit.activities = _collect_activities(visit.supporting_events)
        visit.confidence = _score_confidence(visit)

    return visits


def _score_confidence(visit: CityVisit) -> float:
    """Score confidence based on evidence quality."""
    score = 0.0

    has_explicit_enter = visit.enter_method and "inferred" not in visit.enter_method
    has_explicit_exit = visit.exit_method and "inferred" not in visit.exit_method

    if has_explicit_enter and has_explicit_exit:
        score = 1.0
    elif has_explicit_enter or has_explicit_exit:
        score = 0.7
    else:
        score = 0.4

    # Boost for supporting evidence
    if visit.accommodations:
        score = min(1.0, score + 0.1)
    if len(visit.supporting_events) >= 3:
        score = min(1.0, score + 0.1)

    return round(score, 2)


def _dedup_accommodations(accs: List[Accommodation]) -> List[Accommodation]:
    """Remove duplicate accommodations by confirmation number or name+dates."""
    seen = set()
    unique = []
    for a in accs:
        key = a.confirmation if a.confirmation else f"{a.name}|{a.check_in}|{a.check_out}"
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


def merge_consecutive_visits(visits: List[CityVisit]) -> List[CityVisit]:
    """Merge consecutive visits to the same city into a single visit.

    When hotel PRESENT signals create multiple entries for the same city
    back-to-back, collapse them into one visit that spans the full range.
    """
    if not visits:
        return visits

    merged: List[CityVisit] = []
    current = visits[0]

    for nxt in visits[1:]:
        same_city = current.city.lower() == nxt.city.lower()

        # Also merge if gap between them is ≤ 1 day
        gap_days = None
        curr_end = current.exit_date or current.enter_date
        nxt_start = nxt.enter_date or nxt.exit_date
        if curr_end and nxt_start:
            gap_days = (nxt_start - curr_end).days

        should_merge = same_city and (gap_days is None or gap_days <= 1)

        if should_merge:
            # Extend current visit
            # Keep the earliest enter
            if nxt.enter_date and (not current.enter_date or nxt.enter_date < current.enter_date):
                current.enter_date = nxt.enter_date
                current.enter_method = nxt.enter_method
            # Keep the latest exit
            if nxt.exit_date and (not current.exit_date or nxt.exit_date > current.exit_date):
                current.exit_date = nxt.exit_date
                current.exit_method = nxt.exit_method
            # Prefer explicit methods over inferred
            if "inferred" in current.enter_method and "inferred" not in nxt.enter_method:
                current.enter_method = nxt.enter_method
            if "inferred" in current.exit_method and "inferred" not in nxt.exit_method:
                current.exit_method = nxt.exit_method
            # Merge supporting data
            for ev in nxt.supporting_events:
                if ev not in current.supporting_events:
                    current.supporting_events.append(ev)
            current.accommodations.extend(nxt.accommodations)
            current.activities.extend(nxt.activities)
            # Don't carry over noise notes from sub-visits
        else:
            # Finalize current and start new
            current.accommodations = _dedup_accommodations(current.accommodations)
            current.confidence = _score_confidence(current)
            # Remove noisy inferred notes when we have a solid merged visit
            current.notes = [n for n in current.notes if "Started from PRESENT" not in n]
            merged.append(current)
            current = nxt

    # Finalize last
    current.accommodations = _dedup_accommodations(current.accommodations)
    current.confidence = _score_confidence(current)
    current.notes = [n for n in current.notes if "Started from PRESENT" not in n]
    merged.append(current)

    return merged


def build_timeline(events: List[TravelEvent]) -> List[CityVisit]:
    """Full pipeline: events → signals → sorted → assembled → merged visits."""
    signals = events_to_signals(events)
    visits = assemble_visits(signals)
    visits = merge_consecutive_visits(visits)
    return visits
