# kie_api.py
#
# Client für die kie.ai-kompatible Bild-API und das Auslesen ihrer Antworten.
# Die URLs kommen aus der config.ini und sind nicht fest im Code verdrahtet.

import json
from dataclasses import dataclass
from typing import Any

import requests

REQUEST_TIMEOUT_S = 60
CREDITS_TIMEOUT_S = 15

# Status-Texte, mit denen die APIs einen fertigen oder gescheiterten Task melden.
# Alles andere (waiting, queuing, generating, pending, running ...) heißt: weiter warten.
SUCCESS_STATES = ("success", "succeeded", "succeed", "completed", "complete", "done", "finished")
FAILURE_STATES = ("fail", "failed", "failure", "error")

# Unter diesen Schlüsseln kann die Bild-URL stehen — als Text, als Liste von
# Texten oder als Liste von Objekten mit "url"/"imageUrl".
IMAGE_URL_KEYS = (
    "resultUrls", "result_urls", "resultImageUrls", "resultImageUrl",
    "images", "urls", "imageUrl", "url",
)


class ApiError(Exception):
    """Die API hat mit einem Fehler geantwortet oder war nicht erreichbar."""


@dataclass
class TaskState:
    """Ausgewerteter Status eines Tasks."""
    is_finished: bool   # Task ist beendet (erfolgreich oder gescheitert)
    is_success: bool    # nur sinnvoll, wenn is_finished
    message: str        # Fehlermeldung bei gescheitertem Task
    raw_state: str      # erkannter Status als Text, für die Statusanzeige; "unknown" wenn keiner


class KieAPI:
    """Generischer kie.ai-kompatibler Client."""

    def __init__(self, api_key: str, generate_url: str, status_url: str, credits_url: str) -> None:
        self.api_key = api_key
        self.generate_url = generate_url
        self.status_url = status_url
        self.credits_url = credits_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def create_task(self, api_model: str, callback_url: str, input_payload: dict) -> str:
        """Legt einen Generierungs-Task an und gibt die taskId zurück."""
        payload = {
            "model":       api_model,
            "callBackUrl": callback_url,
            "input":       input_payload,
        }
        try:
            response = requests.post(
                self.generate_url, headers=self.headers, json=payload, timeout=REQUEST_TIMEOUT_S
            )
        except requests.RequestException as exc:
            raise ApiError(f"Netzwerkfehler beim Task-Erzeugen: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError(
                f"Ungültige Antwort vom Server ({response.status_code}): {response.text[:200]}"
            ) from exc

        if not response.ok:
            raise ApiError(_error_message(body, f"HTTP {response.status_code}"))
        code = body.get("code")
        if code is not None and code != 200:
            raise ApiError(_error_message(body, f"API-Fehlercode {code}"))

        task_id = (body.get("data") or {}).get("taskId")
        if not task_id:
            raise ApiError(f"Keine taskId in der Antwort: {response.text[:200]}")
        return task_id

    def get_task_status(self, task_id: str) -> dict:
        """Fragt den Status eines Tasks ab und gibt das "data"-Objekt der Antwort zurück."""
        try:
            response = requests.get(
                self.status_url,
                params={"taskId": task_id},
                headers=self.headers,
                timeout=REQUEST_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            raise ApiError(f"Netzwerkfehler beim Statusabruf: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise ApiError(
                f"Ungültige Statusantwort (HTTP {response.status_code}): {response.text[:200]}"
            ) from exc

        if not response.ok:
            message = _error_message(body, f"HTTP {response.status_code}")
            raise ApiError(f"Status-Endpoint Fehler: {message}")
        code = body.get("code")
        if code is not None and code != 200:
            message = _error_message(body, f"code {code}")
            raise ApiError(f"API-Fehler: {message}")

        return body.get("data") or {}

    def get_account_credits(self) -> float:
        """Guthaben des Kontos; -1.0, wenn die Antwort keinen Zahlenwert enthält."""
        response = requests.get(self.credits_url, headers=self.headers, timeout=CREDITS_TIMEOUT_S)
        try:
            body = response.json()
        except ValueError:
            return -1.0

        value = body.get("data")
        if isinstance(value, dict):
            value = value.get("credits") or value.get("balance") or value.get("amount")
        if value is None:
            return -1.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return -1.0


def _error_message(body: dict, fallback: str) -> str:
    """Fehlertext aus einer API-Antwort ("msg" oder "message")."""
    return body.get("msg") or body.get("message") or fallback


# ======================================================================
# Antworten auswerten
# ======================================================================

def extract_image_url(status_data: dict) -> str | None:
    """Sucht die Bild-URL in den verschiedenen Antwortformaten.

    Gesucht wird in dieser Reihenfolge:
      1. data.resultJson — bei kie.ai ein JSON-Text (manchmal schon ein dict)
         mit z.B. {"resultUrls": [...]}
      2. direkt im data-Objekt
      3. data.response — älteres nanobanana-Format
    """
    places_to_search: list[dict] = []

    result_json = status_data.get("resultJson")
    if isinstance(result_json, str) and result_json:
        try:
            result_json = json.loads(result_json)
        except ValueError:
            result_json = None
    if isinstance(result_json, dict):
        places_to_search.append(result_json)

    places_to_search.append(status_data)

    response = status_data.get("response")
    if isinstance(response, dict):
        places_to_search.append(response)

    for place in places_to_search:
        for key in IMAGE_URL_KEYS:
            url = _url_from_value(place.get(key))
            if url:
                return url
    return None


def _url_from_value(value: Any) -> str | None:
    """Macht aus "https://...", ["https://..."] oder [{"url": ...}] eine URL."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str) and first:
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("imageUrl")
    return None


def read_task_state(status_data: dict) -> TaskState:
    """Wertet das Status-Objekt eines Tasks aus."""
    # kie.ai: "state" / andere APIs: "status" / "taskStatus"
    state = (
        status_data.get("state")
        or status_data.get("status")
        or status_data.get("taskStatus")
    )
    state_text = str(state).lower() if state is not None else ""
    if state_text:
        if state_text in SUCCESS_STATES:
            return TaskState(True, True, "", state_text)
        if state_text in FAILURE_STATES:
            message = (
                status_data.get("failMsg")
                or status_data.get("failMessage")
                or status_data.get("errorMessage")
                or status_data.get("msg")
                or "Generierung fehlgeschlagen"
            )
            return TaskState(True, False, str(message), state_text)
        return TaskState(False, False, "", state_text)

    # Älteres nanobanana-Format: successFlag 0 = wartet, 1 = fertig, 2/3 = Fehler
    flag = status_data.get("successFlag")
    if flag == 1:
        return TaskState(True, True, "", "flag=1")
    if flag in (2, 3):
        message = status_data.get("errorMessage") or "Generierung fehlgeschlagen"
        return TaskState(True, False, str(message), f"flag={flag}")
    if flag == 0:
        return TaskState(False, False, "", "flag=0")

    # Kein Status, aber schon eine Bild-URL: manche APIs liefern das Bild
    # direkt ohne ausdrücklichen Status — das gilt als Erfolg.
    if extract_image_url(status_data):
        return TaskState(True, True, "", "no-state-but-url")

    return TaskState(False, False, "", "unknown")
