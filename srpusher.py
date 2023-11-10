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
    debug = True
    header_channel = "__channel__"
    header_usercache = "__usercache__"
    header_keyword = "__keyword__"
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    key_members = "members"
    key_members_previous = "members_prev"
    _previous_sr_status_epoch = 0
    _previous_sr_status = None

    def __init__(self, dry_run=False) -> None:
        if dry_run:
            self.redis = redis.Redis(
                host=self.settings['redis']['host'],
                port=self.settings['redis']['port'],
                db=10,
                charset="utf-8", decode_responses=True,
            )
        else:
            self.redis = redis.Redis(
                host=self.settings['redis']['host'],
                port=self.settings['redis']['port'],
                db=self.settings['redis']['db'],
                charset="utf-8", decode_responses=True,
            )
        # if you don't want send something via pushover, just remove `pushover` from settings.yml
        if self.settings['pushover']:
            self.pushover = pushover.Client(
                self.settings['pushover']['user_key'],
                api_token=self.settings['pushover']['api_token'],
            )

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
        # if self.pushover.message_status() != pushover.PUSHOVER_MESSAGE_STATUS_OK:
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


    def srpprint(self, users: list) -> None:
        """ sr pprint for debug """
        for userid in users:
            logging.info(userid + " " + (self.get_user_cache(userid).get("nickname") if dict(self.get_user_cache(userid)) else ''))


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


    def check_keyword(self, *args: str) -> bool:
        keywords = self.settings["sr"].get("target_keywords") or []
        keywords_negative = self.settings["sr"].get("target_keywords_exclude") or []
        for arg in args:
            if str(arg) and arg != '' and \
                    [k for k in keywords if k in arg] and not [k for k in keywords_negative if k in arg]:
                if not self.check_notify_duplicated(arg):
                    return True
        return False


    def check_sr_status(self) -> bool:
        """ Check SR status and send notification if needed """
        nowtime = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        content = self.sr_status
        """
          memo
            room[]:
              - roomName
              - roomDesc
              - numMembers
              - createTime
              - members[]:
                  - nickname
                  - userId
                  - nsgmMemberId
        """
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
            logging.info("--- onlined")
            self.srpprint(onlined_users)
        if len(offlined_users):
            logging.info("--- offlined")
            self.srpprint(offlined_users)
        # flush previous list with current list
        self.flush_users_status(self.key_members, self.key_members_previous)

        # pass 2
        new_rooms_text = {}
        new_rooms = {}
        for room in content["rooms"]:
            is_new_room = False
            roomname = room.get("roomName")
            roomdesc = room.get("roomDesc")
            numMembers = room.get("numMembers")
            needPasswd = room.get("needPasswd")
            createTime = dateutil.parser.parse(room.get("createTime"))
            roomid = self.generate_roomid(createTime, roomname)
            if self.check_keyword(roomname, roomdesc):
                is_new_room = True
                logging.debug("keyword: {} {}".format(roomname, roomdesc))
            for m in room["members"]:
                nickname = m.get("nickname")
                userid = m.get("userId")
                # memberid = m.get("nsgmMemberId")  # This could be a action ID?
                if self.check_keyword(nickname):
                    is_new_room = True
                    logging.debug("keyword: {}".format(nickname))
                if (userid in self.settings["sr"]["targets"] and userid not in self.settings["sr"].get("targets_exclude") and userid in onlined_users) or is_new_room:
                    members = "  - "
                    members += "\n  - ".join([x['nickname'] for x in room["members"]])
                    roomext = ' (protected)' if needPasswd else ''
                    members_text = 'Room: {}{}\nMembers({}):\n{}\n{}\nElapsed: {}\n\n'.format(roomname, roomext, numMembers, members, roomdesc, (nowtime - createTime))
                    new_rooms_text[roomid] = members_text
                    new_rooms[roomid] = room
        for k, v in new_rooms_text.items():
            logging.info(v)
            self.send_notification(v, title=new_rooms[k].get("roomName"))


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
    stream_handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--runonce', '-1', action='store_true', help='run once and exit')
    parser.add_argument('--disable_pushover', action='store_true', help='disable pushover')
    parser.add_argument('--quiet', '-s', action='store_true', help="show less logs")
    parser.add_argument('--debug', '-v', action='store_true', help='show more logs')
    args = parser.parse_args().__dict__

    if args.get('silent'):
        loglevel = logging.ERROR
    if args.get('debug'):
        loglevel = logging.DEBUG
    if 'DEBUG' in os.environ:
        loglevel = logging.DEBUG

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
