"""Data models for the travel itinerary pipeline."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    FLIGHT = "flight"
    HOTEL = "hotel"
    RAIL = "rail"
    BUS_FERRY = "bus_ferry"
    CAR_RENTAL = "car_rental"
    TOUR = "tour"


class SignalType(str, Enum):
    ENTER = "enter"
    EXIT = "exit"
    PRESENT = "present"


@dataclass
class Location:
    city: str  # canonical city name after normalization
    raw: str = ""  # original string before normalization
    iata: str = ""  # airport code if applicable
    country: str = ""


@dataclass
class FlightLeg:
    origin: Location
    destination: Location
    departure_date: Optional[date] = None
    arrival_date: Optional[date] = None
    flight_number: str = ""
    carrier: str = ""


@dataclass
class TravelEvent:
    event_type: EventType
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    origin: Optional[Location] = None
    destination: Optional[Location] = None
    confirmation_number: str = ""
    provider: str = ""
    property_name: str = ""  # hotel/Airbnb name
    activity_name: str = ""  # tour/event name
    traveler_name: str = ""  # passenger/guest name from booking
    legs: list[FlightLeg] = field(default_factory=list)
    source_email_id: str = ""
    source_subject: str = ""
    extraction_confidence: float = 0.0
    raw_extraction: dict = field(default_factory=dict)


@dataclass
class CitySignal:
    """A single temporal signal about presence in a city."""
    signal_type: SignalType
    city: str
    dt: date
    strength: float = 1.0  # 1.0 = strong (flight), 0.5 = weak (car rental)
    source_event: Optional[TravelEvent] = None
    method: str = ""  # "flight_arrival", "hotel_checkin", etc.


@dataclass
class Accommodation:
    name: str
    provider: str = ""
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    confirmation: str = ""


@dataclass
class Activity:
    name: str
    provider: str = ""
    dt: Optional[date] = None
    confirmation: str = ""


@dataclass
class CityVisit:
    city: str
    enter_date: Optional[date] = None
    exit_date: Optional[date] = None
    enter_method: str = "inferred"
    exit_method: str = "inferred"
    accommodations: list[Accommodation] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    confidence: float = 0.0
    supporting_events: list[TravelEvent] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class Gap:
    last_known_city: str
    last_known_date: Optional[date] = None
    next_known_city: str = ""
    next_known_date: Optional[date] = None
    duration_days: int = 0
    note: str = ""
