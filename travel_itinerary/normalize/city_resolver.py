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
    "montreal": "Montreal",
    "albuquerque": "Albuquerque",
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


# ---------------------------------------------------------------------------
# City → Country mapping (for Global Entry report)
# ---------------------------------------------------------------------------

CITY_TO_COUNTRY = {
    "Albuquerque": "United States",
    "Amarillo": "United States",
    "Atlanta": "United States",
    "Barcelona": "Spain",
    "Big Bear Lake": "United States",
    "Carlsbad": "United States",
    "Clarksville": "United States",
    "Dallas": "United States",
    "Denver": "United States",
    "Frankfurt": "Germany",
    "Fuerteventura": "Spain",
    "Houston": "United States",
    "La Costa": "United States",
    "Liberia": "Costa Rica",
    "London": "United Kingdom",
    "Los Angeles": "United States",
    "Memphis": "United States",
    "Mexico City": "Mexico",
    "Minneapolis": "United States",
    "Montreal": "Canada",
    "Nashville": "United States",
    "New York": "United States",
    "Oklahoma City": "United States",
    "Palm Springs": "United States",
    "Palma de Mallorca": "Spain",
    "Paris": "France",
    "Philadelphia": "United States",
    "Roanoke": "United States",
    "Sacramento": "United States",
    "Salt Lake City": "United States",
    "Sedona": "United States",
    "Washington DC": "United States",
}


# ---------------------------------------------------------------------------
# City → (lat, lng) mapping (for travel map)
# ---------------------------------------------------------------------------

CITY_TO_COORDS = {
    # --- A ---
    "Abu Dhabi": (24.4539, 54.3773),
    "Albuquerque": (35.0844, -106.6504),
    "Alp": (42.3728, 1.8833),
    "Amarillo": (35.2220, -101.8313),
    "Amsterdam": (52.3676, 4.9041),
    "Antalya": (36.8969, 30.7133),
    "Arrecife": (28.9630, -13.5477),
    "Atlanta": (33.7490, -84.3880),
    "Atlantic City": (39.3643, -74.4229),
    "Austin": (30.2672, -97.7431),
    # --- B ---
    "Bamberg": (49.8988, 10.9028),
    "Bangalore": (12.9716, 77.5946),
    "Bangkok": (13.7563, 100.5018),
    "Barcelona": (41.3874, 2.1686),
    "Beijing": (39.9042, 116.4074),
    "Bensalem": (40.1046, -74.9516),
    "Berkeley": (37.8716, -122.2727),
    "Berlin": (52.5200, 13.4050),
    "Berlin, DE": (52.5200, 13.4050),
    "Berlin, Germany": (52.5200, 13.4050),
    "Big Bear Lake": (34.2439, -116.9114),
    "Bilbao": (43.2630, -2.9350),
    "Bordeaux": (44.8378, -0.5792),
    "Bordes d'Envalira": (42.5419, 1.7316),
    "Boston": (42.3601, -71.0589),
    "Boston Back Bay": (42.3503, -71.0810),
    "Buenos Aires": (-34.6037, -58.3816),
    "Buenos Aires, Argentina": (-34.6037, -58.3816),
    # --- C ---
    "Cambridge": (42.3736, -71.1097),
    "Cancun": (21.1619, -86.8515),
    "Cancun, MX": (21.1619, -86.8515),
    "Carlsbad": (33.1581, -117.3506),
    "Carpinteria": (34.3989, -119.5184),
    "Castelldefels": (41.2800, 1.9767),
    "Caye Caulker": (17.7514, -88.0290),
    "Charleston": (32.7765, -79.9311),
    "Charlotte": (35.2271, -80.8431),
    "Chicago": (41.8781, -87.6298),
    "Cincinnati": (39.1031, -84.5120),
    "Ciudad de México": (19.4326, -99.1332),
    "Clarksville": (35.4676, -93.4616),
    "Copenhagen": (55.6761, 12.5683),
    # --- D ---
    "Dallas": (32.7767, -96.7970),
    "Delhi": (28.7041, 77.1025),
    "Denver": (39.7392, -104.9903),
    "Detroit": (42.3314, -83.0458),
    "Detroit Wayne": (42.2124, -83.3534),
    "Detroit, MI": (42.3314, -83.0458),
    "Devanahalli": (13.2468, 77.7120),
    "Dublin": (53.3498, -6.2603),
    # --- E ---
    "El Prat de Llobregat": (41.2971, 2.0785),
    "Encinitas": (33.0370, -117.2920),
    "Erlangen": (49.5897, 11.0078),
    # --- F ---
    "Fiumicino (Rome)": (41.8003, 12.2389),
    "Florence": (43.7696, 11.2558),
    "Fort Lauderdale": (26.1224, -80.1373),
    "Frankfurt": (50.1109, 8.6821),
    "Fuerteventura": (28.3587, -14.0538),
    # --- G ---
    "Goa": (15.2993, 74.1240),
    "Guangzhou": (23.1291, 113.2644),
    # --- H ---
    "Heathrow (London)": (51.4700, -0.4543),
    "Holbox": (21.5224, -87.3794),
    "Hong Kong": (22.3193, 114.1694),
    "Houston": (29.7604, -95.3698),
    # --- I ---
    "Inverness": (57.4778, -4.2247),
    "Istanbul": (41.0082, 28.9784),
    # --- J ---
    "Jakarta": (-6.2088, 106.8456),
    "Jamaica": (40.6915, -73.8073),
    # --- K ---
    "Karlsruhe": (49.0069, 8.4037),
    "Keflavik": (63.9850, -22.5975),
    # --- L ---
    "La Costa": (33.0781, -117.2653),
    "Lake Sonoma": (38.7180, -123.0050),
    "Lanzarote": (29.0469, -13.5900),
    "Liberia": (10.6346, -85.4408),
    "Lima": (-12.0464, -77.0428),
    "Lisbon": (38.7223, -9.1393),
    "Lisbon, Portugal": (38.7223, -9.1393),
    "London": (51.5074, -0.1278),
    "London City": (51.5074, -0.1278),
    "London, England": (51.5074, -0.1278),
    "London-Gatwick": (51.1537, -0.1821),
    "Los Angeles": (34.0522, -118.2437),
    "Los Ángeles": (34.0522, -118.2437),
    "Lyon": (45.7640, 4.8357),
    # --- M ---
    "Madison": (43.0731, -89.4012),
    "Malaga": (36.7213, -4.4214),
    "Malta": (35.9375, 14.3754),
    "Manavgat": (36.7833, 31.4333),
    "Manchester": (53.4808, -2.2426),
    "Manila": (14.5995, 120.9842),
    "Marrakech": (31.6295, -7.9811),
    "Memphis": (35.1495, -90.0490),
    "Menlo Park": (37.4530, -122.1817),
    "Messina": (38.1938, 15.5540),
    "Mexico City": (19.4326, -99.1332),
    "Miami": (25.7617, -80.1918),
    "Miami Beach": (25.7907, -80.1300),
    "Miami, FL": (25.7617, -80.1918),
    "Milan": (45.4642, 9.1900),
    "Minneapolis": (44.9778, -93.2650),
    "Minsk": (53.9045, 27.5615),
    "Montreal": (45.5017, -73.5673),
    "Moscow": (55.7558, 37.6173),
    "Munich": (48.1351, 11.5820),
    "Munich, DE": (48.1351, 11.5820),
    # --- N ---
    "Narita": (35.7720, 140.3929),
    "Nashville": (36.1627, -86.7816),
    "New Delhi": (28.6139, 77.2090),
    "New Jersey": (40.0583, -74.4057),
    "New Orleans": (29.9511, -90.0715),
    "New Orleans, LA": (29.9511, -90.0715),
    "New York": (40.7128, -74.0060),
    "New York Penn": (40.7506, -73.9935),
    "New York-Kennedy": (40.6413, -73.7781),
    "Nottingham": (52.9548, -1.1581),
    "Nuremberg": (49.4521, 11.0767),
    # --- O ---
    "Oakland": (37.8044, -122.2712),
    "Oklahoma City": (35.4676, -97.5164),
    # --- P ---
    "Palm Springs": (33.8303, -116.5453),
    "Palma de Mallorca": (39.5696, 2.6502),
    "Paris": (48.8566, 2.3522),
    "Philadelphia": (39.9526, -75.1652),
    "Phoenix, AZ": (33.4484, -112.0740),
    "Phuket": (7.8804, 98.3923),
    "Playa Avellanas": (10.1283, -85.8386),
    "Playa Blanca": (28.8603, -13.8312),
    "Playa del Carmen": (20.6296, -87.0739),
    "Portland": (45.5152, -122.6784),
    "Prats i Sansor": (42.3894, 1.8003),
    "Providence": (41.8240, -71.4128),
    "Puerto Vallarta": (20.6534, -105.2253),
    # --- Q ---
    "Queens": (40.7282, -73.7949),
    # --- R ---
    "Raleigh": (35.7796, -78.6382),
    "Renton": (47.4829, -122.2171),
    "Reykjavik": (64.1466, -21.9426),
    "Rio De Janeiro, Brazil": (-22.9068, -43.1729),
    "Rio de Janeiro": (-22.9068, -43.1729),
    "Roanoke": (37.2710, -79.9414),
    "Rome": (41.9028, 12.4964),
    # --- S ---
    "Sacramento": (38.5816, -121.4944),
    "Salisbury": (38.3607, -75.5994),
    "Salt Lake City": (40.7608, -111.8910),
    "San Diego": (32.7157, -117.1611),
    "San Francisco": (37.7749, -122.4194),
    "San Juan": (18.4655, -66.1057),
    "Santa Cruz": (36.9741, -122.0308),
    "Santa Rosa": (38.4405, -122.7141),
    "Santiago": (42.8782, -8.5448),
    "Sao Paulo": (-23.5505, -46.6333),
    "Scottsdale": (33.4942, -111.9261),
    "Seattle": (47.6062, -122.3321),
    "Seattle, WA": (47.6062, -122.3321),
    "Sedona": (34.8697, -111.7610),
    "Seoul": (37.5665, 126.9780),
    "Shanghai": (31.2304, 121.4737),
    "Singapore": (1.3521, 103.8198),
    "Solana Beach": (32.9912, -117.2712),
    "Stockholm": (59.3293, 18.0686),
    "Sydney": (-33.8688, 151.2093),
    "Sydney, Australia": (-33.8688, 151.2093),
    # --- T ---
    "Tel Aviv": (32.0853, 34.7818),
    "Tenerife North": (28.4827, -16.3415),
    "Toronto": (43.6532, -79.3832),
    "Toronto, ON": (43.6532, -79.3832),
    "Truckee": (39.3280, -120.1833),
    "Tuckerton": (39.6034, -74.3401),
    "Tulum": (20.2114, -87.4654),
    # --- U ---
    "Urtx": (42.3569, 1.9172),
    "Urumqi": (43.8256, 87.6168),
    # --- V ---
    "Valletta": (35.8989, 14.5146),
    "Van Nuys": (34.1867, -118.4487),
    "Vancouver": (49.2827, -123.1207),
    "Varsovia": (52.2297, 21.0122),
    "Vienna": (48.2082, 16.3738),
    # --- W ---
    "Warszawa": (52.2297, 21.0122),
    "Washington": (38.9072, -77.0369),
    "Washington DC": (38.9072, -77.0369),
    "Washington Dulles": (38.9531, -77.4565),
    "Webster": (43.2120, -77.4298),
    "West Kill": (42.2098, -74.3473),
    "West Orange": (40.7987, -74.2390),
    # --- Z ---
    "Zurich": (47.3769, 8.5417),
}
