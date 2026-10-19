"""Constants for the IO-Darts integration."""

from datetime import timedelta

DOMAIN = "io_darts"
MODULE_ID = "homeassistant"
MODULE_ROUTES = f"/api/modules/{MODULE_ID}/routes"
SESSION_COOKIE = "autodarts_session"
CONF_WEBHOOK_ID = "webhook_id"
POLL_INTERVAL = timedelta(seconds=30)
REQUEST_TIMEOUT = 10
EVENT_NAME = "io_darts_event"
INTENT_SLOTS = 5
PUSH_TYPES = {
    "state",
    "match_started",
    "match_finished",
    "match_cancelled",
    "match_closed",
    "leg_finished",
    "player_changed",
    "throw",
    "turn_finished",
    "cricket_closed",
}
TAGS = {"180", "bust", "bullseye", "bull", "triple", "double", "miss", "high_finish"}
