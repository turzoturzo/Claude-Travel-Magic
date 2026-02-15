"""Output formatters: CSV, JSON, HTML, and human-readable timeline."""

import csv
import json
import io
from datetime import date, timedelta
from pathlib import Path
from typing import List

from travel_itinerary.models import CityVisit, Gap, TravelEvent
from travel_itinerary.normalize.city_resolver import CITY_TO_COUNTRY, CITY_TO_COORDS


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


# ---------------------------------------------------------------------------
# Global Entry HTML report
# ---------------------------------------------------------------------------

def _parse_date(s: str):
    """Parse a date string, returning None for '?' or invalid."""
    if not s or s == "?":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def format_global_entry_html(visits: List[CityVisit], path: Path):
    """Write a printable HTML table of international trips for CBP Global Entry."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build international-only rows, sorted most-recent first
    rows = []
    for v in visits:
        country = CITY_TO_COUNTRY.get(v.city, "Unknown")
        if country == "United States":
            continue

        enter = _parse_date(_date_str(v.enter_date))
        exit_ = _parse_date(_date_str(v.exit_date))

        if enter and exit_:
            duration = (exit_ - enter).days
        else:
            duration = ""

        enter_fmt = enter.strftime("%b %d, %Y") if enter else "Unknown"
        exit_fmt = exit_.strftime("%b %d, %Y") if exit_ else "Unknown"

        sort_key = exit_ or enter or date.min
        rows.append((sort_key, country, v.city, enter_fmt, exit_fmt, duration))

    # Most recent first
    rows.sort(key=lambda r: r[0], reverse=True)

    table_rows = ""
    for _, country, city, enter_fmt, exit_fmt, duration in rows:
        dur_str = f"{duration}" if isinstance(duration, int) else "&mdash;"
        table_rows += f"""        <tr>
          <td>{country}</td>
          <td>{city}</td>
          <td>{enter_fmt}</td>
          <td>{exit_fmt}</td>
          <td>{dur_str}</td>
        </tr>\n"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>International Travel History — Matthew Turzo</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    color: #222;
    background: #fff;
    padding: 40px 60px;
    max-width: 900px;
    margin: 0 auto;
  }}
  h1 {{
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 6px;
  }}
  .subtitle {{
    font-size: 13px;
    color: #666;
    margin-bottom: 28px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }}
  thead th {{
    text-align: left;
    font-weight: 600;
    padding: 8px 12px;
    border-bottom: 2px solid #333;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  tbody td {{
    padding: 7px 12px;
    border-bottom: 1px solid #e0e0e0;
  }}
  tbody tr:hover {{
    background: #f8f8f8;
  }}
  .total {{
    margin-top: 20px;
    font-size: 13px;
    color: #666;
  }}
  @media print {{
    body {{ padding: 20px; }}
    tbody tr:hover {{ background: none; }}
  }}
</style>
</head>
<body>
  <h1>International Travel History &mdash; Matthew Turzo</h1>
  <p class="subtitle">{len(rows)} international trips &bull; Generated from email records (2021&ndash;2025)</p>
  <table>
    <thead>
      <tr>
        <th>Country</th>
        <th>City</th>
        <th>Arrival</th>
        <th>Departure</th>
        <th>Days</th>
      </tr>
    </thead>
    <tbody>
{table_rows}    </tbody>
  </table>
  <p class="total">{len(rows)} trips to {len(set(r[1] for r in rows))} countries</p>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Travel map HTML (Leaflet.js)
# ---------------------------------------------------------------------------

def _human_duration(enter_str: str, exit_str: str) -> str:
    """Format duration in human-friendly terms like '12 days' or '2 months'."""
    enter = _parse_date(enter_str)
    exit_ = _parse_date(exit_str)
    if not enter or not exit_:
        return ""
    days = (exit_ - enter).days
    if days == 0:
        return "day trip"
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    months = days / 30.44
    if months < 2:
        return "1 month"
    return f"{months:.0f} months"


def _month_year(date_str: str) -> str:
    """Format a date as 'Jan 2023'."""
    d = _parse_date(date_str)
    if not d:
        return "?"
    return d.strftime("%b %Y")


def format_travel_map_html(visits: List[CityVisit], path: Path):
    """Write an interactive Leaflet travel map as a single HTML file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build visit data for JS
    js_visits = []
    for v in visits:
        coords = CITY_TO_COORDS.get(v.city)
        if not coords:
            continue

        # Skip layovers: same-day visits with no accommodation
        if (v.enter_date and v.exit_date and v.enter_date == v.exit_date
                and not v.accommodations):
            continue

        enter_str = _date_str(v.enter_date)
        exit_str = _date_str(v.exit_date)
        enter = _parse_date(enter_str)
        exit_ = _parse_date(exit_str)
        sort_date = enter or exit_

        hotel = ""
        if v.accommodations:
            hotel = v.accommodations[0].name

        duration = _human_duration(enter_str, exit_str)
        month = _month_year(enter_str) if enter else _month_year(exit_str)
        country = CITY_TO_COUNTRY.get(v.city, "")

        js_visits.append({
            "city": v.city,
            "country": country,
            "lat": coords[0],
            "lng": coords[1],
            "enter": enter_str if enter_str != "?" else "",
            "exit": exit_str if exit_str != "?" else "",
            "month": month,
            "duration": duration,
            "hotel": hotel,
            "sort": sort_date.isoformat() if sort_date else "",
        })

    visits_json = json.dumps(js_visits, ensure_ascii=False)

    # Compute year range from visit data
    years = [int(v["sort"][:4]) for v in js_visits if v.get("sort") and len(v["sort"]) >= 4]
    year_range = f"{min(years)} to {max(years)}" if years else "all time"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Matt's Travel Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Helvetica Neue", Arial, sans-serif;
    background: #f5f5f5;
  }}
  #header {{
    background: #2c3e50;
    color: white;
    padding: 18px 24px;
    text-align: center;
  }}
  #header h1 {{
    font-size: 28px;
    font-weight: 600;
    margin-bottom: 4px;
  }}
  #header p {{
    font-size: 16px;
    opacity: 0.8;
  }}
  #map {{
    width: 100%;
    height: 55vh;
    min-height: 400px;
  }}
  #sidebar {{
    padding: 20px 24px;
    max-width: 1000px;
    margin: 0 auto;
  }}
  #sidebar h2 {{
    font-size: 22px;
    margin-bottom: 14px;
    color: #2c3e50;
  }}
  .trip-list {{
    list-style: none;
    columns: 2;
    column-gap: 32px;
  }}
  .trip-list li {{
    padding: 6px 0;
    font-size: 17px;
    break-inside: avoid;
    border-bottom: 1px solid #e0e0e0;
    line-height: 1.5;
  }}
  .trip-city {{
    font-weight: 600;
    color: #2c3e50;
  }}
  .trip-date {{
    color: #666;
    font-size: 15px;
  }}
  .trip-duration {{
    color: #888;
    font-size: 14px;
  }}
  .year-header {{
    font-size: 20px;
    font-weight: 700;
    color: #2c3e50;
    margin-top: 18px;
    margin-bottom: 6px;
    column-span: all;
  }}
  .top-cities {{
    color: #666;
    font-size: 15px;
    line-height: 1.8;
    margin-bottom: 18px;
    column-span: all;
  }}
  .top-cities h3 {{
    font-size: 18px;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 4px;
  }}
  .top-cities span {{
    white-space: nowrap;
  }}
  .top-cities .sep {{
    color: #ccc;
    margin: 0 6px;
  }}
  .view-toggle {{
    display: flex;
    gap: 6px;
    margin-bottom: 16px;
  }}
  .view-toggle button {{
    padding: 6px 14px;
    border: 1px solid #ccc;
    border-radius: 20px;
    background: #fff;
    color: #666;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }}
  .view-toggle button.active {{
    background: #2c3e50;
    color: #fff;
    border-color: #2c3e50;
  }}
  .country-header {{
    font-size: 19px;
    font-weight: 700;
    color: #2c3e50;
    margin-top: 18px;
    margin-bottom: 4px;
    column-span: all;
  }}
  .country-days {{
    font-weight: 400;
    color: #666;
    font-size: 15px;
  }}
  .leaflet-popup-content {{
    font-size: 15px;
    line-height: 1.5;
  }}
  .leaflet-popup-content strong {{
    font-size: 17px;
  }}
  @media (max-width: 700px) {{
    .trip-list {{ columns: 1; }}
    #header h1 {{ font-size: 22px; }}
  }}
</style>
</head>
<body>
  <div id="header">
    <h1>Where Matt Has Been</h1>
    <p>Travel from {year_range}</p>
  </div>
  <div id="map"></div>
  <div id="sidebar">
    <h2>All Trips</h2>
    <div class="view-toggle">
      <button class="active" data-view="timeline">Timeline</button>
      <button data-view="country">By Country</button>
      <button data-view="city">By City</button>
    </div>
    <div class="top-cities" id="top-cities"></div>
    <ul class="trip-list" id="trip-list"></ul>
  </div>

<script>
(function() {{
  var visits = {visits_json};

  // --- Map ---
  var map = L.map('map').setView([38, -20], 3);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18
  }}).addTo(map);

  // Dedupe cities for pins (show all visits in popup) and compute total days
  var cityMap = {{}};
  visits.forEach(function(v) {{
    if (!cityMap[v.city]) {{
      cityMap[v.city] = {{ lat: v.lat, lng: v.lng, country: v.country, visits: [], totalDays: 0 }};
    }}
    cityMap[v.city].visits.push(v);
    if (v.enter && v.exit) {{
      var d = Math.round((new Date(v.exit) - new Date(v.enter)) / 86400000);
      if (d > 0) cityMap[v.city].totalDays += d;
      else cityMap[v.city].totalDays += 1;
    }} else {{
      cityMap[v.city].totalDays += 1;
    }}
  }});

  // Add pins with radius scaled by total days
  var markers = [];
  Object.keys(cityMap).forEach(function(city) {{
    var c = cityMap[city];
    var visitCount = c.visits.length;
    var totalDays = c.totalDays;
    var popupLines = '<strong>' + city + '</strong>';
    if (c.country) popupLines += '<br>' + c.country;
    popupLines += '<br>' + visitCount + (visitCount === 1 ? ' visit' : ' visits') + ', ' + totalDays + ' days total';
    c.visits.forEach(function(v) {{
      var line = '<br>' + v.month;
      if (v.duration) line += ' (' + v.duration + ')';
      if (v.hotel) line += '<br><em>' + v.hotel + '</em>';
      popupLines += line;
    }});
    var radius = Math.max(6, Math.min(22, 6 + Math.sqrt(totalDays) * 1.5));
    var marker = L.circleMarker([c.lat, c.lng], {{
      radius: radius,
      fillColor: '#e74c3c',
      color: '#c0392b',
      weight: 2,
      fillOpacity: 0.85
    }}).bindPopup(popupLines).addTo(map);
    markers.push(marker);
  }});

  // Fit bounds to all markers
  if (markers.length > 0) {{
    var group = L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
  }}

  // Draw route lines in chronological order
  var sorted = visits.filter(function(v) {{ return v.sort; }})
    .sort(function(a, b) {{ return a.sort < b.sort ? -1 : 1; }});
  var coords = sorted.map(function(v) {{ return [v.lat, v.lng]; }});
  if (coords.length > 1) {{
    L.polyline(coords, {{
      color: '#3498db',
      weight: 2,
      opacity: 0.4,
      dashArray: '6,8'
    }}).addTo(map);
  }}

  // --- Shared data ---
  var cityDaysList = Object.keys(cityMap).map(function(city) {{
    return {{ city: city, days: cityMap[city].totalDays, visits: cityMap[city].visits.length, country: cityMap[city].country }};
  }}).sort(function(a, b) {{ return b.days - a.days; }});

  function humanDays(d) {{
    if (d >= 30) {{
      var m = Math.round(d / 30);
      return m + (m === 1 ? ' month' : ' months');
    }}
    return d + (d === 1 ? ' day' : ' days');
  }}

  var topEl = document.getElementById('top-cities');
  var listEl = document.getElementById('trip-list');

  // --- Render: Timeline (default) ---
  function renderTimeline() {{
    topEl.innerHTML = '';
    listEl.innerHTML = '';

    var topHtml = '<h3>Top Cities</h3>';
    var chips = cityDaysList.map(function(c) {{
      return '<span>' + c.city + ' &mdash; ' + humanDays(c.days) + '</span>';
    }});
    topHtml += chips.join('<span class="sep">|</span>');
    topEl.innerHTML = topHtml;

    var yearGroups = {{}};
    sorted.forEach(function(v) {{
      var year = v.sort ? v.sort.substring(0, 4) : 'Unknown';
      if (!yearGroups[year]) yearGroups[year] = [];
      yearGroups[year].push(v);
    }});
    var years = Object.keys(yearGroups).sort();
    years.forEach(function(year) {{
      var header = document.createElement('li');
      header.className = 'year-header';
      header.textContent = year;
      listEl.appendChild(header);
      yearGroups[year].forEach(function(v) {{
        var li = document.createElement('li');
        var dur = v.duration ? ' (' + v.duration + ')' : '';
        li.innerHTML = '<span class="trip-city">' + v.city + '</span> '
          + '<span class="trip-date">&mdash; ' + v.month + dur + '</span>';
        listEl.appendChild(li);
      }});
    }});
  }}

  // --- Render: By Country ---
  function renderByCountry() {{
    topEl.innerHTML = '';
    listEl.innerHTML = '';

    var countryMap = {{}};
    cityDaysList.forEach(function(c) {{
      var co = c.country || 'Unknown';
      if (!countryMap[co]) countryMap[co] = {{ days: 0, visits: 0, cities: [] }};
      countryMap[co].days += c.days;
      countryMap[co].visits += c.visits;
      countryMap[co].cities.push(c);
    }});
    var countries = Object.keys(countryMap).map(function(co) {{
      return {{ country: co, days: countryMap[co].days, cities: countryMap[co].cities }};
    }}).sort(function(a, b) {{ return b.days - a.days; }});

    countries.forEach(function(co) {{
      var header = document.createElement('li');
      header.className = 'country-header';
      header.innerHTML = co.country + ' <span class="country-days">&mdash; ' + humanDays(co.days) + '</span>';
      listEl.appendChild(header);
      co.cities.sort(function(a, b) {{ return b.days - a.days; }});
      co.cities.forEach(function(c) {{
        var li = document.createElement('li');
        li.innerHTML = '<span class="trip-city">' + c.city + '</span> '
          + '<span class="trip-date">&mdash; ' + humanDays(c.days)
          + ', ' + c.visits + (c.visits === 1 ? ' visit' : ' visits') + '</span>';
        listEl.appendChild(li);
      }});
    }});
  }}

  // --- Render: By City ---
  function renderByCity() {{
    topEl.innerHTML = '';
    listEl.innerHTML = '';

    cityDaysList.forEach(function(c) {{
      var li = document.createElement('li');
      li.innerHTML = '<span class="trip-city">' + c.city + '</span> '
        + '<span class="trip-date">&mdash; ' + humanDays(c.days)
        + ', ' + c.visits + (c.visits === 1 ? ' visit' : ' visits') + '</span>';
      listEl.appendChild(li);
    }});
  }}

  // --- Toggle wiring ---
  var buttons = document.querySelectorAll('.view-toggle button');
  var renderMap = {{ timeline: renderTimeline, country: renderByCountry, city: renderByCity }};
  buttons.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      buttons.forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      renderMap[btn.getAttribute('data-view')]();
    }});
  }});

  // Default render
  renderTimeline();
}})();
</script>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")
