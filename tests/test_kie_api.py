import json

import pytest
import requests

from core import kie_api
from core.kie_api import ApiError, KieAPI, extract_image_url, read_task_state


# ----------------------------------------------------------------------
# extract_image_url
# ----------------------------------------------------------------------

def test_image_url_from_result_json_text():
    data = {"resultJson": json.dumps({"resultUrls": ["https://x/a.png", "https://x/b.png"]})}
    assert extract_image_url(data) == "https://x/a.png"


def test_image_url_from_result_json_dict():
    data = {"resultJson": {"resultImageUrl": "https://x/a.png"}}
    assert extract_image_url(data) == "https://x/a.png"


def test_image_url_from_list_of_objects():
    data = {"images": [{"url": "https://x/a.png"}]}
    assert extract_image_url(data) == "https://x/a.png"


def test_image_url_directly_on_data():
    assert extract_image_url({"imageUrl": "https://x/a.png"}) == "https://x/a.png"


def test_image_url_from_legacy_response_object():
    data = {"response": {"resultImageUrl": "https://x/a.png"}}
    assert extract_image_url(data) == "https://x/a.png"


def test_image_url_missing():
    assert extract_image_url({"resultJson": "kein json"}) is None
    assert extract_image_url({}) is None


# ----------------------------------------------------------------------
# read_task_state
# ----------------------------------------------------------------------

def test_state_success():
    state = read_task_state({"state": "SUCCESS"})
    assert state.is_finished and state.is_success
    assert state.raw_state == "success"


def test_state_failure_carries_message():
    state = read_task_state({"state": "fail", "failMsg": "NSFW"})
    assert state.is_finished and not state.is_success
    assert state.message == "NSFW"


def test_state_in_progress():
    state = read_task_state({"state": "generating"})
    assert not state.is_finished
    assert state.raw_state == "generating"


def test_state_legacy_success_flag():
    assert read_task_state({"successFlag": 0}).raw_state == "flag=0"
    assert read_task_state({"successFlag": 1}).is_success
    failed = read_task_state({"successFlag": 2, "errorMessage": "kaputt"})
    assert failed.is_finished and not failed.is_success and failed.message == "kaputt"


def test_state_without_state_but_with_url_counts_as_success():
    state = read_task_state({"resultUrls": ["https://x/a.png"]})
    assert state.is_finished and state.is_success


def test_state_empty_text_is_treated_as_no_state():
    assert read_task_state({"state": ""}).raw_state == "unknown"


def test_state_unknown():
    state = read_task_state({"irgendwas": 1})
    assert not state.is_finished
    assert state.raw_state == "unknown"


# ----------------------------------------------------------------------
# KieAPI mit nachgebauten HTTP-Antworten
# ----------------------------------------------------------------------

class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = json.dumps(body) if body is not None else "<html>"

    def json(self):
        if self._body is None:
            raise ValueError("kein JSON")
        return self._body


def make_api() -> KieAPI:
    return KieAPI("key", "https://api/create", "https://api/status", "https://api/credits")


def test_create_task_returns_task_id(monkeypatch):
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent["url"] = url
        sent["payload"] = json
        return FakeResponse({"code": 200, "data": {"taskId": "abc"}})

    monkeypatch.setattr(kie_api.requests, "post", fake_post)
    assert make_api().create_task("model-x", "https://cb", {"prompt": "p"}) == "abc"
    assert sent["payload"] == {"model": "model-x", "callBackUrl": "https://cb", "input": {"prompt": "p"}}


def test_create_task_api_error_code(monkeypatch):
    monkeypatch.setattr(
        kie_api.requests, "post",
        lambda *args, **kwargs: FakeResponse({"code": 402, "msg": "Credits aufgebraucht"}),
    )
    with pytest.raises(ApiError, match="Credits aufgebraucht"):
        make_api().create_task("m", "cb", {})


def test_create_task_network_error(monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(kie_api.requests, "post", fake_post)
    with pytest.raises(ApiError, match="Netzwerkfehler"):
        make_api().create_task("m", "cb", {})


def test_get_task_status_sends_task_id_and_returns_data(monkeypatch):
    sent = {}

    def fake_get(url, params, headers, timeout):
        sent["url"] = url
        sent["params"] = params
        return FakeResponse({"code": 200, "data": {"state": "waiting"}})

    monkeypatch.setattr(kie_api.requests, "get", fake_get)
    assert make_api().get_task_status("abc") == {"state": "waiting"}
    assert sent == {"url": "https://api/status", "params": {"taskId": "abc"}}


def test_get_task_status_http_error(monkeypatch):
    monkeypatch.setattr(
        kie_api.requests, "get",
        lambda *args, **kwargs: FakeResponse({"msg": "nicht gefunden"}, status_code=404),
    )
    with pytest.raises(ApiError, match="Status-Endpoint Fehler: nicht gefunden"):
        make_api().get_task_status("abc")


@pytest.mark.parametrize("body, expected", [
    ({"data": 12.5}, 12.5),
    ({"data": {"credits": 7}}, 7.0),
    ({"data": None}, -1.0),
    ({"data": "abc"}, -1.0),
    (None, -1.0),
])
def test_get_account_credits(monkeypatch, body, expected):
    monkeypatch.setattr(kie_api.requests, "get", lambda *args, **kwargs: FakeResponse(body))
    assert make_api().get_account_credits() == expected
