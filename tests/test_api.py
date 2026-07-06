"""
API integration tests — covers POST /logs, GET /logs/{id}, GET /logs.
No Claude API calls; no LangGraph. Tests the HTTP layer + DB writes only.
"""

from datetime import date

BASE_LOG = {
    "entry_date": str(date.today()),
    "migraine_occurred": True,
    "pain_level": 7,
    "pain_location": "left temporal",
    "pain_quality": "throbbing",
    "duration_hours": 4.0,
    "foods": ["coffee", "cheese"],
    "sleep_hours": 5.5,
    "sleep_quality": 3,
    "stress_level": 8,
    "stress_source": "deadline",
    "notes": "rough morning",
}


def test_create_log_returns_201(client):
    resp = client.post("/logs/", json=BASE_LOG)
    assert resp.status_code == 201


def test_create_log_response_shape(client):
    resp = client.post("/logs/", json=BASE_LOG)
    body = resp.json()
    assert "log" in body
    assert "red_flag" in body
    assert "moh_alert" in body
    assert "triptan_days" in body
    assert body["log"]["pain_level"] == 7
    assert body["log"]["migraine_occurred"] is True


def test_create_log_persists_id(client):
    resp = client.post("/logs/", json=BASE_LOG)
    log_id = resp.json()["log"]["id"]
    assert isinstance(log_id, int)
    assert log_id >= 1


def test_get_log_by_id(client):
    create_resp = client.post("/logs/", json=BASE_LOG)
    log_id = create_resp.json()["log"]["id"]

    get_resp = client.get(f"/logs/{log_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == log_id
    assert get_resp.json()["pain_location"] == "left temporal"


def test_get_log_not_found(client):
    resp = client.get("/logs/9999")
    assert resp.status_code == 404


def test_list_logs_empty(client):
    resp = client.get("/logs/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_logs_returns_created(client):
    client.post("/logs/", json=BASE_LOG)
    resp = client.get("/logs/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_red_flag_not_triggered_on_normal_entry(client):
    resp = client.post("/logs/", json=BASE_LOG)
    assert resp.json()["red_flag"] is False
    assert resp.json()["red_flag_symptoms"] == []


def test_red_flag_triggered_on_thunderclap(client):
    payload = {**BASE_LOG, "notes": "worst headache of life, thunderclap onset"}
    resp = client.post("/logs/", json=payload)
    assert resp.json()["red_flag"] is True
    assert len(resp.json()["red_flag_symptoms"]) > 0


def test_moh_not_triggered_below_threshold(client):
    resp = client.post("/logs/", json=BASE_LOG)
    assert resp.json()["moh_alert"] is False


def test_log_entry_date_stored_correctly(client):
    payload = {**BASE_LOG, "entry_date": "2026-01-15"}
    resp = client.post("/logs/", json=payload)
    assert resp.json()["log"]["entry_date"] == "2026-01-15"
