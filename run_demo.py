import json
import os

from processor import process_file

DEMO_CSV = b"""desk_id,floor,zone,desk_type,employee_name,employee_email,department,recurring_schedule_preset,assigned_permanent_desk,team_capacity_cap
D-101,1,Zone A,standing,Ada Lovelace,ada@example.com,Engineering,Mon-Wed,true,25
D-102,2,Zone B,accessible,Grace Hopper,grace@example.com,Engineering,Mon/Wed/Fri,true,25
"""


def main() -> int:
    # Use local parser in demo; no external API call needed.
    os.environ.pop("DEEPSEEK_API_KEY", None)

    records = process_file(DEMO_CSV)

    assert isinstance(records, list)
    assert records
    for record in records:
        assert set(record) == {"title", "status", "details", "due_date"}

    print(json.dumps(records, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
