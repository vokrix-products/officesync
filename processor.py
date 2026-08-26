import csv
import datetime as dt
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pdfplumber
from openai import OpenAI

STATUS_VALUES = [
    "available:good",
    "valid:good",
    "expired:warning",
    "no_show:critical",
    "missing:critical",
    "flagged:critical",
    "maintenance_cleaning:warning",
    "over_capacity:critical",
]

HEADER_ALIASES = {
    "desk id": "desk_id",
    "deskid": "desk_id",
    "desk": "desk_id",
    "desk name": "desk_id",
    "desk id/name": "desk_id",
    "id": "desk_id",
    "floor": "floor",
    "zone": "zone",
    "area": "area",
    "floor/zone/area": "floor",
    "desk type": "desk_type",
    "type": "desk_type",
    "desk type/features": "desk_type",
    "features": "features",
    "desk features": "features",
    "map coordinate": "map_coordinate",
    "map label": "map_coordinate",
    "coordinate": "map_coordinate",
    "label": "map_coordinate",
    "employee name": "employee_name",
    "name": "employee_name",
    "employee": "employee_name",
    "employee email": "employee_email",
    "email": "employee_email",
    "department": "department",
    "team": "team",
    "department/team": "department",
    "recurring schedule preset": "recurring_schedule_preset",
    "recurring schedule": "recurring_schedule_preset",
    "schedule preset": "recurring_schedule_preset",
    "schedule": "recurring_schedule_preset",
    "assigned/permanent desk": "assigned_permanent_desk",
    "assigned": "assigned_permanent_desk",
    "permanent desk": "assigned_permanent_desk",
    "assigned/permanent": "assigned_permanent_desk",
    "team capacity cap": "team_capacity_cap",
    "capacity cap": "team_capacity_cap",
    "team cap": "team_capacity_cap",
    "team capacity": "team_capacity_cap",
    "booking date": "due_date",
    "due date": "due_date",
    "date": "due_date",
    "status": "status",
    "notes": "notes",
    "maintenance/cleaning mode": "maintenance_cleaning_mode",
    "maintenance": "maintenance_cleaning_mode",
    "cleaning": "maintenance_cleaning_mode",
}

DEFAULT_DETAILS_FIELDS = [
    "desk_id",
    "floor",
    "zone",
    "area",
    "desk_type",
    "features",
    "map_coordinate",
    "employee_name",
    "employee_email",
    "department",
    "team",
    "recurring_schedule_preset",
    "assigned_permanent_desk",
    "team_capacity_cap",
    "notes",
    "maintenance_cleaning_mode",
]


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            parts = []
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    parts.append(page_text)
        return "\n".join(parts).strip()
    except Exception:
        return ""


def _extract_text_from_excel(file_bytes: bytes) -> str:
    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes), data_only=True, read_only=True
        )
    except Exception:
        return ""

    lines = []
    try:
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [
                    "" if c is None else str(c).replace("\n", " ").replace("\r", " ")
                    for c in row
                ]
                if any(c.strip() for c in cells):
                    lines.append("\t".join(cells))
    finally:
        wb.close()
    return "\n".join(lines)


def _parse_tabular(text: str) -> Tuple[List[str], List[List[str]]]:
    sample = text[:4096]
    if not sample.strip():
        return [], []

    delimiter = None
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except Exception:
        if "," in sample:
            delimiter = ","
        elif "\t" in sample:
            delimiter = "\t"
        else:
            return [], []

    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except Exception:
        return [], []

    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        return [], []

    header = [h.strip().lower() for h in rows[0]]
    if not header:
        return [], []

    return header, rows[1:]


def _get_canonical_field(field: str) -> str:
    field = field.strip().lower()
    if field in HEADER_ALIASES:
        return HEADER_ALIASES[field]
    return field.replace(" ", "_").replace("/", "_").replace("-", "_")


def _map_record_keys(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for raw_key, value in row_dict.items():
        key = _get_canonical_field(str(raw_key))
        if key not in out:
            out[key] = str(value).strip() if value is not None else ""
    return out


def _normalize_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.date().isoformat()

    s = str(value).strip()


def _parse_tabular(text: str) -> Tuple[List[str], List[List[str]]]:
    sample = text[:4096]
    if not sample.strip():
        return [], []

    delimiter = None
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except Exception:
        if "," in sample:
            delimiter = ","
        elif "\t" in sample:
            delimiter = "\t"
        else:
            return [], []

    try:
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except Exception:
        return [], []

    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        return [], []

    header = [h.strip().lower() for h in rows[0]]
    if not header:
        return [], []

    return header, rows[1:]


def _get_canonical_field(field: str) -> str:
    field = field.strip().lower()
    if field in HEADER_ALIASES:
        return HEADER_ALIASES[field]
    return field.replace(" ", "_").replace("/", "_").replace("-", "_")


def _map_record_keys(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for raw_key, value in row_dict.items():
        key = _get_canonical_field(str(raw_key))
        if key not in out:
            out[key] = str(value).strip() if value is not None else ""
    return out


def _normalize_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.date().isoformat()

    s = str(value).strip()
    if not s:
        return None

    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        pass

    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue

    m = re.match(r"^\d{4}-\d{2}-\d{2}", s)
    if m:
        return m.group(0)

    return None


def _infer_status(record: Dict[str, Any]) -> str:
    if record.get("status"):
        status = str(record["status"]).strip().lower()
        if status in STATUS_VALUES:
            return status

    combined = (
        str(record.get("notes", ""))
        + " "
        + str(record.get("maintenance_cleaning_mode", ""))
        + " "
        + str(record.get("status", ""))
    )

    if re.search(r"maintenance|cleaning", combined, re.I):
        return "maintenance_cleaning:warning"

    if not record.get("employee_name") and not record.get("desk_id"):
        return "missing:critical"

    if re.search(r"over.?capacity|team.?cap exceeded|over.?limit", combined, re.I):
        return "over_capacity:critical"

    if re.search(r"conflict|double.?book|flag", combined, re.I):
        return "flagged:critical"

    if re.search(r"no.?show", combined, re.I):
        return "no_show:critical"

    if re.search(r"expired", combined, re.I):
        return "expired:warning"

    if record.get("employee_name"):
        assigned = str(record.get("assigned_permanent_desk", "")).strip().lower()
        if assigned in {"false", "no", "n", "0"}:
            return "available:good"
        return "valid:good"

    return "available:good"


def _normalize_record(record: Dict[str, Any], idx: int = 0) -> Dict[str, Any]:
    if not isinstance(record, dict):
        record = {"notes": str(record)}

    details = record.get("details")
    if not isinstance(details, dict):
        details = {}
    else:
        details = dict(details)

    for field in DEFAULT_DETAILS_FIELDS:
        if field in record and field not in details:
            details[field] = record[field]

    title = (
        record.get("title")
        or details.get("employee_name")
        or details.get("desk_id")
        or "Untitled"
    )
    title = str(title).strip() or "Untitled"

    status = str(record.get("status") or "missing:critical").strip()
    if status not in STATUS_VALUES:
        status = "missing:critical"

    due_date = _normalize_date(record.get("due_date") or record.get("dueDate"))

    return {
        "title": title,
        "status": status,
        "details": details,
        "due_date": due_date,
    }


def _extract_records_from_text(text: str) -> List[Dict[str, Any]]:
    header, rows = _parse_tabular(text)
    if not header:
        return []

    records: List[Dict[str, Any]] = []
    for row in rows:
        row_dict: Dict[str, Any] = {}
        for i, value in enumerate(row):
            if i < len(header):
                row_dict[header[i].strip()] = value

        if not row_dict:
            continue

        mapped = _map_record_keys(row_dict)
        if not mapped:
            continue

        if not mapped.get("status"):
            mapped["status"] = _infer_status(mapped)

        if "due_date" not in mapped:
            mapped["due_date"] = (
                mapped.get("booking_date") or mapped.get("date") or None
            )

        records.append(mapped)

    return records


def process_file(file_bytes: bytes) -> List[Dict[str, Any]]:
    if not file_bytes:
        return []

    text = _extract_text_from_pdf(file_bytes)
    if not text:
        text = _extract_text_from_excel(file_bytes)
    if not text:
        try:
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            text = ""

    if not text.strip():
        return []

    if os.environ.get("DEEPSEEK_API_KEY"):
        try:
            extracted = _extract_records_with_deepseek(text)
            if extracted:
                return [_normalize_record(record, i) for i, record in enumerate(extracted)]
        except Exception:
            pass

    records = _extract_records_from_text(text)
    if records:
        return [_normalize_record(record, i) for i, record in enumerate(records)]

    first_line = next(
        (line.strip() for line in text.splitlines() if line.strip()), "Untitled"
    )
    return [
        _normalize_record(
            {
                "title": first_line,
                "status": "missing:critical",
                "details": {"notes": text.strip()},
            }
        )
    ]
