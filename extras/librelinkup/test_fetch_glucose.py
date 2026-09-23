from __future__ import annotations

import copy
import unittest

from extras.librelinkup.fetch_glucose import normalize_alarm_thresholds


class AlarmThresholdCompatibilityTests(unittest.TestCase):
    def test_normalizes_fractional_alarm_thresholds_only(self):
        payload = {
            "data": {
                "connection": {
                    "alarmRules": {
                        "f": {"th": 70},
                        "l": {"th": 59.4, "thmm": 3.3},
                        "h": {"th": 250.2},
                    },
                    "glucoseMeasurement": {"Value": 4.2},
                },
                "graphData": [{"Value": 5.7}],
            }
        }

        result = normalize_alarm_thresholds(copy.deepcopy(payload))

        self.assertEqual(result["data"]["connection"]["alarmRules"]["f"]["th"], 70)
        self.assertEqual(result["data"]["connection"]["alarmRules"]["l"]["th"], 59)
        self.assertEqual(result["data"]["connection"]["alarmRules"]["h"]["th"], 250)
        self.assertEqual(result["data"]["connection"]["glucoseMeasurement"]["Value"], 4.2)
        self.assertEqual(result["data"]["graphData"][0]["Value"], 5.7)

    def test_ignores_unrelated_payloads(self):
        payload = {"data": [{"Value": 5.7}]}
        self.assertIs(normalize_alarm_thresholds(payload), payload)

class SessionTests(unittest.TestCase):
    def test_cached_session_skips_login(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from extras.librelinkup import fetch_glucose as fetch
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'session.json'
            fetch.write_state(state, {'token': 'fictional-token', 'account_id_hash': 'fictional-hash'})
            with patch.object(fetch, 'PyLibreLinkUp') as client, patch.object(fetch, 'authenticate') as login:
                result = fetch.build_client('example@example.com', 'unused', fetch.APIUrl.EU, state)
                self.assertIs(result, client.return_value)
                login.assert_not_called()
                client.return_value.get_patients.assert_called_once()
            self.assertEqual(state.stat().st_mode & 0o777, 0o600)

    def test_backoff_skips_network_login(self):
        import tempfile
        import time
        from pathlib import Path
        from unittest.mock import patch
        from extras.librelinkup import fetch_glucose as fetch
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / 'session.json'
            fetch.write_state(state, {'login_blocked_until': time.time() + 3600})
            with patch.object(fetch, 'authenticate') as login:
                with self.assertRaises(SystemExit) as raised:
                    fetch.build_client('example@example.com', 'unused', fetch.APIUrl.EU, state)
                self.assertEqual(raised.exception.code, 0)
                login.assert_not_called()

    def test_multiple_connections_require_selection(self):
        from unittest.mock import Mock
        from extras.librelinkup.fetch_glucose import pick_patient
        client = Mock()
        client.get_patients.return_value = [Mock(), Mock()]
        with self.assertRaises(SystemExit):
            pick_patient(client, None, None)
        self.assertIs(pick_patient(client, None, 1), client.get_patients.return_value[1])


if __name__ == "__main__":
    unittest.main()
