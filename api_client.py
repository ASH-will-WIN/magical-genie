"""Thin wrapper over every HTTP call the Streamlit UI makes to the FastAPI
backend. Centralized so pages don't each hand-roll try/except around
`requests` -- every function here soft-fails (returns a dict with an
"error" key, or an empty list/None) instead of raising, per CLAUDE.md's
"failure is always soft" rule."""
import requests

API_BASE = "http://localhost:8000"


def run_campaign(url: str | None = None, manual_text: str | None = None) -> dict:
    try:
        resp = requests.post(
            f"{API_BASE}/campaign",
            json={"url": url, "manual_text": manual_text},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"error": f"Couldn't reach the backend. Is `uvicorn main:app --reload` running? ({e})"}


def get_campaign(campaign_id: int) -> dict | None:
    try:
        resp = requests.get(f"{API_BASE}/campaigns/{campaign_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def list_campaigns() -> list[dict]:
    try:
        resp = requests.get(f"{API_BASE}/campaigns", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except requests.RequestException:
        return []


def approve_candidate(campaign_id: int, candidate_id: int) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/campaigns/{campaign_id}/candidates/{candidate_id}/approve", timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"error": str(e)}


def reject_candidate(campaign_id: int, candidate_id: int) -> dict | None:
    try:
        resp = requests.post(
            f"{API_BASE}/campaigns/{campaign_id}/candidates/{candidate_id}/reject", timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"error": str(e)}


def health_keys() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/health/keys", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return {"openai": False, "apollo": False}