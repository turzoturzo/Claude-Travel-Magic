"""Detect gaps in the timeline where Matt has no evidence of location."""

from typing import List, Tuple

from travel_itinerary.config import GAP_THRESHOLD_DAYS, HOME_BASE_EUROPE
from travel_itinerary.models import CityVisit, Gap

# European cities that suggest BCN as home base
_EUROPEAN_CITIES = {
    "Barcelona", "Madrid", "Paris", "London", "Rome", "Milan", "Berlin",
    "Amsterdam", "Brussels", "Lisbon", "Vienna", "Prague", "Budapest",
    "Zurich", "Geneva", "Copenhagen", "Stockholm", "Oslo", "Helsinki",
    "Dublin", "Edinburgh", "Athens", "Istanbul", "Warsaw", "Bordeaux",
    "Malaga", "Palma de Mallorca", "Fuerteventura", "Frankfurt",
    "Munich", "Hamburg", "Moscow", "Minsk", "St. Petersburg",
    "Tel Aviv",  # close enough for the Europe-base heuristic
}


def detect_gaps(visits: List[CityVisit]) -> Tuple[List[CityVisit], List[Gap]]:
    """Detect gaps between consecutive visits.

    Returns:
        (visits_with_inferred_home, gaps)

    If a gap follows an arrival back in a European city with no outbound booking,
    we infer a return to Barcelona as home base.
    """
    if not visits:
        return visits, []

    # Sort by enter_date (or exit_date if enter is unknown)
    sorted_visits = sorted(
        visits,
        key=lambda v: v.enter_date or v.exit_date or __import__("datetime").date.max,
    )

    gaps: List[Gap] = []
    augmented: List[CityVisit] = []

    for i, visit in enumerate(sorted_visits):
        augmented.append(visit)

        if i < len(sorted_visits) - 1:
            next_visit = sorted_visits[i + 1]
            exit_date = visit.exit_date or visit.enter_date
            next_enter = next_visit.enter_date or next_visit.exit_date

            if exit_date and next_enter:
                gap_days = (next_enter - exit_date).days
                if gap_days > GAP_THRESHOLD_DAYS:
                    gap = Gap(
                        last_known_city=visit.city,
                        last_known_date=exit_date,
                        next_known_city=next_visit.city,
                        next_known_date=next_enter,
                        duration_days=gap_days,
                    )

                    # European departure → infer BCN home base
                    if visit.city in _EUROPEAN_CITIES:
                        gap.note = f"Likely at home base ({HOME_BASE_EUROPE})"
                    else:
                        gap.note = f"No evidence for {gap_days} days"

                    gaps.append(gap)

    return augmented, gaps
