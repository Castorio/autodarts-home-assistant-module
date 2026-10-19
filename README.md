# Autodarts Home Assistant Module

Connects an [Autodarts](https://autodarts.io) board to Home Assistant, via
[IO-Darts-Agent](https://github.com/Castorio/io-darts-agent).

Two parts in this repository:

- **Hub module `homeassistant`** (`src/`, Node/TypeScript): runs inside IO-Darts-Agent, turns match
  events into a small push payload, and forwards it to a webhook on Home Assistant. It also exposes
  a service for Home Assistant to trigger hub intents.
- **Home Assistant integration `io_darts`** (`custom_components/io_darts/`, Python): adds an
  "IO-Darts Board" device with sensors for the board, the hub and the current match, plus buttons,
  switches, device triggers and an event for automations.

Status: both parts are implemented and tested, developed on a feature branch. Neither is published
to a module registry or the HACS default store yet — install manually as described below.

## Installation

### Hub module (`homeassistant`)

Install it on the hub directly from this repository:

- Hub UI → Modules → "Install from Git" → URL `https://github.com/Castorio/autodarts-home-assistant-module.git`

or via the hub API:

```bash
curl -X POST http://<hub>/api/modules/install \
  -H "Content-Type: application/json" \
  -d '{ "source": "git", "url": "https://github.com/Castorio/autodarts-home-assistant-module.git" }'
```

Then start the module from the hub UI (or `POST /api/modules/homeassistant/start`).

Optional module config:

- `allowedHosts` — comma-separated host names or IPs the webhook registration may point to. Empty
  (default) allows any host; set it to restrict the module to your Home Assistant host.

### Home Assistant integration (`io_darts`)

Via [HACS](https://hacs.xyz/):

1. HACS → the three-dot menu → Custom repositories → add
   `https://github.com/Castorio/autodarts-home-assistant-module`, category "Integration".
2. Install "IO-Darts" from HACS and restart Home Assistant if prompted.
3. Settings → Devices & Services → Add Integration → search "IO-Darts" → enter the hub URL (e.g.
   `http://192.168.41.108:3000`) and, only if web login is enabled on the hub, a username and
   password.

Home Assistant needs an internal URL that the board PC can reach: Settings → System → Network →
Home Assistant URL → Internal URL. The integration registers a local-only webhook at that address
for the hub module to push match events to; without a reachable internal URL, setup fails with
"Home Assistant has no internal URL the hub can reach".

## Entities

Device: **IO-Darts Board**. Entity IDs below follow the device name, e.g.
`sensor.io_darts_board_current_player`.

### Sensors

| Entity          | Description                                                                      |
| --------------- | --------------------------------------------------------------------------------- |
| current_player  | Name of the current player. Attribute `players`: list of `{name, score, legs_won, sets_won}` for all players in the match. |
| current_score   | Remaining score of the current player.                                            |
| last_throw      | Last recorded throw, e.g. `T20`.                                                   |
| last_turn       | Points scored in the last finished turn.                                          |
| game_variant    | Variant name as reported by the hub, e.g. `X01` or `Cricket`.                     |
| round           | Current round number.                                                             |
| hub_version     | IO-Darts-Agent version (diagnostic).                                              |
| hub_started     | Time the hub was started (timestamp, to the minute; diagnostic).                  |
| running_modules | Number of hub modules currently running (diagnostic).                            |
| current_player_color | Hex color (`#rrggbb`) of the current player. Attribute `rgb_color`: `[r, g, b]` list for use in `light.turn_on`. Keeps the last known color after the match ends. |
| next_player_color    | Hex color (`#rrggbb`) of the next player. Same `rgb_color` attribute and persistence as above. |

### Binary sensors

| Entity                | Description                                                              |
| ---------------------- | ------------------------------------------------------------------------- |
| match_active           | On while a match is running.                                              |
| autodarts_connected    | On while the hub is connected to Autodarts (connectivity device class).  |
| hub_reachable          | On while the hub responds to polling. Stays available even when the hub is unreachable, so it can report "off" (connectivity device class). |

### Switches and buttons

One switch and one restart button are created per hub module except `homeassistant` itself (e.g.
WLED, darts-caller):

- Switch "`<module name>`" — on while the module is running; turning it on/off starts/stops the
  module on the hub.
- Button "Restart `<module name>`" — restarts the module.

Fixed buttons:

| Entity               | Description                                   |
| --------------------- | ---------------------------------------------- |
| connect_autodarts     | Tells the hub to connect to Autodarts.         |
| disconnect_autodarts  | Tells the hub to disconnect from Autodarts.    |
| restart_hub           | Restarts IO-Darts-Agent itself.                |

## Event: `io_darts_event`

Every push except plain state updates fires `io_darts_event` on the Home Assistant event bus, with
`device_id` (the IO-Darts Board device), `type` and `tags` (e.g. `180`, `bust`, `bullseye`, `bull`,
`triple`, `double`, `miss`, `high_finish`) always present, plus per-`type` fields:

| type                 | Fields                                                            |
| -------------------- | ------------------------------------------------------------------ |
| player_changed       | playerName, playerIndex, remaining, playerColor, nextPlayerColor  |
| throw                | segment, number, multiplier, points, turnPoints, busted            |
| turn_finished        | playerName, playerIndex, turnScore, remaining, busted, round        |
| leg_finished         | winnerName, winnerPlayerIndex, leg, set                             |
| match_finished       | winnerName, winnerPlayerIndex                                      |
| match_started        | matchId                                                            |
| match_cancelled      | matchId                                                            |
| match_closed         | matchId                                                            |
| cricket_closed       | field, playerName, playerIndex                                    |

### Device triggers

The `io_darts` device also offers these device triggers (Settings → Automations → trigger → Device,
select "IO-Darts Board"):

- Match started
- Match won
- Leg won
- Player changed
- Dart thrown
- 180 thrown
- Bust
- Bullseye hit
- Triple hit
- High finish (100+)
- Cricket field closed

## Intents

Action `io_darts.trigger_intent`:

| Field           | Description                                        |
| --------------- | --------------------------------------------------- |
| slot            | Required, integer 1 to 5.                            |
| data            | Optional string, max. 200 characters.                |
| config_entry_id | Optional; only needed with more than one hub set up. |

Calling it emits `homeassistant.trigger_<slot>` as a hub intent. On the hub, open another module
(e.g. WLED or darts-caller) and under its intent subscriptions map `homeassistant.trigger_<n>` to
an action.

## Example automations

Announce the next player, using the `playerName` from a `player_changed` event:

```yaml
automation:
  - alias: "Darts: announce next player"
    triggers:
      - trigger: event
        event_type: io_darts_event
        event_data:
          type: player_changed
    actions:
      - action: tts.cloud_say # replace with your TTS service and target
        data:
          message: "It's {{ trigger.event.data.playerName }}'s turn"
```

Flash a light on a 180, using the `throw_180` device trigger (replace `device_id` with the actual
IO-Darts Board device id from Settings → Devices & Services):

```yaml
automation:
  - alias: "Darts: 180 flash"
    triggers:
      - trigger: device
        domain: io_darts
        device_id: <io_darts_board_device_id>
        type: throw_180
    actions:
      - action: light.turn_on
        target:
          entity_id: light.living_room
        data:
          flash: long
```

Trigger a hub intent from Home Assistant, e.g. from a script or another automation:

```yaml
actions:
  - action: io_darts.trigger_intent
    data:
      slot: 1
```

Dart light follows the current player:

```yaml
alias: Dart light follows the current player
triggers:
  - trigger: state
    entity_id: sensor.io_darts_board_current_player_color
actions:
  - action: light.turn_on
    target:
      entity_id: light.dart_light
    data:
      rgb_color: "{{ state_attr('sensor.io_darts_board_current_player_color', 'rgb_color') }}"
```

## Security

- The webhook the integration registers is `local_only`: Home Assistant rejects pushes that arrive
  through remote access (e.g. Nabu Casa), only the local network can reach it.
- Hub login (if enabled) is session-based via a cookie; credentials are only used against the hub's
  own login endpoint and stored by Home Assistant's config entry storage, not in this repository.
- The hub module needs no separate credentials; its routes are gated by the hub's own session
  authentication like any other module route.
- Intent payloads are bounded: 5 fixed slots, optional `data` capped at 200 characters.

## Development

Hub module (Node/TypeScript):

```bash
npm install
npm test
npm run build
```

Home Assistant integration (Python):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```
