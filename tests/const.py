"""Shared test data."""

URL = "http://hub.local:3000"
WEBHOOK_ID = "a" * 32
ENTRY_DATA = {"url": URL, "username": "admin", "password": "pw", "webhook_id": WEBHOOK_ID}

STATUS = {
    "version": "1.2.0",
    "uptime": 3600,
    "setupCompleted": True,
    "autodarts": {"connected": True, "boardId": "board-123"},
    "modules": {"total": 3, "running": 2},
}

MODULES = [
    {"id": "wled", "name": "WLED Lighting Controller", "version": "1.3.0", "description": "", "status": "running", "events": []},
    {"id": "darts-caller", "name": "Darts Caller", "version": "1.0.0", "description": "", "status": "stopped", "events": []},
    {"id": "homeassistant", "name": "Home Assistant", "version": "0.1.0", "description": "", "status": "running", "events": []},
]

PLAYER_ALICE = {"index": 0, "name": "Alice", "score": 301, "legsWon": 1, "setsWon": 0, "color": "#3b82f6"}
PLAYER_BOB = {"index": 1, "name": "Bob", "score": 241, "legsWon": 0, "setsWon": 0, "color": "#ef4444"}

MATCH = {
    "active": True,
    "matchId": "m1",
    "variant": "X01",
    "mode": "x01",
    "round": 3,
    "currentPlayer": PLAYER_BOB,
    "players": [PLAYER_ALICE, PLAYER_BOB],
    "lastThrow": "T20",
    "lastTurnPoints": 100,
    "winnerName": None,
    "currentPlayerColor": "#ef4444",
    "nextPlayerColor": "#3b82f6",
}


def routes(path: str) -> str:
    """URL of a module route."""
    return f"{URL}/api/modules/homeassistant/routes{path}"
