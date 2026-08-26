import os

from processor import process_file

CSV_BYTES = b"""desk_id,floor,employee_name,department,assigned_permanent_desk
D1,1,Jane Doe,Marketing,true
"""


def test_process_csv():
    os.environ.pop("DEEPSEEK_API_KEY", None)

    records = process_file(CSV_BYTES)

    assert isinstance(records, list)
    assert records

    for rec in records:
        assert set(rec) == {"title", "status", "details", "due_date"}
        assert rec["title"] == "Jane Doe"
        assert rec["status"] in {
            "available:good",
            "valid:good",
            "expired:warning",
            "no_show:critical",
            "missing:critical",
            "flagged:critical",
            "maintenance_cleaning:warning",
            "over_capacity:critical",
        }
        assert isinstance(rec["details"], dict)
        assert "due_date" in rec

    assert records[0]["details"]["desk_id"] == "D1"


def test_empty_bytes():
    os.environ.pop("DEEPSEEK_API_KEY", None)
    assert process_file(b"") == []


if __name__ == "__main__":
    test_process_csv()
    test_empty_bytes()
    print("tests passed")
