"""
Tests for dashboard.py — covers:
  • Emergency squawk detection (regression)
  • UAV squawk detection (new)
  • UAV category detection (new)
  • Combined is_uav flag logic (squawk + category)
  • Audio state-change detection logic (pure Python simulation)
"""

import sys
import os
import types
import unittest

# ---------------------------------------------------------------------------
# Minimal stubs so dashboard.py can be imported without Flask / paho / etc.
# ---------------------------------------------------------------------------

def _stub_module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod

# eventlet — needs monkey_patch() and nothing else here
_em = _stub_module("eventlet")
_em.monkey_patch = lambda: None

# flask
_flask = _stub_module("flask")
_flask.Flask = lambda *a, **kw: types.SimpleNamespace(route=lambda *a, **kw: (lambda f: f))
_flask.render_template_string = lambda t: t
_stub_module("flask_socketio", SocketIO=lambda *a, **kw: types.SimpleNamespace(
    emit=lambda *a, **kw: None,
    on=lambda *a, **kw: (lambda f: f),
    run=lambda *a, **kw: None,
))

# paho.mqtt
_mqtt_client = _stub_module("paho")
_mqtt = _stub_module("paho.mqtt")
_mqtt_client_mod = _stub_module("paho.mqtt.client")
_mqtt_client_mod.Client = lambda *a, **kw: types.SimpleNamespace(
    username_pw_set=lambda *a, **kw: None,
    tls_set=lambda *a, **kw: None,
    on_message=None,
    connect=lambda *a, **kw: None,
    subscribe=lambda *a, **kw: None,
    loop_start=lambda: None,
)

# ssl — only CERT_REQUIRED is used
import ssl as _ssl_real
_stub_module("ssl", CERT_REQUIRED=_ssl_real.CERT_REQUIRED)

# Make sure os.getenv returns empty strings for the env vars dashboard reads
os.environ.setdefault("MQTT_HOST", "localhost")
os.environ.setdefault("MQTT_PORT", "8883")
os.environ.setdefault("MQTT_USER", "")
os.environ.setdefault("MQTT_PASS", "")

# Now import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import importlib

# Patch open() for the password file so it raises OSError (no real file needed)
import builtins as _builtins
_real_open = _builtins.open

def _mock_open(path, *args, **kwargs):
    if "mqtt_secret" in str(path):
        raise OSError("test: no secret file")
    return _real_open(path, *args, **kwargs)

_builtins.open = _mock_open
import dashboard.dashboard as _dash
_builtins.open = _real_open


class TestEmergencySquawks(unittest.TestCase):
    """Regression: existing emergency-squawk detection must remain intact."""

    def test_standard_emergency_codes_present(self):
        self.assertIn("7500", _dash.EMERGENCY_SQUAWKS)  # hijack
        self.assertIn("7600", _dash.EMERGENCY_SQUAWKS)  # radio failure
        self.assertIn("7700", _dash.EMERGENCY_SQUAWKS)  # general emergency

    def test_non_emergency_squawk_not_detected(self):
        self.assertNotIn("1200", _dash.EMERGENCY_SQUAWKS)
        self.assertNotIn("0000", _dash.EMERGENCY_SQUAWKS)

    def test_emergency_flag_logic(self):
        for code in ("7500", "7600", "7700"):
            self.assertTrue(code in _dash.EMERGENCY_SQUAWKS)
        self.assertFalse("7400" in _dash.EMERGENCY_SQUAWKS)


class TestUavSquawks(unittest.TestCase):
    """UAV squawk-code detection."""

    def test_uav_squawk_set_exists(self):
        self.assertTrue(hasattr(_dash, "UAV_SQUAWKS"))
        self.assertIsInstance(_dash.UAV_SQUAWKS, set)

    def test_7400_is_uav_squawk(self):
        """7400 — UAS lost C2 link (ICAO Doc 10019)."""
        self.assertIn("7400", _dash.UAV_SQUAWKS)

    def test_emergency_codes_are_not_uav_codes(self):
        for code in _dash.EMERGENCY_SQUAWKS:
            self.assertNotIn(code, _dash.UAV_SQUAWKS,
                             msg=f"Emergency squawk {code} should not be in UAV_SQUAWKS")

    def test_normal_vfr_squawk_not_uav(self):
        self.assertNotIn("1200", _dash.UAV_SQUAWKS)
        self.assertNotIn("7000", _dash.UAV_SQUAWKS)


class TestUavCategoryDetection(unittest.TestCase):
    """ADS-B emitter-category based UAV detection."""

    def test_is_uav_category_function_exists(self):
        self.assertTrue(hasattr(_dash, "is_uav_category"))
        self.assertTrue(callable(_dash.is_uav_category))

    def test_b4_is_uav(self):
        self.assertTrue(_dash.is_uav_category("B4"))  # UAV/Drone

    def test_b6_is_uav(self):
        self.assertTrue(_dash.is_uav_category("B6"))  # UAV

    def test_b7_is_uav(self):
        self.assertTrue(_dash.is_uav_category("B7"))  # UAV

    def test_manned_categories_not_uav(self):
        for cat in ("A1", "A2", "A3", "A5", "A7", "B1", "B2", "B3", "C1"):
            self.assertFalse(_dash.is_uav_category(cat),
                             msg=f"Category {cat} should not be flagged as UAV")

    def test_none_and_empty_not_uav(self):
        self.assertFalse(_dash.is_uav_category(None))
        self.assertFalse(_dash.is_uav_category(""))


class TestUavFlagLogic(unittest.TestCase):
    """
    The 'uav' field on an aircraft entry should be True when EITHER the squawk
    OR the category indicates an unmanned aircraft.
    """

    def _compute_uav(self, squawk, category):
        """Mirror the entry.update(…) logic from on_message()."""
        return (
            (squawk in _dash.UAV_SQUAWKS if squawk else False)
            or _dash.is_uav_category(category)
        )

    def test_uav_squawk_triggers_flag(self):
        self.assertTrue(self._compute_uav("7400", None))

    def test_uav_category_triggers_flag(self):
        for cat in ("B4", "B6", "B7"):
            self.assertTrue(self._compute_uav(None, cat),
                            msg=f"Category {cat} should trigger UAV flag")

    def test_both_conditions_true(self):
        self.assertTrue(self._compute_uav("7400", "B4"))

    def test_neither_condition_false(self):
        self.assertFalse(self._compute_uav("1200", "A3"))
        self.assertFalse(self._compute_uav(None, None))
        self.assertFalse(self._compute_uav("7700", "A5"))

    def test_emergency_squawk_does_not_trigger_uav(self):
        """An emergency squawk must not be mistaken for a UAV squawk."""
        for code in _dash.EMERGENCY_SQUAWKS:
            self.assertFalse(self._compute_uav(code, "A3"),
                             msg=f"Emergency squawk {code} must not trigger UAV flag")


class TestAudioStateChangeLogic(unittest.TestCase):
    """
    Pure-Python simulation of the client-side audio state-change detection.

    The dashboard JS tracks ``acPrevState[hex] = {emergency, uav}`` and only
    calls speakAlert() when a flag transitions from False to True.  We replicate
    that logic here to verify correctness without a browser.
    """

    def _run_update(self, aircraft_list, prev_state):
        """
        Simulate one map_update cycle and return (alerts_fired, new_prev_state).

        aircraft_list: list of dicts with 'hex', 'emergency', 'uav', 'flight'
        prev_state:    dict hex → {emergency, uav}  (mutated in place)
        alerts:        list of spoken strings (returned)
        """
        alerts = []
        new_state = {}

        for ac in aircraft_list:
            hex_id   = ac["hex"]
            callsign = ac.get("flight") or hex_id.upper()
            is_emerg = bool(ac.get("emergency"))
            is_uav   = bool(ac.get("uav"))
            prev     = prev_state.get(hex_id, {})

            if is_emerg and not prev.get("emergency"):
                alerts.append(
                    "Emergency squawk {} {}".format(ac.get("squawk", "unknown"), callsign)
                )
            if is_uav and not prev.get("uav"):
                alerts.append("Unmanned aircraft {}".format(callsign))

            new_state[hex_id] = {"emergency": is_emerg, "uav": is_uav}

        prev_state.clear()
        prev_state.update(new_state)
        return alerts

    # ── Emergency callout tests ──────────────────────────────────────────────

    def test_emergency_first_detection_fires_alert(self):
        prev = {}
        alerts = self._run_update(
            [{"hex": "abc123", "emergency": True, "squawk": "7700", "uav": False}],
            prev
        )
        self.assertEqual(len(alerts), 1)
        self.assertIn("7700", alerts[0])
        self.assertIn("ABC123", alerts[0])

    def test_emergency_repeated_detection_no_alert(self):
        prev = {"abc123": {"emergency": True, "uav": False}}
        alerts = self._run_update(
            [{"hex": "abc123", "emergency": True, "squawk": "7700", "uav": False}],
            prev
        )
        self.assertEqual(len(alerts), 0, "No repeat alert for ongoing emergency")

    def test_emergency_cleared_then_reenters_fires_again(self):
        prev = {}
        # First detection
        self._run_update(
            [{"hex": "abc123", "emergency": True, "squawk": "7700", "uav": False}],
            prev
        )
        # Emergency clears
        self._run_update(
            [{"hex": "abc123", "emergency": False, "squawk": "1200", "uav": False}],
            prev
        )
        # Emergency re-enters
        alerts = self._run_update(
            [{"hex": "abc123", "emergency": True, "squawk": "7500", "uav": False}],
            prev
        )
        self.assertEqual(len(alerts), 1)
        self.assertIn("7500", alerts[0])

    # ── UAV callout tests ────────────────────────────────────────────────────

    def test_uav_first_detection_fires_alert(self):
        prev = {}
        alerts = self._run_update(
            [{"hex": "deadb4", "emergency": False, "uav": True, "flight": "DRONE1"}],
            prev
        )
        self.assertEqual(len(alerts), 1)
        self.assertIn("Unmanned", alerts[0])
        self.assertIn("DRONE1", alerts[0])

    def test_uav_repeated_detection_no_alert(self):
        prev = {"deadb4": {"emergency": False, "uav": True}}
        alerts = self._run_update(
            [{"hex": "deadb4", "emergency": False, "uav": True, "flight": "DRONE1"}],
            prev
        )
        self.assertEqual(len(alerts), 0)

    def test_uav_new_aircraft_fires_alert(self):
        prev = {}
        alerts = self._run_update(
            [
                {"hex": "111111", "emergency": False, "uav": False},
                {"hex": "222222", "emergency": False, "uav": True, "flight": "UAV01"},
            ],
            prev
        )
        self.assertEqual(len(alerts), 1)
        self.assertIn("UAV01", alerts[0])

    def test_both_emergency_and_uav_fires_two_alerts(self):
        prev = {}
        alerts = self._run_update(
            [{"hex": "aabbcc", "emergency": True, "squawk": "7700", "uav": True,
              "flight": "HYBRID1"}],
            prev
        )
        self.assertEqual(len(alerts), 2)
        topics = " ".join(alerts)
        self.assertIn("Emergency", topics)
        self.assertIn("Unmanned", topics)

    def test_normal_aircraft_no_alerts(self):
        prev = {}
        alerts = self._run_update(
            [{"hex": "cafe01", "emergency": False, "uav": False, "flight": "FIN123"}],
            prev
        )
        self.assertEqual(len(alerts), 0)

    def test_aircraft_leaving_state_cleans_prev(self):
        prev = {}
        # Appear as UAV
        self._run_update(
            [{"hex": "deadb6", "emergency": False, "uav": True}],
            prev
        )
        # Aircraft disappears (simulate server-side stale cleanup)
        del prev["deadb6"]
        # Aircraft reappears as UAV — should fire again
        alerts = self._run_update(
            [{"hex": "deadb6", "emergency": False, "uav": True, "flight": "REENTRY"}],
            prev
        )
        self.assertEqual(len(alerts), 1)
        self.assertIn("REENTRY", alerts[0])


if __name__ == "__main__":
    unittest.main()
