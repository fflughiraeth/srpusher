#!./venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

import unittest
import json
import os

from srpusher import (
        Config,
        SRPusher,
)

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.config._filename = "settings_test.yml"

    def test_config_defaults(self):
        self.assertAlmostEqual(self.config["global"]["verbose"], True)
        self.assertIsInstance(self.config["sr"]["targets"], list)

class TestSRPusher(unittest.TestCase):
    def setUp(self):
        self.s = SRPusher(dry_run=True)


