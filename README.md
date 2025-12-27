# Travel Email Sorter

A local, offline tool to classify travel-related emails into mutually exclusive categories using rule-based scoring and multi-language pattern matching.

## Features

- **Offline Processing**: No external APIs or network calls required—works directly on local `.mbox` files.
- **MECE Classification**: Every email is assigned exactly one category from a predefined taxonomy.
- **Multi-Language Support**: Built-in support for English (EN), Spanish (ES), French (FR), German (DE), Italian (IT), and Portuguese (PT).
- **Transparent Scoring**: Results include a `reasons` column explaining why a message was categorized with its specific confidence score.
- **Detailed Output**: Generates CSV and JSONL reports with summary statistics.

## Taxonomy

The tool uses a priority-based system (highest priority first) to resolve overlaps:
1. `FLIGHT_CONFIRMATION`
2. `LODGING_CONFIRMATION`
3. `RAIL_CONFIRMATION`
4. `BUS_FERRY_CONFIRMATION`
5. `CAR_RENTAL_TRANSFER`
6. `TOUR_ACTIVITY_TICKET`
7. `TRAVEL_DOCUMENT_ADMIN`
8. `TRAVEL_CHANGE_DISRUPTION`
9. `TRAVEL_MARKETING_NEWSLETTER`
10. `NON_TRAVEL`

## Usage

### Prerequisites
- Python 3.7+
- Beautiful Soup 4

### Preparation
Install dependencies:
```bash
pip install beautifulsoup4
```

### Running the Sorter
Process an MBOX file:
```bash
python travel_sorter.py --mbox my_emails.mbox --out results.csv
```

Process a directory of `.eml` files:
```bash
python travel_sorter.py --mbox ./my_emls --out results.csv
```

### Options
- `--mbox PATH`: Path to input `.mbox` file or directory of `.eml` files.
- `--out PATH`: Filename for the output CSV. (JSONL and Summary files are also generated automatically).
- `--debug N`: Print detailed scoring breakdowns for the first N messages.

## Example Output
The tool produces:
- `results.csv`: A spreadsheet-ready table of message IDs, subjects, categories, and confidence.
- `results.jsonl`: One JSON object per message for programmatic use.
- `results.summary.txt`: A breakdown of category distribution and confidence levels.

## Pattern Matching Notes
The sorter uses high-signal features like PNR codes, IATA airport pairs, flight numbers, and multi-language keywords to ensure high precision even without ML models.
