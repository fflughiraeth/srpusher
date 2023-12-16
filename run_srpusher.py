#! venv/bin/python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 sts=4 ff=unix ft=python expandtab

import os
import sys
import logging
import rich.logging
import importlib
import pkgutil
import argparse
import pluggy

from srpusher import SRPusher
srphookspec = pluggy.HookspecMarker("srpusher")


def discover_plugins(disable_plugins=False) -> dict:
    """ import plugins that named as srpusher_plugin_*py """
    if disable_plugins:
        logging.info("Plugins are disabled.")
        return {}
    _plugins = {
        name: importlib.import_module(name)
        for _, name, _ in pkgutil.iter_modules() if name.startswith('srpusher_plugin_')
    }
    logging.info("Discovered Plugins: " + str(_plugins), stack_info=False)
    return _plugins


if __name__ == '__main__':
    loglevel = logging.INFO

    stream_handler: rich.logging.RichHandler = rich.logging.RichHandler(rich_tracebacks=True)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--runonce', '-1', action='store_true', help='run once and exit')
    parser.add_argument('--disable_pushover', action='store_true', help='disable pushover')
    parser.add_argument('--quiet', '-s', action='store_true', help="show less logs")
    parser.add_argument('--debug', '-v', action='store_true', help='show more logs')
    parser.add_argument('--disable_plugins', action='store_true', help='disable plugin')
    parser.add_argument('--list_plugins', action='store_true', help='list plugins')
    args = parser.parse_args().__dict__

    if args.get('quiet'):
        loglevel = logging.ERROR
    if args.get('debug'):
        loglevel = logging.DEBUG
    if 'DEBUG' in os.environ:
        loglevel = logging.DEBUG

    stream_handler.setLevel(loglevel)
    logging.basicConfig(level=loglevel, handlers=[stream_handler])
    if loglevel <= logging.INFO:
        print("hit Ctrl-c to exit.")

    if args.get('disable_plugins'):
        SRPusher.disable_plugins = True

    plugins = discover_plugins(args.get('disable_plugins'))
    logging.debug("All plugins: " + str(plugins))
    pm = pluggy.PluginManager("srpusher")
    srp = SRPusher(pm=pm)
    pm.add_hookspecs(SRPusher)
    for package_name, module in plugins.items():
        for m in dir(module):
            if m.startswith('SRPusher_'):
                ci = getattr(module, m)()
                plugin_name = pm.register(ci)
                logging.debug(pm.get_hookcallers(ci))
                logging.info(f"Registered plugin: {package_name}.{m}")
    logging.debug(pm.list_name_plugin())
    logging.info("hit Ctrl-c to exit.")

    srp.run(args.get('runonce'))
    sys.exit(0)
