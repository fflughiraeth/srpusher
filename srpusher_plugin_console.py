#! venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

"""
    This is a tiny sample of plugin.
    Output event log to console.
"""
import logging
import traceback
import pluggy

# use pluggy and make hookimpl
srphookimpl = pluggy.HookimplMarker("srpusher")


class SRPusher_Console(object):
    """
    1. SRPusher automatically loads modules and evaluate classes, whose filename startswith `srpusher_plugin_` and whose class name startswith `SRPusher_`.
    2. The method name of the method you want to be hooked must be [`onlined_room`, `offlined_room`, `onlined_user`, `offlined_user`]. and the name is usually unchangeable.
    3. These method must have `srphookimpl` decorator.
    """
    def __init__(self, parent=None):
        pass

    @srphookimpl
    def onlined_room(self, room: dict, roomid: str) -> None:
        """ Called when a new room is created """
        try:
            logging.info("Room has appeared: '{}' created by '{}'".format(room.get("roomName"), room["creator"].get("nickname")))
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def offlined_room(self, room: dict, roomid: str) -> None:
        """ Called when a room disappeared. The room object given is cached when it last existed. """
        try:
            logging.info("Room has disappeared: '{}'".format(room.get("roomName")))
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def onlined_user(self, user: dict, room: dict, roomid: str) -> None:
        """ Called when a new user appears. """
        try:
            logging.info("User Onlined: '{}' to room '{}'({}/5)".format(user.get("nickname"), room.get("roomName"), len(room.get("members"))))
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def offlined_user(self, user: dict, room: dict, roomid: str) -> None:
        """ Called when a user is no longer in any room (signed-out). The room and user objects given are cached they last existed. """
        try:
            logging.info("User Offlined: '{}' from room '{}'({}/5)".format(user.get("nickname"), room.get("roomName"), len(room.get("members"))))
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def option_room(self, room: dict, roomid: str) -> None:
        """ room alternatives """
        try:
            logging.warn("(Option)Room: '{}'".format(room.get("roomName")))
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def hit_keyword(self, messages: list, keyword: None) -> None:
        """ keyword hit """
        try:
            for message in messages:
                logging.info("(Hit Keyword) Message: {}".format(message))
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def send_pushover(self, message: str, title: None) -> None:
        try:
            logging.info(f"(Send PushOver) {title}: {message.strip()}")
        except Exception:
            logging.error(traceback.format_exc())

    @srphookimpl
    def changed_user_status(self, user: dict, user_prev: dict) -> None:
        try:
            logging.debug("(userstatus) %s -> %s" % (str(user_prev), str(user)))
        except Exception:
            logging.error(traceback.format_exc())
