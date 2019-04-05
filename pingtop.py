# -*- coding: utf-8 -*-

import click
import urwid
import threading
from concurrent.futures import ThreadPoolExecutor
from ping import do_one
import time
from gui import screen, tablebox, get_palette, old_signal_keys


hosts = {"baidu.com": {}, "alipay.com": {}}
event = threading.Event()


def forever_ping(dest, index_flag):
    global hosts
    global event
    while event.is_set():
        delay = do_one(dest, 1, 64, index_flag)
        if delay is None:
            hosts[dest].setdefault("lost", 0)
            hosts[dest]["lost"] += 1
        else:
            hosts[dest].setdefault("rtts", []).append(delay)
        time.sleep(1)


def global_input(key):
    if key in ("q", "Q"):
        # TODO Ctrl-C
        event.clear()
        raise urwid.ExitMainLoop()
    else:
        return False


mainloop = urwid.MainLoop(
    urwid.Frame(urwid.Filler(tablebox)),
    palette=get_palette(),
    screen=screen,
    unhandled_input=global_input,
)


@click.command()
def multi_ping():
    global hosts
    pool = ThreadPoolExecutor(max_workers=len(hosts))
    event.set()
    for index, host in zip(range(len(hosts)), hosts):
        last_future = pool.submit(forever_ping, host, index)

    try:
        mainloop.run()
    finally:
        screen.tty_signal_keys(*old_signal_keys)


if __name__ == "__main__":
    multi_ping()
