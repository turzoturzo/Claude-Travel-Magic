#!/usr/bin/env python3
"""CLI entry point for the Travel Itinerary Builder.

Usage:
    python build_itinerary.py --mbox path/to/file.mbox [--all] [--output-dir output/]

Options:
    --mbox PATH       Path to the mbox file to process
    --all             Extract from ALL emails, not just travel-classified ones
    --output-dir DIR  Directory for output files (default: output/)
    --format FMT      Output format: timeline, csv, json, all (default: all)
    --dry-run         Show stats without writing files
"""

import argparse
import sys
from pathlib import Path

from travel_itinerary.config import MBOX_PATH, OUTPUT_DIR
from travel_itinerary.pipeline import run_pipeline
from travel_itinerary.output import (
    format_timeline,
    visits_to_csv,
    events_to_csv,
    to_json,
)


def main():
    parser = argparse.ArgumentParser(
        description="Build a city-by-city travel itinerary from email data.",
    )
    parser.add_argument(
        "--mbox",
        default=MBOX_PATH,
        help="Path to the mbox file",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="extract_all",
        help="Extract from all emails, not just travel-classified",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_DIR),
        help="Output directory",
    )
    parser.add_argument(
        "--format",
        choices=["timeline", "csv", "json", "all"],
        default="all",
        help="Output format",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show stats only, don't write files",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    # Run the pipeline
    visits, gaps, events = run_pipeline(
        mbox_path=args.mbox,
        skip_classify=args.extract_all,
        verbose=True,
    )

    if args.dry_run:
        print(f"\nDry run complete. {len(visits)} visits, {len(gaps)} gaps, {len(events)} events.")
        return

    # Output
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ("timeline", "all"):
        timeline_text = format_timeline(visits, gaps)
        timeline_path = output_dir / "itinerary.txt"
        timeline_path.write_text(timeline_text, encoding="utf-8")
        print(f"\nTimeline written to: {timeline_path}")
        # Also print to stdout
        print(timeline_text)

    if args.format in ("csv", "all"):
        visits_path = output_dir / "city_visits.csv"
        events_path = output_dir / "travel_events.csv"
        visits_to_csv(visits, visits_path)
        events_to_csv(events, events_path)
        print(f"CSV written to: {visits_path}, {events_path}")

    if args.format in ("json", "all"):
        json_path = output_dir / "itinerary.json"
        to_json(visits, gaps, json_path)
        print(f"JSON written to: {json_path}")


if __name__ == "__main__":
    main()
