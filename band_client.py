"""Thin, deterministic REST wrapper for Band control calls.

Used for the inspectable control plane (create room, add/remove/list
participants, read history) and for the Phase A acceptance tests. The LLM
agents use the SDK's thenvoi_* tools; this wrapper is for the plumbing we want
to be exact and debuggable.

Every path here was verified against https://docs.band.ai/api/agent-api .
Auth header is X-API-Key.
"""

import os
import httpx

REST_URL = os.getenv("THENVOI_REST_URL", "https://app.band.ai/").rstrip("/")
# The Agent REST API is served under /api/v1 (same prefix as the websocket).
API_PREFIX = "/api/v1"


class BandClient:
    def __init__(self, api_key: str, rest_url: str = REST_URL):
        self._http = httpx.Client(
            base_url=f"{rest_url}{API_PREFIX}",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    # --- identity ---------------------------------------------------------
    def me(self):
        return self._http.get("/agent/me").raise_for_status().json()

    # --- rooms ------------------------------------------------------------
    def create_chat(self, task_id: str | None = None):
        # Body must wrap fields in "chat"; an empty body 422s.
        chat = {"task_id": task_id} if task_id else {}
        return self._http.post("/agent/chats", json={"chat": chat}).raise_for_status().json()

    def get_chat(self, chat_id: str):
        return self._http.get(f"/agent/chats/{chat_id}").raise_for_status().json()

    # --- participants -----------------------------------------------------
    def list_participants(self, chat_id: str):
        return self._http.get(
            f"/agent/chats/{chat_id}/participants"
        ).raise_for_status().json()

    def add_participant(self, chat_id: str, participant_id: str):
        # participant_id is the target's Agent UUID (or a User UUID).
        return self._http.post(
            f"/agent/chats/{chat_id}/participants",
            json={"participant": {"participant_id": participant_id}},
        ).raise_for_status().json()

    def remove_participant(self, chat_id: str, participant_id: str):
        # Enforcer's hands. Room creator has authority over participants.
        resp = self._http.delete(f"/agent/chats/{chat_id}/participants/{participant_id}")
        resp.raise_for_status()
        return resp.status_code

    # --- messages & events ------------------------------------------------
    def send_message(self, chat_id: str, content: str, mentions: list[dict] | None = None):
        return self._http.post(
            f"/agent/chats/{chat_id}/messages",
            json={"message": {"content": content, "mentions": mentions or []}},
        ).raise_for_status().json()

    def post_event(self, chat_id: str, content: str, message_type: str, metadata: dict | None = None):
        return self._http.post(
            f"/agent/chats/{chat_id}/events",
            json={"event": {"content": content, "message_type": message_type, "metadata": metadata or {}}},
        ).raise_for_status().json()

    def context(self, chat_id: str):
        """Messages sent by this agent + messages mentioning it, chronological.
        This is Warden's mention-scoped audit view and the Investigator's trail."""
        return self._http.get(
            f"/agent/chats/{chat_id}/context"
        ).raise_for_status().json()

    def messages(self, chat_id: str, status: str | None = None):
        params = {"status": status} if status else None
        return self._http.get(
            f"/agent/chats/{chat_id}/messages", params=params
        ).raise_for_status().json()

    def peers(self, not_in_chat: str | None = None):
        params = {"not_in_chat": not_in_chat} if not_in_chat else None
        return self._http.get("/agent/peers", params=params).raise_for_status().json()
