#! venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

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
import pluggy
import inspect
from typing import Tuple

srphookspec = pluggy.HookspecMarker("srpusher")


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
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    key_members = "members"
    key_members_previous = "members_prev"
    key_rooms = "rooms"
    key_rooms_option = "rooms_option"
    key_rooms_previous = "rooms_prev"
    key_func_count = "_sr_function_counter"
    key_func_count_previous = "_sr_function_counter_previous"
    key_func_gauge = "_sr_function_gauge"
    _previous_sr_status_epoch = 0
    _previous_sr_status_epoch_private = 0
    _previous_sr_status = None
    _disable_plugins = False
    _all_members = {}


    def __init__(self, dry_run=False, configfilename="settings.yml", pm=None) -> None:
        self._filename = configfilename
        self.pm = pm
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


    @property
    def disable_plugins(self) -> bool:
        return self._disable_plugins

    @disable_plugins.setter
    def disable_plugins(self, value: bool) -> None:
        self._disable_plugins = value

    def disable_pushover(self) -> None:
        self.pushover = None
        logging.debug("PushOver has disabled.")

    def function_counter(self, fname: str, count=1) -> int:
        return self.redis.hincrby(self.key_func_count, fname, count)

    def function_gauge(self, fname: str, value: float) -> int:
        return self.redis.hset(self.key_func_gauge, fname, value)

    @property
    def sr_status(self) -> list:
        """ Get SR status from SR API """
        self.function_counter(inspect.currentframe().f_code.co_name)
        min_wait_sec = 10
        if (self._previous_sr_status_epoch + min_wait_sec) > time.time():
            self.function_counter(inspect.currentframe().f_code.co_name + ".requests.cache")
            return self._previous_sr_status

        http_headers = {
            "User-Agent": self.settings["sr"]["http_user_agent"] if "http_user_agent" in self.settings["sr"] else self.default_ua
        }
        url = self.settings["sr"]["api_url"]
        if url.startswith("uggcf://"):
            url = codecs.decode(url, 'rot13')

        time_response = time.time()
        response = requests.get(url, headers=http_headers)
        time_response_delta = time.time() - time_response
        self.function_gauge(inspect.currentframe().f_code.co_name + ".requests_http_response_time", time_response_delta)

        if response.status_code == requests.codes.ok:
            self._previous_sr_status_epoch = time.time()
            self._previous_sr_status = json.loads(response.text)
            self.function_counter(inspect.currentframe().f_code.co_name + ".requests.ok")
            # self.pm.hook.update_sr_status(content=self._previous_sr_status)
        else:
            logging.error(f"(SR API) {response.status_code}: {response.text}")
            self.function_counter(inspect.currentframe().f_code.co_name + ".requests.error")

        return self._previous_sr_status

    @property
    def sr_status_option(self) -> list:
        """ abstract """
        return []

    def map_member_room(self, content: dict) -> None:
        self._all_members = {}
        try:
            for room in content["rooms"]:
                for member in room["members"]:
                    prev = self._all_members.get(member["userId"])
                    prev = prev if prev is not None else 0
                    self._all_members[member["userId"]] = 1 + prev
        except KeyError:
            pass

    def send_notification(self, message: str, title: str) -> bool:
        """ Send notification via pushover """
        self.function_counter(inspect.currentframe().f_code.co_name)
        if self.pushover is None:
            logging.debug("PushOver has disabled or not configured.")
            return False
        if not message or not type(message) is str:
            return False
        logging.debug(f"(Send PushOver) {title}: {message.strip()}")
        self.function_counter(inspect.currentframe().f_code.co_name + ".sent")
        return self.pushover.send_message(message.strip(), title=title)

    def redis_touch(self, key: str, expire: int) -> None:
        """ Set last touch time """
        self.redis.set(key, time.time())
        self.redis.expire(key, expire)

    def get_users_diff(self, key1, key2) -> list:
        """ Get offline<=>online of users diff from redis """
        self.function_counter(inspect.currentframe().f_code.co_name)
        return list(self.redis.sdiff(key1, key2))


    def set_users_status(self, key, userids) -> None:
        """ Set users online status in redis """
        self.function_counter(inspect.currentframe().f_code.co_name)
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


    def set_user_cache(self, user: object, isonline=True) -> None:
        """ Cache user detail in redis.
            the information of user that go offline must be cached or it will be UNKNOWN (of course!)
        """
        self.function_counter(inspect.currentframe().f_code.co_name)
        if type(user) is dict and user.get("userId"):
            userid = user.get("userId")
        else:
            return
        key = self.header_usercache + userid.lower()
        user["online"] = isonline
        self.redis.set(key, json.dumps(user))
        self.redis.expire(key, 60 * 60)  # shorter is ok, at least it should remain until the next fetch.


    def set_room_cache(self, roomid: str, room_object: object) -> None:
        """ Cache room detail in redis """
        self.function_counter(inspect.currentframe().f_code.co_name)
        key = self.header_roomcache + roomid
        self.redis.set(key, json.dumps(room_object))
        self.redis.expire(key, 60 * 60)


    def get_room_cache(self, roomid: str) -> object:
        """ Get room's detail cache from redis if exists (unreliable) """
        self.function_counter(inspect.currentframe().f_code.co_name)
        if roomid is None:
            return {}
        key = self.header_roomcache + roomid
        try:
            roomcache = json.loads(self.redis.get(key))
        except TypeError:
            roomcache = {}
        return roomcache

    def get_user_cache(self, userid: str) -> object:
        """ Get user's detail cache from redis if exists (unreliable) """
        self.function_counter(inspect.currentframe().f_code.co_name)
        key = self.header_usercache + userid.lower()
        try:
            usercache = json.loads(self.redis.get(key))
        except TypeError:
            usercache = {}
        return usercache


    def check_user_diff(self, user: dict, room: dict) -> None:
        """ Compare user object against cache and evaluate hook if it has changed """
        self.function_counter(inspect.currentframe().f_code.co_name)
        user_prev = None
        if type(user) is dict and user.get("userId"):
            userid = user.get("userId")
            user_prev = self.get_user_cache(userid=userid)
            if user_prev == {} or user_prev is None:
                return
        else:
            # client under v1.5 or testroom
            return

        if self._all_members.get(userid) and self._all_members.get(userid) > 1:
            room_dup = True
            logging.debug("room dup: " + user.get("nickname"))
        else:
            room_dup = False
        """ 1. nickname has changed
            2. iconInfo has changed
            3. roomid has changed but offline -> online (because it's normal) or one user has multiple logged in whether in different room or the same room(it's not normal but happens).
        """
        if user_prev.get("nickname") != user.get("nickname") or \
           user_prev["iconInfo"] != user["iconInfo"] or \
           (not (user_prev.get("online") is False and user.get("online") is True) and
                room_dup is False and user_prev.get("roomid") != '' and user.get("roomid") != '' and user_prev.get("roomid") != user.get("roomid")):
            self.pm.hook.change_user_status(user=user, user_prev=user_prev, room=room)


    def generate_roomid(self, createTime: str, roomName: str, nsgmmemberid: str) -> str:
        self.function_counter(inspect.currentframe().f_code.co_name)
        """ Generate roomid from hash(timestamp+name+actionid) """
        if (not str(createTime) or not str(roomName) or not str(nsgmmemberid)) or (createTime == '' or roomName == '' or nsgmmemberid == ''):
            logging.error("generate_roomid: invalid parameters")
            raise ValueError("generate_roomid: invalid parameters")
        # to preserve idempotence, no longer used nsgmmemberid.
        return hashlib.sha256((str(createTime) + roomName).encode('utf-8')).hexdigest()


    def get_rooms_diff(self, key1, key2) -> list:
        """ Get offline<=>online of rooms diff from redis """
        return list(self.redis.sdiff(key1, key2))

    def set_rooms_status(self, key, roomids) -> None:
        """ Set rooms alive in redis """
        self.function_counter(inspect.currentframe().f_code.co_name)
        self.redis.delete(key)
        for roomid in roomids:
            if str(roomid) and roomid != '':
                self.redis.sadd(key, roomid)
        self.redis.expire(key, 60 * 60 * 24 * 7)

    def flush_rooms_status(self, key_src: str, key_dest: str) -> None:
        """ Flush rooms alive for next comparing """
        self.redis.delete(key_dest)
        self.redis.sinterstore(key_dest, key_src)
        if not self.debug:
            self.redis.delete(key_src)
        self.redis.expire(key_dest, 60 * 60 * 24 * 7)

    def srpprint(self, users: list, style: str = '') -> None:
        """ sr pprint for debug """
        for userid in users:
            logging.info(userid + (self.get_user_cache(userid).get("nickname") if dict(self.get_user_cache(userid)) else ''))


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


    def get_onlines(self, content: dict) -> Tuple[list, list, int]:
        """
        Parse api content object, get online members and rooms.
        Side effect: Update user and room *cache in redis*.
        """
        online_members = []
        alive_rooms = []
        private_rooms_count = 0
        for room in content["rooms"]:
            roomname = room.get("roomName")
            createTime = dateutil.parser.parse(room.get("createTime"))
            nsgmmemberid = room.get("creator").get("nsgmMemberId") or ''  # actionid
            roomid = self.generate_roomid(createTime, roomname, nsgmmemberid)
            if room.get("needPasswd"):
                private_rooms_count += 1
            alive_rooms.append(roomid)
            self.set_room_cache(roomid, room)
            for m in room["members"]:
                userid = m.get("userId")
                m["roomid"] = roomid  # for user->room lookup
                m["online"] = True
                online_members.append(userid)
                self.check_user_diff(user=m, room=room)  # check user diff. the room object is for optional information
                self.set_user_cache(user=m, isonline=True)
        return online_members, alive_rooms, private_rooms_count


    def check_sr_status_diff(self, content: dict, content_option=None) -> Tuple[list, list, list, list, list]:
        # pass 1
        online_members, alive_rooms, private_rooms_count = self.get_onlines(content)
        self.redis_touch("last_fetch", 60 * 10)
        if content_option:
            _, alive_rooms_option, private_rooms_count = self.get_onlines(content=content_option)
            self.redis_touch("last_fetch_option", 60 * 10)
        else:
            _, alive_rooms_option = ([], [])

        # set current users to `current` list
        self.set_users_status(self.key_members, online_members)
        # compare current list with `previous` list
        offlined_users = self.get_users_diff(self.key_members_previous, self.key_members)
        onlined_users = self.get_users_diff(self.key_members, self.key_members_previous)
        # flush previous list with current list
        self.flush_users_status(self.key_members, self.key_members_previous)

        # also
        self.set_rooms_status(self.key_rooms, alive_rooms)
        offlined_rooms = self.get_rooms_diff(self.key_rooms_previous, self.key_rooms)
        if content_option and len(alive_rooms_option) > 0:
            self.set_rooms_status(self.key_rooms_option, alive_rooms_option)
            option_rooms = self.get_rooms_diff(self.key_rooms, self.key_rooms_option)
        else:
            option_rooms = []
        onlined_rooms = self.get_rooms_diff(self.key_rooms, self.key_rooms_previous)
        self.flush_rooms_status(self.key_rooms, self.key_rooms_previous)

        # stats
        self.function_counter(inspect.currentframe().f_code.co_name + ".onlined_users", len(onlined_users))
        self.function_counter(inspect.currentframe().f_code.co_name + ".offlined_users", len(offlined_users))
        self.function_counter(inspect.currentframe().f_code.co_name + ".onlined_rooms", len(onlined_rooms))
        self.function_counter(inspect.currentframe().f_code.co_name + ".offlined_rooms", len(offlined_rooms))
        self.function_counter(inspect.currentframe().f_code.co_name + ".option_rooms", len(option_rooms))
        self.function_gauge(inspect.currentframe().f_code.co_name + ".count_room_private", private_rooms_count)

        return onlined_users, offlined_users, onlined_rooms, offlined_rooms, option_rooms


    def check_sr_status_members(self, content: dict, onlined_users: list) -> dict:
        # pass 2
        nowtime = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
        new_rooms_text = {}
        for room in content["rooms"]:
            messages = []
            is_new_room = False
            roomname = room.get("roomName")
            roomdesc = room.get("roomDesc")
            numMembers = room.get("numMembers")
            needPasswd = room.get("needPasswd")
            members = room.get("members")
            createTime = dateutil.parser.parse(room.get("createTime"))
            nsgmmemberid = room.get("creator").get("nsgmMemberId") or ''  # actionid
            roomid = self.generate_roomid(createTime, roomname, nsgmmemberid)
            if self.check_keyword(roomname, roomdesc, members=members):
                is_new_room = True
                messages.append("keyword: {} {}".format(roomname, roomdesc))
                logging.debug("keyword: {} {}".format(roomname, roomdesc))
            room_members = ""
            for m in room["members"]:
                nickname = m.get("nickname")
                userid = m.get("userId")
                # memberid = m.get("nsgmMemberId")  # This could be a action ID?
                if self.check_keyword(nickname, members=members):
                    is_new_room = True
                    messages.append("keyword: {} {}".format(roomname, roomdesc))
                    logging.debug("keyword: {}".format(nickname))
                if userid in list(onlined_users) and userid in self.settings["sr"]["targets"]:
                    header = "  + "  # online-ed now
                elif userid in self.settings["sr"]["targets"]:
                    header = "  * "  # pinned
                elif userid in self.settings["sr"]["targets_exclude"]:
                    header = "  x "  # excluded
                else:
                    header = "  - "  # normal
                room_members += f"{header}{nickname}\n"

                if is_new_room or (userid in self.settings["sr"]["targets"] and userid not in self.settings["sr"].get("targets_exclude") and userid in onlined_users):
                    room_members_text = {}
                    room_members_text['room'] = '{}{}'.format(roomname, ' (protected)' if needPasswd else '')
                    room_members_text['detail'] = 'Members({}):\n{}\n{}\nElapsed: {}\n\n'.format(numMembers, room_members, roomdesc, (nowtime - createTime))
                    new_rooms_text[roomid] = room_members_text
                if messages:
                    self.pm.hook.hit_keyword(messages=messages, keyword=None)

        return new_rooms_text

    def check_sr_status(self) -> bool:
        """ Check SR status and send notification if needed """
        content_option = self.sr_status_option
        content = self.sr_status
        self.map_member_room(content=content)
        self.pm.hook.change_count_user(count=len(self._all_members))
        logging.info(f"{len(self.sr_status.get('rooms'))} rooms, {len(self._all_members)} membres are online.")

        onlined_users, offlined_users, onlined_rooms, offlined_rooms, option_rooms = self.check_sr_status_diff(content, content_option=content_option)
        new_rooms_text = self.check_sr_status_members(content=content, onlined_users=onlined_users)

        if len(onlined_rooms):
            for r in onlined_rooms:
                self.pm.hook.onlined_room(room=self.get_room_cache(r).copy(), roomid=r)
        if len(offlined_rooms):
            for r in offlined_rooms:
                self.pm.hook.offlined_room(room=self.get_room_cache(r).copy(), roomid=r)
        if len(option_rooms):
            for r in option_rooms:
                self.pm.hook.option_room(room=self.get_room_cache(r).copy(), roomid=r)
        if len(onlined_users):
            for u in onlined_users:
                roomid = self.get_user_cache(u).get("roomid")
                room = self.get_room_cache(roomid)
                self.pm.hook.onlined_user(user=self.get_user_cache(u).copy(), room=room, roomid=roomid)
        if len(offlined_users):
            for u in offlined_users:
                roomid = self.get_user_cache(u).get("roomid")
                room = self.get_room_cache(roomid)
                self.pm.hook.offlined_user(user=self.get_user_cache(u).copy(), room=room, roomid=roomid)
                self.set_user_cache(user=self.get_room_cache(u), isonline=False)
        for k, v in new_rooms_text.items():
            result = self.send_notification(v['detail'], title=v['room'])
            if result:
                room = self.get_room_cache(k)
                self.pm.hook.send_pushover(message=v['detail'], title=v['room'], room=room, roomid=k)
            logging.info(str(result))


    def redis_copy(self, key_dest: str, key_src: str) -> None:
        """ copy data (redis < 6.0) """
        if self.redis.exists(key_src):
            ttl = self.redis.ttl(key_src)
            self.redis.restore(key_dest, ttl=0, value=self.redis.dump(key_src), replace=True)
            if ttl > 0:
                self.redis.expire(key_dest, ttl)


    def lpf(self, n0: float, n1: float, T=.5) -> float:
        """ smoothing filter """
        return (n0 + (n1 - n0) * (.1 / (1 / (2 * 3.1415 * T))))


    def dyn_wait_sec(self, users: int):
        """ dynamic wait seconds from count(user) """
        multiplier = float(self.settings["sr"]["api_duration_dynamic"]["multiplier"])
        intercept = float(self.settings["sr"]["api_duration_dynamic"]["intercept"])
        min_wait_sec = float(self.settings["sr"]["api_duration_dynamic"]["min_wait_sec"])  # min + jitter
        min_wait_sec_abs = float(self.settings["sr"]["api_duration_dynamic"]["min_wait_sec_absolute"])
        jitter_mu = float(self.settings["sr"]["api_duration_dynamic"]["jitter_mu"])
        jitter_sigma = float(self.settings["sr"]["api_duration_dynamic"]["jitter_sigma"])
        # max_wait_sec = 60 * 3
        jitter_sec = random.gauss(mu=jitter_mu, sigma=jitter_sigma)
        wait_sec = users * multiplier + intercept
        logging.debug("wait_sec %d = %d * %.2f + %d +(%d) " % (wait_sec, users, multiplier, intercept, jitter_sec))
        # wait_sec = wait_sec if wait_sec > min_wait_sec else min_wait_sec + jitter_sec  # add jitter if clamped below minimum seconds
        raw_sec = wait_sec if wait_sec > min_wait_sec_abs else min_wait_sec_abs  # just for stats, no jitter
        wait_sec = wait_sec + jitter_sec  # add jitter if clamped below minimum seconds
        wait_sec = wait_sec if wait_sec > min_wait_sec_abs else min_wait_sec_abs + jitter_sec  # clamp absolute minimum
        # wait_sec = wait_sec if wait_sec < max_wait_sec else max_wait_sec * jitter_sec
        return (wait_sec, jitter_sec, raw_sec)


    @property
    def previous_wait_sec(self) -> float:
        try:
            return float(self.redis.get("prev_wait_sec"))
        except Exception:
            return float(self.settings["sr"]["api_duration_sec"])

    @previous_wait_sec.setter
    def previous_wait_sec(self, value: float) -> None:
        self.redis.set("prev_wait_sec", value)


    def run(self, runonce=False) -> None:
        """ default first runner """
        base_wait_sec = float(self.settings["sr"]["api_duration_sec"])
        prev_wait_sec = base_wait_sec
        while True:
            self.check_sr_status()
            if runonce:
                return
            jitter = random.uniform(1 - float(self.settings["sr"]["api_duration_jitter"]), 1 + self.settings["sr"]["api_duration_jitter"])
            logging.debug(f"{len(self.sr_status.get('rooms'))} rooms available.")

            prev_wait_sec = self.previous_wait_sec
            # (wait_sec, jitter_calc) = self.dyn_wait_sec(len(self._all_members) * (60 / prev_wait_sec))  # normalize /min
            (wait_sec, jitter_calc, raw_sec) = self.dyn_wait_sec(len(self._all_members))
            wait_sec = self.lpf(prev_wait_sec, wait_sec)
            prev_wait_sec = wait_sec
            self.previous_wait_sec = wait_sec
            logging.info("wait_sec: %d jitter(%d) exact:%d" % (wait_sec, jitter_calc, raw_sec))

            # stats
            self.pm.hook.change_count_room(count=len(self.sr_status.get('rooms')))
            self.function_gauge(inspect.currentframe().f_code.co_name + ".sleep_sec", wait_sec)
            self.function_gauge(inspect.currentframe().f_code.co_name + ".estimated_sleep_sec", raw_sec)
            self.pm.hook.py_function_count(counter=self.redis.hgetall(self.key_func_count), counter_prev=self.redis.hgetall(self.key_func_count_previous))
            self.redis_copy(key_dest=self.key_func_count_previous, key_src=self.key_func_count)
            self.redis.hset(self.key_func_count_previous, "run.previous_epoch", time.time())

            self.pm.hook.py_function_gauge(gauge=self.redis.hgetall(self.key_func_gauge))
            self.redis.delete(self.key_func_gauge)

            # time.sleep(base_wait_sec * jitter)
            time.sleep(wait_sec)


    """ format plugin decorators and hooks """
    @classmethod
    def plugin_register(cls, _class) -> None:
        classname = _class.__class__.__name__
        cls._plugin_classes[classname] = _class
        logging.info("Registered plugin: " + classname)


    @srphookspec
    def onlined_room(self, room: dict, roomid: str) -> None:
        """ call when room has created """

    @srphookspec
    def offlined_room(self, room: dict, roomid: str) -> None:
        """ call when room has vanished """

    @srphookspec
    def option_room(self, room: dict, roomid: str) -> None:
        """ call when room has vanished """

    @srphookspec
    def onlined_user(self, user: dict, room: dict, roomid: str) -> None:
        """ call when user is onlined  """

    @srphookspec
    def offlined_user(self, user: dict, room: dict, roomid: str) -> None:
        """ call when user is offlined  """

    @srphookspec
    def update_sr_status(self, content: dict) -> None:
        """ call when status is updated """

    @srphookspec
    def send_pushover(self, message: str, title: str, room: dict, roomid: str) -> None:
        """ call when send pushover """

    @srphookspec
    def hit_keyword(self, messages: list, keyword: None) -> None:
        """ call when hit keyword """

    @srphookspec
    def change_user_status(self, user: dict, user_prev: dict, room: dict) -> None:
        """ call when user object has changed """

    @srphookspec
    def change_count_user(self, count: int) -> None:
        """ count(user) """

    @srphookspec
    def change_count_room(self, count: int) -> None:
        """ count(room) """

    @srphookspec
    def py_function_count(self, counter: object, counter_prev: object) -> None:
        """ stats cache """

    @srphookspec
    def py_function_gauge(self, gauge: object) -> None:
        """ stats cache """
