#!./venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

import unittest
import json
import os
import base64

from srpusher import (
        Config,
        SRPusher,
)

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config._filename = "settings_test.yml"

    def test_config_defaults(self):
        self.assertTrue(self.config.settings["global"]["test"])


class TestSRPusher(unittest.TestCase):
    testapidata="""
eyJyb29tcyI6IFt7InJlYWxtIjogNCwgImluZGV4IjogMSwgInJvb21BdHRyaWJ1dGUiOiB7Imxhbmd1YWdlIjogImphIn0sICJyb29tTmFtZSI6ICJSb29tMSIsICJyb29tRGVzYyI6ICJEZXNjMSIsICJuZWVkUGFzc3dkIjogZmFsc2UsICJjcmVhdG9yIjogeyJ1c2VySWQiOiAiNzkzOWRlODYtNmM4My00OWRhLTllZDEtMDg1ODBkNzZiZGYzIiwgImlkUHJvdmlkZXIiOiAieW1pZC1qcCIsICJuaWNrbmFtZSI6ICJSeWFuIiwgIm5zZ21NZW1iZXJJZCI6ICIxMjU0NjEiLCAiaWNvbkluZm8iOiB7InByZXNldCI6ICIwIiwgInR5cGUiOiAicHJlc2V0IiwgInVybCI6ICIifSwgImZhdm9yaXRlIjogZmFsc2V9LCAibWVtYmVycyI6IFt7InVzZXJJZCI6ICI3OTM5ZGU4Ni02YzgzLTQ5ZGEtOWVkMS0wODU4MGQ3NmJkZjMiLCAibmlja25hbWUiOiAiUnlhbiIsICJuc2dtTWVtYmVySWQiOiAiMTI1NDYxIiwgImljb25JbmZvIjogeyJwcmVzZXQiOiAiMCIsICJ0eXBlIjogInByZXNldCIsICJ1cmwiOiAiIn0sICJmYXZvcml0ZSI6IGZhbHNlfSwgeyJ1c2VySWQiOiAiNGVlNzBkYTItNjU1Zi00YWY5LWEwOGUtYzIwM2RkMzdmZWEyIiwgIm5pY2tuYW1lIjogIkp1bGlvIiwgIm5zZ21NZW1iZXJJZCI6ICIxMjU1NDYiLCAiaWNvbkluZm8iOiB7InByZXNldCI6ICIzIiwgInR5cGUiOiAicHJlc2V0IiwgInVybCI6ICIifSwgImZhdm9yaXRlIjogZmFsc2V9LCB7InVzZXJJZCI6ICJiYTlmZGRjYi05YWJjLTQ5MjgtYjQxNy0xYmVjYjU4MDQ4NjIiLCAibmlja25hbWUiOiAiRGVsZ2FkaWxsbyIsICJuc2dtTWVtYmVySWQiOiAiMTI1NTQ5IiwgImljb25JbmZvIjogeyJwcmVzZXQiOiAiNiIsICJ0eXBlIjogInByZXNldCIsICJ1cmwiOiAiIn0sICJmYXZvcml0ZSI6IGZhbHNlfV0sICJudW1NZW1iZXJzIjogMywgInRhZ01hc2siOiAiMCIsICJ0YWdPcmlnIjogIiIsICJjcmVhdGVUaW1lIjogIjIwMjMtMTEtMTIgMTQ6MzY6MTEgR01UIn0sIHsicmVhbG0iOiA0LCAiaW5kZXgiOiAyLCAicm9vbUF0dHJpYnV0ZSI6IHsibGFuZ3VhZ2UiOiAiamEifSwgInJvb21OYW1lIjogIkQvTy9QL0UiLCAicm9vbURlc2MiOiAiU3RyZWV0IExpZmUiLCAibmVlZFBhc3N3ZCI6IHRydWUsICJjcmVhdG9yIjogeyJ1c2VySWQiOiAiOTAwMmI2OTUtNzJhZC00Y2Y2LTkwNzUtOWFiNTlhMmRmODBmIiwgImlkUHJvdmlkZXIiOiAieW1pZC1qcCIsICJuaWNrbmFtZSI6ICJFbnJcdTAwZWRxdWV6IiwgIm5zZ21NZW1iZXJJZCI6ICIxMjUwNTkiLCAiaWNvbkluZm8iOiB7InByZXNldCI6ICIzIiwgInR5cGUiOiAicHJlc2V0IiwgInVybCI6ICIifSwgImZhdm9yaXRlIjogZmFsc2V9LCAibWVtYmVycyI6IFt7InVzZXJJZCI6ICI5MDAyYjY5NS03MmFkLTRjZjYtOTA3NS05YWI1OWEyZGY4MGYiLCAibmlja25hbWUiOiAiRW5yXHUwMGVkcXVleiIsICJuc2dtTWVtYmVySWQiOiAiMTI1MDU5IiwgImljb25JbmZvIjogeyJwcmVzZXQiOiAiMyIsICJ0eXBlIjogInByZXNldCIsICJ1cmwiOiAiIn0sICJmYXZvcml0ZSI6IGZhbHNlfSwgeyJ1c2VySWQiOiAiN2U2YTM0NTQtYTk5Yi00YzY2LWI4ZDAtMTE4Mzg4ZmQwNGExIiwgIm5pY2tuYW1lIjogIlNhbnRhY3J1eiIsICJuc2dtTWVtYmVySWQiOiAiMTI1MDc0IiwgImljb25JbmZvIjogeyJwcmVzZXQiOiAiMCIsICJ0eXBlIjogInVybCIsICJ1cmwiOiAiaHR0cHM6Ly9leGFtcGxlLmNvbS8jLmpwZyJ9LCAiZmF2b3JpdGUiOiBmYWxzZX0sIHsidXNlcklkIjogIjVlMDBhM2FjLTM3NmQtNGJkYy1iY2ZmLWVlZjM4ZDI0ZTAyNSIsICJuaWNrbmFtZSI6ICJQZXJhbHRhIiwgIm5zZ21NZW1iZXJJZCI6ICIxMjUyMTQiLCAiaWNvbkluZm8iOiB7InByZXNldCI6ICIwIiwgInR5cGUiOiAidXJsIiwgInVybCI6ICJodHRwczovL2V4YW1wbGUuY29tLyMuanBnIn0sICJmYXZvcml0ZSI6IGZhbHNlfSwgeyJ1c2VySWQiOiAiYzkyNTNmN2UtNmE4NC00Y2ViLWIxYTgtZjMzOWU5YTViODIzIiwgIm5pY2tuYW1lIjogIlRcdTAwZjNycmV6IiwgIm5zZ21NZW1iZXJJZCI6ICIxMjUyNDMiLCAiaWNvbkluZm8iOiB7InByZXNldCI6ICIwIiwgInR5cGUiOiAidXJsIiwgInVybCI6ICJodHRwczovL2V4YW1wbGUuY29tLyMuanBnIn0sICJmYXZvcml0ZSI6IGZhbHNlfSwgeyJ1c2VySWQiOiAiMDczNWVmNzMtZTE4NC00M2E1LWJhMDctZGZhNjYyZDE5NGZlIiwgIm5pY2tuYW1lIjogIkVjaGV2YXJyXHUwMGVkYSIsICJuc2dtTWVtYmVySWQiOiAiMTI1NTE4IiwgImljb25JbmZvIjogeyJwcmVzZXQiOiAiMiIsICJ0eXBlIjogInVybCIsICJ1cmwiOiAiaHR0cHM6Ly9leGFtcGxlLmNvbS8jLmpwZyJ9LCAiZmF2b3JpdGUiOiBmYWxzZX1dLCAibnVtTWVtYmVycyI6IDUsICJ0YWdNYXNrIjogIjAiLCAidGFnT3JpZyI6ICJIaXBIb3AiLCAiY3JlYXRlVGltZSI6ICIyMDIzLTExLTEyIDEzOjQ1OjEyIEdNVCJ9LCB7InJlYWxtIjogNCwgImluZGV4IjogMywgInJvb21BdHRyaWJ1dGUiOiB7Imxhbmd1YWdlIjogImphIn0sICJyb29tTmFtZSI6ICJPZmZpY2lhbCBUZXN0IFJvb20iLCAicm9vbURlc2MiOiAiIiwgIm5lZWRQYXNzd2QiOiBmYWxzZSwgImNyZWF0b3IiOiB7InVzZXJJZCI6ICIiLCAiaWRQcm92aWRlciI6ICIiLCAibmlja25hbWUiOiAiU1IgYm90IiwgIm5zZ21NZW1iZXJJZCI6ICIxMjMwMDgiLCAiZmF2b3JpdGUiOiBmYWxzZX0sICJtZW1iZXJzIjogW3sidXNlcklkIjogIiIsICJuaWNrbmFtZSI6ICJTUiBib3QiLCAibnNnbU1lbWJlcklkIjogIjEyMzAwOCIsICJpY29uSW5mbyI6IHt9LCAiZmF2b3JpdGUiOiBmYWxzZX1dLCAibnVtTWVtYmVycyI6IDEsICJ0YWdNYXNrIjogIjAiLCAidGFnT3JpZyI6ICIiLCAiY3JlYXRlVGltZSI6ICIyMDIzLTExLTEyIDEwOjM0OjI0IEdNVCJ9XSwgInRvdGFsUHVibGlzaGVkUm9vbXMiOiAzLCAidG90YWxVbnB1Ymxpc2hlZFJvb21zIjogMTB9
"""
    _previous_sr_status = None

    def setUp(self):
        self.s = SRPusher(configfilename="settings_test.yml", dry_run=True)
        self.s.redis.flushdb()

    def test_instance(self):
        self.assertIsInstance(self.s, SRPusher)
        self.assertIsInstance(self.s.settings["sr"]["api_url"], str)
        self.assertIsInstance(self.s.settings["sr"]["targets"], list)
        self.assertIsInstance(self.s.settings["sr"]["targets_exclude"], list)
        self.assertIsInstance(self.s.settings["sr"]["target_keywords"], list)
        self.assertIsInstance(self.s.settings["sr"]["target_keywords_exclude"], list)
        self.assertIsInstance(self.s.settings["global"]["verbose"], bool)
        self.assertIsInstance(self.s.settings["pushover"]["user_key"], str)
        self.assertIsInstance(self.s.settings["pushover"]["api_token"], str)
        self.assertIsInstance(self.s.settings["redis"]["host"], str)
        self.assertIsInstance(self.s.settings["redis"]["port"], int)
        self.assertIsInstance(self.s.settings["redis"]["db"], int)

    @property
    def _sr_status(self):
        if self._previous_sr_status is None:
            try:
                self._previous_sr_status = json.loads(base64.b64decode(self.testapidata[1:-1]).decode('utf-8'))
            except:
                raise
                with open("tests.json", "r") as fp:
                    self._previous_sr_status = json.load(fp)
        return self._previous_sr_status

    def _sr_status_reload(self):
        self._previous_sr_status = None

    def test_sr_status_json(self):
        self.assertIn("rooms", self._sr_status)

    def test_check_keyword(self):
        self.assertFalse(self.s.check_keyword(""))
        self.assertFalse(self.s.check_keyword("", members=self._sr_status["rooms"][1]["members"]))

        # positive keyword
        self.assertTrue(self.s.check_keyword("Street Life", members=self._sr_status["rooms"][1]["members"]))
        self.assertFalse(self.s.check_keyword("__NON_KEYWORD__", members=self._sr_status["rooms"][1]["members"]))

        # negative keyword
        self.assertFalse(self.s.check_keyword("Street Life", "ZqsAk6lINEGATIVEKEYWORD_ONE_", members=self._sr_status["rooms"][1]["members"]))
        self.assertFalse(self.s.check_keyword("__NON_KEYWORD__", "ZqsAk6lINEGATIVEKEYWORD_ONE_", members=self._sr_status["rooms"][1]["members"]))

        # negative user
        self.s.settings["sr"]["targets_exclude"].append("5e00a3ac-376d-4bdc-bcff-eef38d24e025")
        self.assertFalse(self.s.check_keyword("Street Life", members=self._sr_status["rooms"][1]["members"]))
        self._sr_status_reload()


if __name__ == "__main__":
    unittest.main()
