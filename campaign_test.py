"""
End-to-end test suite. Run with: python campaign_test.py
Requires uvicorn main:app running on localhost:8000 and a real .env configured.
"""
import sys

import requests

API_BASE = "http://localhost:8000"
TEST_URL = "https://www.reuters.com/business/healthcare-pharmaceuticals/"  # replace with a real article URL


def check(name, condition):
    status = "✅ PASS" if condition else "❌ FAIL"
    print(f"{status} — {name}")
    return condition


def test_health():
    r = requests.get(f"{API_BASE}/health", timeout=10)
    return check("Health check", r.status_code == 200 and r.json().get("status") == "ok")


def test_scrape():
    r = requests.post(f"{API_BASE}/scrape", json={"url": TEST_URL}, timeout=20)
    ok = r.status_code == 200
    return check("Scrape endpoint responds", ok)


def test_analyze():
    r = requests.post(f"{API_BASE}/analyze", json={"url": TEST_URL}, timeout=30)
    ok = r.status_code == 200 and "status" in r.json()
    return check("Analyze endpoint responds", ok)


def test_full_campaign():
    r = requests.post(f"{API_BASE}/campaign", json={"url": TEST_URL}, timeout=90)
    ok = r.status_code == 200 and "campaign_id" in r.json()
    if ok:
        global _campaign_id
        _campaign_id = r.json()["campaign_id"]
    return check("Full campaign end-to-end", ok)


def test_database_integrity():
    if not globals().get("_campaign_id"):
        return check("Database integrity (skipped, no campaign_id)", False)
    r = requests.get(f"{API_BASE}/campaigns/{_campaign_id}", timeout=10)
    return check("Database integrity", r.status_code == 200)


def test_click_logging():
    if not globals().get("_campaign_id"):
        return check("Click logging (skipped, no campaign_id)", False)
    r = requests.post(
        f"{API_BASE}/click",
        params={"campaign_id": _campaign_id, "apollo_id": "test123", "channel": "email"},
        timeout=10,
    )
    return check("Click logging (best-effort)", r.status_code == 200)


def test_list_campaigns():
    r = requests.get(f"{API_BASE}/campaigns", timeout=10)
    return check("List campaigns", r.status_code == 200 and isinstance(r.json(), list))


if __name__ == "__main__":
    print(f"Running against {TEST_URL} — replace with a real article URL for a meaningful run.\n")
    results = [
        test_health(),
        test_scrape(),
        test_analyze(),
        test_full_campaign(),
        test_database_integrity(),
        test_click_logging(),
        test_list_campaigns(),
    ]
    passed = sum(results)
    print(f"\n{passed}/{len(results)} tests passed")
    sys.exit(0 if passed == len(results) else 1)
