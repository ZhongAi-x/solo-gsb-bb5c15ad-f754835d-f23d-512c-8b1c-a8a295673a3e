"""API 层测试（使用 FastAPI TestClient）。"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_align_endpoint():
    resp = client.post("/align", json={"left": "天?下", "right": "天下太?平"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 2
    assert data["merged_text"] == "天下"
    assert data["left_range"]["start"] == 2
    assert len(data["columns"]) == 2


def test_align_blank_returns_400():
    resp = client.post("/align", json={"left": "甲?", "right": "   "})
    assert resp.status_code == 400


def test_align_empty_returns_400():
    resp = client.post("/align", json={"left": "甲", "right": ""})
    assert resp.status_code == 400
    assert "非空" in resp.json()["detail"]


def test_align_without_question_returns_400_by_default():
    resp = client.post("/align", json={"left": "甲乙", "right": "甲丙"})
    assert resp.status_code == 400
    assert "?" in resp.json()["detail"]


def test_align_without_question_allowed_when_disabled():
    resp = client.post(
        "/align",
        json={"left": "甲乙", "right": "甲丙", "require_question": False},
    )
    assert resp.status_code == 200
    assert resp.json()["merged_text"] == "甲乙"


def test_align_missing_field_422():
    resp = client.post("/align", json={"left": "甲?"})
    assert resp.status_code == 422


def test_conflict_listing_end_to_end():
    # 强制构造异字冲突：左 "?甲乙" 与右 "?甲丙"，i=1 全列对齐
    # ?/? 0、甲/甲 +2、乙/丙 -2 = 0 分 3 对（异字保留左字 乙）
    resp = client.post("/align", json={"left": "?甲乙", "right": "?甲丙"})
    data = resp.json()
    assert data["score"] == 0
    assert data["merged_text"] == "?甲乙"
    assert data["conflicts"][0]["left_char"] == "乙"
    assert data["conflicts"][0]["right_char"] == "丙"
    assert len(data["unresolved_questions"]) == 1


def test_substitution_end_to_end():
    resp = client.post("/align", json={"left": "天?下", "right": "天下?太平"})
    data = resp.json()
    assert data["merged_text"] == "天下"
    assert data["substitutions"][0]["known_char"] == "天"
    assert data["substitutions"][0]["unknown_side"] == "left"
