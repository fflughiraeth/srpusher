#!./venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

import unittest
import json
import datetime
import dateutil.parser
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
    __sr_status = None

    @classmethod
    def setUpClass(cls):
        cls.s = SRPusher(configfilename="settings_test.yml", dry_run=True)
        cls.s.redis.flushdb()
        cls.key_members_previous= "_test" + cls.s.key_members_previous
        cls.key_members = "_test" + cls.s.key_members


    def test_instance(self):
        """ read config """
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
        if self.__sr_status is None:
            try:
                self.__sr_status = json.loads(base64.b64decode(self.testapidata[1:-1]).decode('utf-8'))
            except:
                raise
                with open("tests.json", "r") as fp:
                    self.__sr_status = json.load(fp)
        return self.__sr_status

    def _sr_status_reload(self):
        self.__sr_status = None

    def test_sr_status_json(self):
        """ test mock api data """
        self.assertIs(type(self._sr_status), dict)
        self.assertIn("rooms", self._sr_status)
        self.assertIn("members", self._sr_status["rooms"][0])

    def test_check_keyword(self):
        """ keywords """
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


    def test_fetch_real_webapi(self):
        """ fetch real data, this needs internet connection """
        self.assertIs(type(self.s.sr_status["rooms"]), list)
        self.assertIs(type(self.s.sr_status["rooms"][0]), dict)
        self.assertIs(type(self.s.sr_status["rooms"][0]["index"]), int)
        self.assertIs(type(self.s.sr_status["rooms"][0]["realm"]), int)
        self.assertIs(type(self.s.sr_status["rooms"][0]["needPasswd"]), bool)
        self.assertIs(type(self.s.sr_status["rooms"][0]["roomName"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["roomDesc"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["numMembers"]), int)
        self.assertIs(type(self.s.sr_status["rooms"][0]["tagMask"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["tagOrig"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["createTime"]), str)
        self.assertIs(type(dateutil.parser.parse(self.s.sr_status["rooms"][0]["createTime"])), datetime.datetime)
        self.assertIs(type(self.s.sr_status["rooms"][0]["roomAttribute"]), dict)
        self.assertIs(type(self.s.sr_status["rooms"][0]["roomAttribute"]["language"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["members"]), list)
        self.assertIs(type(self.s.sr_status["rooms"][0]["members"][0]), dict)
        self.assertIs(type(self.s.sr_status["rooms"][0]["members"][0]["userId"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["members"][0]["nickname"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["members"][0]["nsgmMemberId"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["members"][0]["iconInfo"]), dict)
        self.assertIs(type(self.s.sr_status["rooms"][0]["creator"]), dict)
        self.assertIs(type(self.s.sr_status["rooms"][0]["creator"]["userId"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["creator"]["idProvider"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["creator"]["nickname"]), str)
        self.assertIs(type(self.s.sr_status["rooms"][0]["creator"]["nsgmMemberId"]), str)

    def reload_test_users_list(self) -> list:
        self.key_members_previous= "_test" + self.s.key_members_previous
        self.key_members = "_test" + self.s.key_members
        members = []
        members.append(self._sr_status["rooms"][0]["members"][0]["userId"])
        members.append(self._sr_status["rooms"][0]["members"][1]["userId"])
        members.append(self._sr_status["rooms"][0]["members"][2]["userId"])
        members.append(self._sr_status["rooms"][1]["members"][0]["userId"])
        members.append(self._sr_status["rooms"][1]["members"][1]["userId"])
        members.append(self._sr_status["rooms"][1]["members"][2]["userId"])
        members.append(self._sr_status["rooms"][1]["members"][3]["userId"])
        members.append(self._sr_status["rooms"][1]["members"][4]["userId"])
        self.s.set_users_status(self.key_members_previous, members)
        self.s.set_users_status(self.key_members, members)
        return members

    def test_users_status_diff(self):
        """ no diff users list """
        self.reload_test_users_list()
        diff = self.s.get_users_diff(self.key_members_previous, self.key_members)
        self.assertEqual(len(diff), 0)
        diff = self.s.get_users_diff(self.key_members, self.key_members_previous)
        self.assertEqual(len(diff), 0)

    def test_users_status_offlined(self):
        """ offlined users """
        user = "c9253f7e-6a84-4ceb-b1a8-f339e9a5b823"
        self.reload_test_users_list()
        # remove a user
        self.s.redis.srem(self.key_members, user)
        # the user is in offlined-list
        diff = self.s.get_users_diff(self.key_members_previous, self.key_members)
        self.assertTrue(user in diff)
        # onlined is 0
        diff = self.s.get_users_diff(self.key_members, self.key_members_previous)
        self.assertEqual(len(diff), 0)

    def test_users_status_onlined(self):
        """ onlined users """
        user = "0efffd95-7ce1-4d37-9a96-24406d0f70b4"
        self.reload_test_users_list()
        # add a user
        self.s.redis.sadd(self.key_members, user)
        # offlined is 0
        diff = self.s.get_users_diff(self.key_members_previous, self.key_members)
        self.assertEqual(len(diff), 0)
        # the user is in onlined-list
        diff = self.s.get_users_diff(self.key_members, self.key_members_previous)
        self.assertTrue(user in diff)

    def test_users_status_flush(self):
        """ replace previous user's list """
        members = self.reload_test_users_list()
        self.s.flush_users_status(self.key_members, self.key_members_previous)
        diff = self.s.get_users_diff(self.key_members, self.key_members_previous)
        self.assertEqual(len(diff), 0)  # no `key_members`
        diff = self.s.get_users_diff(self.key_members_previous, self.key_members)
        self.assertEqual(len(diff), len(members))

    def test_check_user_diff(self):
        members = self.reload_test_users_list()

    def test_wait_sec(self):
        user_count_changes_list = [20, 50, 70, 120, 200, 300, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, ]
        base_wait_sec = float(self.s.settings["sr"]["api_duration_sec"])
        prev_wait_sec = base_wait_sec
        self.assertAlmostEqual(base_wait_sec, 120)
        for users in user_count_changes_list:
            wait_sec = self.s.wait_sec(users)
            wait_sec = self.s.lpf(prev_wait_sec, wait_sec)
            self.assertGreater(wait_sec, 20)
            if users > 500:
                self.assertLess(wait_sec, 80)
            prev_wait_sec = wait_sec

    def test_lpf(self):
        a = self.s.lpf(5, 1, T=.1)
        self.assertLess(a, 5)
        self.assertGreater(a, 1)

if __name__ == "__main__":
    unittest.main()