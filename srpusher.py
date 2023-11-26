#! venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

import os
import sys
import argparse
import json
import yaml
import requests
import codecs
import datetime
import time
import random
import redis
import dateutil.parser
import pushover
import hashlib
import logging
import rich.logging
import importlib
import pkgutil




class Config(object):
    """ Read configration from a file """
    _filename = "settings.yml"
    _settings = None

    @property
    def settings(self):
        if self._settings is None:
            with open(self._filename, "r") as fp:
                self._settings = yaml.safe_load(fp)
        return self._settings


class SRPusher(Config):
    redis = None
    pushover = None
    debug = False
    header_channel = "__channel__"
    header_usercache = "__usercache__"
    header_keyword = "__keyword__"
    header_roomcache = "__roomcache__"
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    key_members = "members"
    key_members_previous = "members_prev"
    _previous_sr_status_epoch = 0
    _previous_sr_status = None
    _plugins = []

    def __init__(self, dry_run=False, configfilename="settings.yml") -> None:
        self._filename = configfilename
        if 'debug' in self.settings['global'] and self.settings['global'].get('debug') is True:
            self.debug = True
        if dry_run:
            self.redis = redis.Redis(
                host=self.settings['redis']['host'],
                port=self.settings['redis']['port'],
                db=10,
                encoding="utf-8", decode_responses=True,
            )
        else:
            self.redis = redis.Redis(
                host=self.settings['redis']['host'],
                port=self.settings['redis']['port'],
                db=self.settings['redis']['db'],
                encoding="utf-8", decode_responses=True,
            )
        # if you don't want send something via pushover, just remove `pushover` from settings.yml
        if self.settings['pushover']:
            self.pushover = pushover.Client(
                self.settings['pushover']['user_key'],
                api_token=self.settings['pushover']['api_token'],
            )


    def discover_plugins(self) -> None:
        self._plugins = {
           name: importlib.import_module(name)
           for finder, name, ispkg in pkgutil.iter_modules() if name.startswith('srpusher_plugin_')
        }
        self._log = self._plugins["srpusher_plugin_logging"].SRPusher_Logger()


    def disable_pushover(self) -> None:
        self.pushover = None
        logging.debug("PushOver has disabled.")

    @property
    def sr_status(self) -> list:
        """ Get SR status from SR API """
        min_wait_sec = 10
        if (self._previous_sr_status_epoch + min_wait_sec) > time.time():
            return self._previous_sr_status

        http_headers = {
            "User-Agent": self.settings["sr"]["http_user_agent"] if "http_user_agent" in self.settings["sr"] else self.default_ua
        }
        url = self.settings["sr"]["api_url"]
        if url.startswith("uggcf://"):
            url = codecs.decode(url, 'rot13')
        response = requests.get(url, headers=http_headers)
        if response.status_code == requests.codes.ok:
            self._previous_sr_status_epoch = time.time()
            self._previous_sr_status = json.loads(response.text)
        else:
            logging.error(f"(SR API) {response.status_code}: {response.text}")
        return self._previous_sr_status


    def send_notification(self, message: str, title: str) -> bool:
        """ Send notification via pushover """
        if self.pushover is None:
            logging.debug("PushOver has disabled or not configured.")
            return False
        if not message:
            return False
        logging.info(f"(Send PushOver) {title}: {message}")
        return self.pushover.send_message(message, title=title)


    def get_users_diff(self, key1, key2) -> list:
        """ Get offline<=>online of users diff from redis """
        return list(self.redis.sdiff(key1, key2))


    def set_users_status(self, key, userids) -> None:
        """ Set users online status in redis """
        self.redis.delete(key)
        for userid in userids:
            if str(userid) and userid != '':
                self.redis.sadd(key, userid.lower())
        self.redis.expire(key, 60 * 60 * 24 * 7)


    def flush_users_status(self, key_src: str, key_dest: str) -> None:
        """ Flush user online status for next comparing """
        # swap and flush!
        self.redis.delete(key_dest)
        self.redis.sinterstore(key_dest, key_src)
        if not self.debug:
            self.redis.delete(key_src)
        self.redis.expire(key_dest, 60 * 60 * 24 * 7)


    def set_user_cache(self, userid: str, status: object) -> None:
        """ Cache user detail in redis.
            the information of user that go offline must be cached or it will be UNKNOWN (of course!)
        """
        key = self.header_usercache + userid.lower()
        self.redis.set(key, json.dumps(status))
        self.redis.expire(key, 60 * 60)  # shorter is ok, at least it should remain until the next fetch.


    def set_room_cache(self, roomid: str, room_object: object) -> None:
        """ Cache room detail in redis """
        key = self.header_roomcache + roomid
        self.redis.set(key, json.dumps(room_object))
        self.redis.expire(key, 60 * 60)


    def get_user_cache(self, userid: str) -> object:
        """ Get user detail cache from cache redis """
        key = self.header_usercache + userid.lower()
        try:
            usercache = json.loads(self.redis.get(key))
        except TypeError:
            usercache = {}
        return usercache


    def generate_roomid(self, createTime: str, roomName: str) -> str:
        """ Generate roomid from timestamp+name """
        return hashlib.sha256((str(createTime) + roomName).encode('utf-8')).hexdigest()


    def srpprint(self, users: list, style: str = '') -> None:
        """ sr pprint for debug """
        for userid in users:
            logging.info(userid + f" [{style}]" + (self.get_user_cache(userid).get("nickname") if dict(self.get_user_cache(userid)) else '') + "[/]", extra={"markup": True})


    def check_notify_duplicated(self, keyword: str) -> bool:
        """ Check if the notification is duplicated and if not, set it """
        key = self.header_keyword + keyword
        if self.redis.exists(key):
            self.redis.expire(key, 60 * 60)  # extend
            return True
        else:
            self.redis.set(key, 1)
            self.redis.expire(key, 60 * 60)
            return False


    def check_keyword(self, *args: str, members: list = []) -> bool:
        """ Check if keywords is in args or not, and if keywords already has been in recently """
        keywords = self.settings["sr"].get("target_keywords") or []
        keywords_negative = self.settings["sr"].get("target_keywords_exclude") or []
        members_negative = self.settings["sr"].get("targets_exclude") or []
        for arg in args:
            if str(arg) and arg != '' and \
                    [k for k in keywords if k in arg] and \
                    not [k for k in keywords_negative if k in arg] and \
                    not [u['userId'] for u in members if u['userId'] in members_negative]:
                if not self.check_notify_duplicated(arg):
                    return True
        return False


    def check_sr_status(self) -> bool:
        """ Check SR status and send notification if needed """
        nowtime = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        content = self.sr_status

        # pass 1
        online_members = []
        for room in content["rooms"]:
            for m in room["members"]:
                userid = m.get("userId")
                online_members.append(userid)
                self.set_user_cache(userid, m)
        # set current users to `current` list
        self.set_users_status(self.key_members, online_members)
        # compare current list with `previous` list
        offlined_users = self.get_users_diff(self.key_members_previous, self.key_members)
        onlined_users = self.get_users_diff(self.key_members, self.key_members_previous)
        if len(onlined_users):
            logging.info("[bold]--- onlined[/]", extra={"markup": True})
            self.srpprint(onlined_users, style="bold white")
        if len(offlined_users):
            logging.info("[grey]--- offlined[/]", extra={"markup": True})
            self.srpprint(offlined_users, style="grey")
        # flush previous list with current list
        self.flush_users_status(self.key_members, self.key_members_previous)

        # pass 2
        new_rooms_text = {}
        for room in content["rooms"]:
            is_new_room = False
            roomname = room.get("roomName")
            roomdesc = room.get("roomDesc")
            numMembers = room.get("numMembers")
            needPasswd = room.get("needPasswd")
            members = room.get("members")
            createTime = dateutil.parser.parse(room.get("createTime"))
            roomid = self.generate_roomid(createTime, roomname)
            self.set_room_cache(roomid, room)
            if self.check_keyword(roomname, roomdesc, members=members):
                is_new_room = True
                logging.debug("keyword: {} {}".format(roomname, roomdesc))
            room_members = ""
            for m in room["members"]:
                nickname = m.get("nickname")
                userid = m.get("userId")
                # memberid = m.get("nsgmMemberId")  # This could be a action ID?
                if self.check_keyword(nickname, members=members):
                    is_new_room = True
                    logging.debug("keyword: {}".format(nickname))
                if userid in list(onlined_users) and userid in self.settings["sr"]["targets"]:
                    header = "  + "  # online-ed now
                elif userid in self.settings["sr"]["targets"]:
                    header = "  * "  # pinned
                else:
                    header = "  - "  # normal
                room_members += f"{header}{nickname}\n"

                if is_new_room or (userid in self.settings["sr"]["targets"] and userid not in self.settings["sr"].get("targets_exclude") and userid in onlined_users):
                    room_members_text = {}
                    room_members_text['room'] = '{}{}'.format(roomname, ' (protected)' if needPasswd else '')
                    room_members_text['detail'] = 'Members({}):\n{}\n{}\nElapsed: {}\n\n'.format(numMembers, room_members, roomdesc, (nowtime - createTime))
                    new_rooms_text[roomid] = room_members_text
        for k, v in new_rooms_text.items():
            result = self.send_notification(v['detail'], title=v['room'])
            logging.info(str(result))


    def run(self, runonce=False) -> None:
        """ default first runner """
        base_wait_sec = float(self.settings["sr"]["api_duration_sec"])
        while True:
            self.check_sr_status()
            if runonce:
                return
            jitter = random.uniform(1 - float(self.settings["sr"]["api_duration_jitter"]), 1 + self.settings["sr"]["api_duration_jitter"])
            logging.info(f"sleep {int(base_wait_sec * jitter)} sec")
            time.sleep(base_wait_sec * jitter)


if __name__ == '__main__':
    loglevel = logging.INFO

    stream_handler: rich.logging.RichHandler = rich.logging.RichHandler(rich_tracebacks=True)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--runonce', '-1', action='store_true', help='run once and exit')
    parser.add_argument('--disable_pushover', action='store_true', help='disable pushover')
    parser.add_argument('--quiet', '-s', action='store_true', help="show less logs")
    parser.add_argument('--debug', '-v', action='store_true', help='show more logs')
    parser.add_argument('--plugins', action='store_true')
    args = parser.parse_args().__dict__

    if args.get('quiet'):
        loglevel = logging.ERROR
    if args.get('debug'):
        loglevel = logging.DEBUG
    if 'DEBUG' in os.environ:
        loglevel = logging.DEBUG
    if args.get('plugins'):
        sys.exit(0)

    stream_handler.setLevel(loglevel)
    logging.basicConfig(level=loglevel, handlers=[stream_handler])

    if loglevel <= logging.INFO:
        print("hit Ctrl-c to exit.")

    srp = SRPusher()
    logging.info("hit Ctrl-c to exit.")

    if args.get('disable_pushover'):
        srp.disable_pushover()

    srp.run(args.get('runonce'))
    sys.exit(0)
