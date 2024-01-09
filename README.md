# S_R_Pusher

## Overview

This is a notifier to PushOver like SR-plus for SR.

You can receive notify with your PushOver when *someone* (as you like) has been online or offline.

😞 This is little study I wanted to make after looking at the web dev tool on SR's room page. But this is against the Terms of Service, so you shoudn't use.

## Requirements

#### SR acccount is not required.

- Python > 3.6
- Redis > 3


## Getting Started

1. Clone this repo to some directory

   ```sh
   $ mkdir -p ~/workspace
   $ git clone https://github.com/fflughiraeth/srpusher.git ~/workspace/srpusher
   $ cd ~/workspace/srpusher
   ```

2. `Redis`: Install Redis or prepare *ElastiCache* etc if you have not already used.

    1. If a Redis is already running, MAKE SURE and make change if needed `database number` so that the db number DON'T CONFLICT with other application. By default db number is `3`. Since these data that this program use are small and volatile in time, memory size is not a concern (maybe less than 1M or 2MB).

3. Copy configration file from skeleton file, `settings.yml.skel` to `settings.yml` , and edit `settings.yml`.

    1. Items to be edited:

         - `pushover: user_key` (string)
         - `pushover: api_token` (string)
           - Pushover stuff that you want to receive notification. You may get/create from https://pushover.net/apps/build (needs logged in to PushOver).  the application-dependent key is *api_token*, your account's only common key is *user_key* on PushOver. these two are easily confused.
        - SR stuff,
          - `sr:targets`(string[])
            - List the UIDs of the **users** you want to pin and receive notifications. UID, The 36 random characters, including `-` at the end of URL of a user's profile page.
          - `sr: targets_exclude` (string[])
            - also UIDs to be excluded. This does not make sense on its own, yet it may work in the keywords section below.
          - `sr: target_keywords` (string[])
            - Notify if these keywords in the roomname, room description and username. Once matched, the target will not be notified again for 1 hour. or else, those will be notified over and over again while the same keyword are present.
          - `sr: target_keywords_exclude` (string[])
            - excluded keywords list.
        - Redis configuration if needed, see above 2.
          - `redis: host`
          - `redis: port`
          - `redis: db`

4. `make setup`
    ```sh
    $ make setup
    ```
    If it fails, make sure that Python3, Python3-venv, Make, compiler to build some modules are installed.
    if you don't want to use *make*, you can run the content of the Makefile manually.

## how to run and stop

### This has 2 modes of operation.

1. **Foreground**; it continues to fetch and run all the time by itself ;  Not daemonized but it continues to run *foreground* until you stop it by Ctrl-c.
2. **Run once** and terminate, no scheduling. To run periodically, it would require something (like *cron*) .

No matter either way. Don't run two or more at the same time. When using *Run once*, make sure to run at a *sensible interval* (120 seconds or more), and add some *jitter* to the run interval if possible. now that, user's information cache expires 1 hour by default, if it executed at intervals more than 1 hour, may missing user's information will occur. So it's better that not be longer than 1 hour.


### Foreground mode
1. to run: just type `make run`
    ```sh
    $ make run
    ...
    ```

    (optional) if you don't want to use make, *activate* venv manually.

    ```sh
    $ source venv/bin/activate
    (venv)$ python run_srpusher.py
    ...
    ```
3. to stop: Ctrl-c
    ```sh
    ...
    ^C
    $
    ```

    (optional) if you *activate* venv above, you might want to *deactivate*.

    ```sh
    ...
    ^C
    (venv)$ deactivate
    $
    ```

### Run once mode
1. to run:
   ```sh
   $ source venv/bin/activate
   (venv) $ python run_srpusher.py --runonce
   ...
   (venv) $ deactivate
   $
   ```

## Internals

how it works

1. Fetch information on the room list of SR. This includes the room list and users in that room.
1. Save the online users list to Redis. This list is compared with the list that retrieved last time, and those who were online last time but don't exist this time, are assumed to be offlin-ed users. The online user list is stored on a *Set* of Redis, *sdiff* is used for difference detection.
1. If any of the users who went online this time *you  pinned*, the room and users information will be notified via PushOver.
1. In foreground mode, it after waiting, then returns to the begeninning. In *Run once*, it exits immediately.


## How to write plugin

### What is this

This plugin mechanism makes it easy to create your original functions() and methods() that are **called when some events occur.**

`srpusher_plugin_console.py` is an accompanying sample that displays status in console, it works by default.

Events are listed in the table below.

### Getting started

1. Create your `.py` file, the filename must be startswith `srpusher_plugin_`, and place it at the same path as `srpusher.py`.
1. Write `import pluggly` in your `.py`
1. Write `srphookimpl = pluggy.HookimplMarker("srpusher")` in your `.py` just below `import` statements.
1. Define a class, that name must startswith `SRPusher_`. No inheritance required.

   1. Write your method(s). See table below.
   2. Decorate with `@srphookimpl` the method you wrote.

| name of method | given args | Events (When to called) |
| ---- | ---- | ---- |
| onlined_room | (room: dict, roomid: str) | When a new room is created. |
| offlined_room | (room: dict, roomid: str) | When a room disappeared. <br/>The room object given is cached when it last existed. |
| onlined_user | (user: dict, room: dict, roomid: str) | When a new user appears. |
| offlined_user | (user: dict, room: dict, roomid: str) | When a user is no longer in any room (signed-out).<br />The room and user objects given are cached they last existed. |
| send_pushover | (message: str, title: str) | When a pushover message has sent. |
| hit_keyword | (message: str[], keyword: str[]) | When a keyword hits |

- room: One of the `room` object _from original API of SR_
- roomid: _generated_ room ID, **not in** original API of SR
- user: One of the `user` _from original API of SR_

### Other limitation
- The name of method usually fixed. What this means is that there is only one method per event that will be hooked and evaluated in a class.
- Please handle exceptions properly. The parent does not handle any exception in plugins. If you raise an exception from your plugin, the parent would stop. There is no guarantee that the data coming from API has the corrrect structure; there may be no `key` in dict for example.


### Internals about plugin

how it works

1. import all .py files in the same path as `run_srpusher.py`, whose filename starts with `srpusher_plugin_`.
1. Create all instances of classes name starts with `SRPusher_` on imported above.
1. Add all instances created above to hooks of pluggy.
1. On event, the hooked methods(decorated with @srphookimpl) of all classses and of all modules are executed in turns.

**Q: Can I write some plugin that overrides the behavior of the parent or other plugin?**

**A:** No. It might not be impssible under the Python language specification, but it surely shouldn't be done.


## uninstall

1. delete working directory that git clone
2. flush your Redis if needed

## License

MIT
