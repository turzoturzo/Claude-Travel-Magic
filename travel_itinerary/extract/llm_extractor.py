"""LLM extraction of structured travel data from email content."""

import json
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from travel_itinerary.config import (
    GOOGLE_API_KEY,
    LLM_BACKEND,
    LLM_MODEL_FALLBACK,
    LLM_MODEL_PRIMARY,
    MAX_BODY_CHARS,
    OPENAI_API_KEY,
)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if LLM_BACKEND == "gemini":
            _client = OpenAI(
                api_key=GOOGLE_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
        else:
            _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


EXTRACTION_PROMPT = """\
You are a structured-data extraction engine for travel booking emails.

Given an email subject, sender, and body, extract ALL travel booking information.
Return a JSON object (no markdown fences) with these fields:

{
  "event_type": "flight" | "hotel" | "rail" | "bus_ferry" | "car_rental" | "tour" | null,
  "start_date": "YYYY-MM-DD or null",
  "end_date": "YYYY-MM-DD or null",
  "origin_city": "city name or null",
  "origin_iata": "3-letter code or null",
  "destination_city": "city name or null",
  "destination_iata": "3-letter code or null",
  "confirmation_number": "string or null",
  "provider": "airline/hotel chain/platform name or null",
  "property_name": "hotel or Airbnb property name or null",
  "activity_name": "tour/event/show name or null",
  "legs": [
    {
      "origin_city": "city",
      "origin_iata": "code",
      "destination_city": "city",
      "destination_iata": "code",
      "departure_date": "YYYY-MM-DD",
      "flight_number": "UA123",
      "carrier": "United Airlines"
    }
  ],
  "traveler_name": "full name of the passenger/guest or null",
  "confidence": 0.0 to 1.0
}

Rules:
- For flights: origin = departure city, destination = arrival city. Extract ALL legs if multi-segment.
- For hotels: destination = hotel city. start_date = check-in, end_date = check-out.
- For trains/buses: origin = departure station city, destination = arrival station city.
- For car rentals: origin = pickup city, destination = return city (may be same).
- For tours/activities: destination = activity city, activity_name = event name, start_date = event date.
- traveler_name: the passenger, guest, or traveler's full name as shown on the booking. If multiple travelers, return the primary one. null if not identifiable.
- confirmation_number: booking reference, PNR, itinerary number — whatever uniquely identifies the booking.
- property_name: the actual hotel/Airbnb name (e.g. "The Lexington NYC"), not the platform.
- Dates must be YYYY-MM-DD. If you only see a month and day, use the email's year.
  The email's send date is included — use it to infer the year when the booking date only shows month/day.
- If the email is a review request, check-in reminder, or receipt for a past stay, still extract the travel dates.
- If the email is clearly not a travel booking (marketing, account alerts), set event_type to null.
- Return ONLY the JSON object, no extra text.
"""


def _build_user_message(email_content: Dict[str, Any]) -> str:
    body = email_content.get("body", "")[:MAX_BODY_CHARS]
    return (
        f"Subject: {email_content.get('subject', '')}\n"
        f"From: {email_content.get('from', '')}\n"
        f"Date: {email_content.get('date', '')}\n"
        f"---\n{body}"
    )


def _parse_response(text: str) -> Dict[str, Any]:
    """Parse the LLM response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"event_type": None, "confidence": 0.0, "parse_error": text[:200]}


def extract_single(
    email_content: Dict[str, Any],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract structured travel data from a single email using the LLM."""
    client = _get_client()
    model = model or LLM_MODEL_PRIMARY
    user_msg = _build_user_message(email_content)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        max_tokens=1000,
    )
    raw = resp.choices[0].message.content or ""
    result = _parse_response(raw)
    result["_model_used"] = model
    return result


def extract_with_fallback(email_content: Dict[str, Any]) -> Dict[str, Any]:
    """Try primary model; fall back to stronger model if key fields are null."""
    result = extract_single(email_content, model=LLM_MODEL_PRIMARY)

    # Fall back to stronger model if key fields are missing
    if result.get("event_type"):
        missing_dates = not result.get("start_date")
        missing_location = not result.get("destination_city") and not result.get("destination_iata")
        if missing_dates or missing_location:
            result = extract_single(email_content, model=LLM_MODEL_FALLBACK)

    return result


def extract_batch(
    emails: List[Dict[str, Any]],
    progress_callback=None,
) -> List[Dict[str, Any]]:
    """Extract from a list of emails with optional progress callback."""
    results = []
    for i, email_content in enumerate(emails):
        result = extract_with_fallback(email_content)
        results.append(result)
        if progress_callback:
            progress_callback(i + 1, len(emails))
    return results
