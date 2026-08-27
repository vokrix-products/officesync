import os, json, time, requests
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
PRODUCT_ID = os.environ["PRODUCT_ID"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json"
}
NOTIFY_URL = "https://njyvnmczoydsaewvfhyq.supabase.co/rest/v1/notifications"

def download_file(bucket, file_path):
    if file_path.startswith(bucket + "/"):
        file_path = file_path[len(bucket) + 1:]
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{file_path}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}", "apikey": SUPABASE_SERVICE_KEY})
    resp.raise_for_status()
    return resp.content

def notify(customer_id, success):
    try:
        requests.post(
            NOTIFY_URL,
            headers=HEADERS,
            json={
                "product_id": PRODUCT_ID,
                "customer_id": customer_id,
                "title": "Processing complete" if success else "Processing failed",
                "body": "Your upload has been processed successfully." if success else "There was an error processing your upload.",
                "type": "success" if success else "error",
                "read": False
            },
            timeout=10
        )
    except Exception:
        pass

def poll():
    while True:
        try:
            params = {
                "select": "*",
                "status": "eq.pending",
                "job_type": "eq.process_upload",
                "product_id": f"eq.{PRODUCT_ID}",
                "order": "created_at.asc"
            }
            jobs_resp = requests.get(f"{SUPABASE_URL}/rest/v1/jobs", headers=HEADERS, params=params)
            jobs_resp.raise_for_status()
            jobs = jobs_resp.json()

            for job in jobs:
                job_id = job["id"]
                customer_id = job["customer_id"]
                input_file_path = job["input_file_path"]
                try:
                    print(f"Processing job {job_id}")
                    file_bytes = download_file("uploads", input_file_path)

                    import processor
                    result = processor.process_file(file_bytes)

                    if isinstance(result, list):
                        records = result
                        summary = "Processed successfully"
                    elif isinstance(result, dict):
                        records = result.get("records", [])
                        summary = result.get("summary", "Processed successfully")
                    else:
                        records = []
                        summary = "No structured records returned"

                    for rec in records:
                        record_payload = {
                            "product_id": PRODUCT_ID,
                            "customer_id": customer_id,
                            "title": rec.get("title", "Untitled"),
                            "status": rec.get("status", "missing:critical"),
                            "details": rec.get("details", {}),
                            "source_file_path": input_file_path,
                            "due_date": rec.get("due_date")
                        }
                        r = requests.post(
                            f"{SUPABASE_URL}/rest/v1/records",
                            headers=HEADERS,
                            json=record_payload
                        )
                        r.raise_for_status()

                    result_json = json.dumps({"summary": summary, "records": [r.get("title", "Untitled") for r in records]})
                    result_path = f"results/{job_id}.json"
                    r = requests.post(
                        f"{SUPABASE_URL}/storage/v1/object/results/{result_path}",
                        headers={
                            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                            "apikey": SUPABASE_SERVICE_KEY,
                            "Content-Type": "application/json",
                            "x-upsert": "true"
                        },
                        data=result_json
                    )
                    r.raise_for_status()

                    completed_at = datetime.now(timezone.utc).isoformat()
                    update_payload = {
                        "status": "completed",
                        "output_file_path": result_path,
                        "result_summary": summary,
                        "completed_at": completed_at
                    }
                    r = requests.patch(
                        f"{SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}",
                        headers=HEADERS,
                        json=update_payload
                    )
                    r.raise_for_status()
                    notify(customer_id, True)

                except Exception as e:
                    print(f"Failed job {job_id}: {e}")
                    completed_at = datetime.now(timezone.utc).isoformat()
                    update_payload = {
                        "status": "failed",
                        "output_file_path": None,
                        "result_summary": str(e),
                        "completed_at": completed_at
                    }
                    try:
                        r = requests.patch(
                            f"{SUPABASE_URL}/rest/v1/jobs?id=eq.{job_id}",
                            headers=HEADERS,
                            json=update_payload
                        )
                        r.raise_for_status()
                    except Exception:
                        pass
                    notify(customer_id, False)

            time.sleep(60)
        except Exception as e:
            print(f"Poller loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("Poller started")
    poll()
