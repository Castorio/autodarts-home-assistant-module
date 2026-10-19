"""Translation files must stay free of ICU tag syntax and in sync.

Home Assistant's frontend renders these strings through an ICU message
parser. Any `<...>` substring is interpreted as an unclosed tag and breaks
the action/service editor with "Translation error: UNCLOSED_TAG".
"""

import json
from pathlib import Path

INTEGRATION_DIR = Path(__file__).parent.parent / "custom_components" / "io_darts"
STRINGS = json.loads((INTEGRATION_DIR / "strings.json").read_text(encoding="utf-8"))
EN = json.loads(
    (INTEGRATION_DIR / "translations" / "en.json").read_text(encoding="utf-8")
)
DE = json.loads(
    (INTEGRATION_DIR / "translations" / "de.json").read_text(encoding="utf-8")
)


def _iter_strings(value, path=()):
    """Yield (path, string) for every leaf string value in a nested dict."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_strings(child, path + (key,))
    elif isinstance(value, str):
        yield path, value


def test_strings_json_matches_en_translation():
    assert STRINGS == EN


def test_no_angle_brackets_in_strings_json():
    offenders = [
        (path, text) for path, text in _iter_strings(STRINGS) if "<" in text or ">" in text
    ]
    assert offenders == []


def test_no_angle_brackets_in_en_translation():
    offenders = [
        (path, text) for path, text in _iter_strings(EN) if "<" in text or ">" in text
    ]
    assert offenders == []


def test_no_angle_brackets_in_de_translation():
    offenders = [
        (path, text) for path, text in _iter_strings(DE) if "<" in text or ">" in text
    ]
    assert offenders == []
