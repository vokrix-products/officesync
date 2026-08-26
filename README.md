# OfficeSync

OfficeSync is a desk-booking backend that ingests messy office desk data — PDF exports, Excel sheets, CSVs, or plain text — and normalizes it into clean, structured records with predictable status values. The OfficeSync poller feeds raw file bytes into `process_file()` and receives a JSON-ready list of records, each with a `title`, `status`, `details`, and `due_date`.

## Archetype

This repository is the **pure processing backend** in the OfficeSync system. It contains no HTTP server and no persistence. It is a single, testable module (`processor.py`) that the poller imports and calls directly.

## What the poller expects as input

The poller calls `process_file(file_bytes: bytes)` with one argument: the raw bytes of an uploaded file. Supported file types:

| Type | Notes |
|---|---|
| PDF | Text is extracted with `pdfplumber` |
| Excel (.xlsx) | All worksheets are flattened to tabular text with `openpyxl` |
| CSV | Parsed locally with `csv` |
| Plain text | Treated as tabular if possible, otherwise as one raw record |

Output is a list of dicts. Each record has:

- `title` — employee name if present, otherwise desk id (never document type).
- `status` — one of `available:good`, `valid:good`, `expired:warning`, `no_show:critical`, `missing:critical`, `flagged:critical`, `maintenance_cleaning:warning`, `over_capacity:critical`.
- `details` — normalized fields including `desk_id`, `floor`, `zone`, `area`, `desk_type`, `features`, `map_coordinate`, `employee_name`, `employee_email`, `department`, `team`, `recurring_schedule_preset`, `assigned_permanent_desk`, `team_capacity_cap`, `notes`, `maintenance_cleaning_mode`.
- `due_date` — ISO-8601 date or `null`.

## Extraction modes

- If `DEEPSEEK_API_KEY` is set, structured extraction uses DeepSeek `deepseek-v4-flash`.
- If no API key is set, `process_file()` falls back to a deterministic local CSV/text parser with header aliasing and status inference.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python3 run_demo.py
python3 run_tests.py
```

Dashboard: https://officesync.vokrix.co
Vercel: officesync
Railway: officesync
Cloudflare: officesync.vokrix.co
