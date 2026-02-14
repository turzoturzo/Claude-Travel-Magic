"""Normalize city names to canonical forms."""

import re
from travel_itinerary.normalize.iata import iata_to_city

# Maps raw variations → canonical name
_ALIASES = {
    # New York variants
    "new york city": "New York",
    "new york, ny": "New York",
    "new york/newark": "New York",
    "new york/newark, nj, us": "New York",
    "nyc": "New York",
    "manhattan": "New York",
    "brooklyn": "New York",
    "newark": "New York",
    "newark, nj": "New York",
    "newark liberty intl, new jersey": "New York",
    "kennedy intl, new york": "New York",
    "john f. kennedy intl, new york": "New York",
    "jfk, new york": "New York",
    "laguardia, new york": "New York",
    # Los Angeles variants
    "los angeles, ca": "Los Angeles",
    "los angeles, ca, us": "Los Angeles",
    "los angeles, ca, us (lax)": "Los Angeles",
    "los angeles intl, california": "Los Angeles",
    "la": "Los Angeles",
    "santa monica": "Los Angeles",
    "santa monica, ca": "Los Angeles",
    "burbank": "Los Angeles",
    "burbank, ca": "Los Angeles",
    "bob hope, california": "Los Angeles",
    "bob hope airport": "Los Angeles",
    "hollywood burbank airport": "Los Angeles",
    # San Francisco
    "san francisco, ca": "San Francisco",
    "sf": "San Francisco",
    # Barcelona
    "barcelona, es": "Barcelona",
    "barcelona, spain": "Barcelona",
    "bcn": "Barcelona",
    # London
    "london, uk": "London",
    "london, gb": "London",
    # Paris
    "paris, france": "Paris",
    "paris, fr": "Paris",
    # Other common
    "washington, dc": "Washington DC",
    "washington dc": "Washington DC",
    "philadelphia, pa": "Philadelphia",
    "boston, ma": "Boston",
    "chicago, il": "Chicago",
    "denver, co": "Denver",
    "atlanta, ga": "Atlanta",
    "atlanta, georgia": "Atlanta",
    "austin, tx": "Austin",
    "nashville, tn": "Nashville",
    "salt lake city, utah": "Salt Lake City",
    "minneapolis/st. paul, minnesota": "Minneapolis",
    "minneapolis/st. paul": "Minneapolis",
    "sedona, az": "Sedona",
    "carlsbad, ca": "Carlsbad",
    "carpinteria, ca": "Carpinteria",
    "palm springs": "Palm Springs",
    "big bear lake": "Big Bear Lake",
    "oklahoma city": "Oklahoma City",
    "clarksville, ar": "Clarksville",
    "amarillo, tx": "Amarillo",
    "memphis": "Memphis",
    "mexico city": "Mexico City",
    "tel aviv": "Tel Aviv",
    "malaga": "Malaga",
    "málaga": "Malaga",
    "bordeaux": "Bordeaux",
    "milan": "Milan",
    "rome": "Rome",
    "moscow": "Moscow",
    "minsk": "Minsk",
    "goa": "Goa",
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "palma de mallorca": "Palma de Mallorca",
    "palma": "Palma de Mallorca",
    "fuerteventura": "Fuerteventura",
    "corralejo": "Fuerteventura",
    "costa rica": "Liberia",  # LIR airport context
    "liberia, cr": "Liberia",
    "frankfurt, de": "Frankfurt",
    "houston, tx": "Houston",
    "sacramento, ca": "Sacramento",
    "san diego, ca": "San Diego",
    "dallas/fort worth": "Dallas",
    "dallas/ft worth": "Dallas",
    "dfw": "Dallas",
    "minneapolis-st paul": "Minneapolis",
    "roanoke": "Roanoke",
    # Hotel names that leak through as cities — map to actual city
    "ca n'alexandre": "Palma de Mallorca",
    "ca n'alexandre - turismo de interior - adults only": "Palma de Mallorca",
    "es princep": "Palma de Mallorca",
    "the big texan motel": "Amarillo",
}

# Words that indicate a string is a hotel/property name, not a city
_HOTEL_INDICATORS = re.compile(
    r'\b(hotel|inn|resort|suites?|motel|hostel|lodge|bnb|airbnb|'
    r'collection|autograph|tapestry|curio|tribute|marriott|hilton|'
    r'hyatt|wyndham|sheraton|westin|aloft|courtyard)\b',
    re.I,
)


def resolve_city(raw: str) -> str:
    """Normalize a raw city/location string to a canonical city name.

    Tries in order:
    1. Exact alias match (case-insensitive)
    2. IATA code match (if input looks like a 3-letter code)
    3. Strip state/country suffixes and try again
    4. Return cleaned-up original
    """
    if not raw:
        return ""

    cleaned = raw.strip()

    # Remove full addresses — just take city portion before street numbers
    # e.g. "Distrikt Hotel NYC, Tapestry Collection by Hilton, 342 W 40th Street, New York, NY 10018"
    # We want "New York" from that
    if re.search(r'\d{5}', cleaned):  # has a zip code
        # Try to extract the city before the state+zip
        m = re.search(r',\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*[A-Z]{2}\s+\d{5}', cleaned)
        if m:
            cleaned = m.group(1)

    lowered = cleaned.lower().strip()

    # 1. Direct alias
    if lowered in _ALIASES:
        return _ALIASES[lowered]

    # 2. IATA code
    if re.match(r'^[A-Z]{3}$', cleaned):
        city = iata_to_city(cleaned)
        if city:
            return city

    # 3. Strip ", STATE" or ", COUNTRY" suffixes
    base = re.sub(r',\s*[A-Z]{2}(\s+\d{5})?$', '', cleaned).strip()
    base_lower = base.lower()
    if base_lower in _ALIASES:
        return _ALIASES[base_lower]

    # 4. Strip ", XX, US" pattern
    base2 = re.sub(r',\s*[A-Z]{2},?\s*(US|USA)?\s*(\([A-Z]{3}\))?$', '', cleaned, flags=re.I).strip()
    base2_lower = base2.lower()
    if base2_lower in _ALIASES:
        return _ALIASES[base2_lower]

    # 5. If it looks like a hotel name, try to find a city in it
    # e.g. "The Ambrose - Santa Monica" → try "Santa Monica"
    if " - " in cleaned:
        after_dash = cleaned.split(" - ")[-1].strip()
        after_lower = after_dash.lower()
        if after_lower in _ALIASES:
            return _ALIASES[after_lower]
        # Also try as-is (it might already be a city name)
        if len(after_dash.split()) <= 3 and after_dash[0].isupper() and not _HOTEL_INDICATORS.search(after_dash):
            return after_dash

    # 6. Detect hotel/property names — these are NOT cities
    if _HOTEL_INDICATORS.search(cleaned):
        # Try to find a city name after a dash or comma
        for sep in [" - ", ", "]:
            if sep in cleaned:
                for part in reversed(cleaned.split(sep)):
                    part = part.strip()
                    part_lower = part.lower()
                    if part_lower in _ALIASES:
                        return _ALIASES[part_lower]
                    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$', part) and not _HOTEL_INDICATORS.search(part):
                        return part
        # Can't extract a city from the hotel name
        return ""

    # 7. Detect airport names — "Kennedy Intl, New York" etc.
    airport_match = re.match(r'^(.+?)\s+(?:Intl|International|Airport|Apt),?\s+(.+)$', cleaned, re.I)
    if airport_match:
        city_part = airport_match.group(2).strip()
        city_lower = city_part.lower()
        if city_lower in _ALIASES:
            return _ALIASES[city_lower]
        return city_part

    # 8. Return with title case cleanup if it looks like a city
    if cleaned and not any(c.isdigit() for c in cleaned) and len(cleaned) < 50:
        return cleaned.title() if cleaned.islower() else cleaned

    return cleaned
