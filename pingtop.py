# -*- coding: utf-8 -*-

import logging
import click
import urwid
import threading
from concurrent.futures import ThreadPoolExecutor
from ping import do_one
import time
from gui import screen, tablebox, get_palette, old_signal_keys

logging.basicConfig(
    filename="pingtop.log",
    filemode="a",
    format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)


hosts = {"baidu.com": {}, "alipay.com": {}}
event = threading.Event()


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


def forever_ping(dest, index_flag):
    logging.info("start ping...")
    global hosts
    global event
    while event.is_set():
        delay = do_one(dest, 1, 64, index_flag)
        if delay is None:
            hosts[dest].setdefault("lost", 0)
            hosts[dest]["lost"] += 1
        else:
            hosts[dest].setdefault("rtts", []).append(delay)
        logging.info("requeryed")
        time.sleep(1)

        tablebox.table.one["real_rtt"] = 300
        tablebox.table.reset()
        mainloop.draw_screen()


def _raise_error(future):
    exp = future.exception()
    if exp:
        logging.exception(exp)


@click.command()
def multi_ping():
    global hosts
    pool = ThreadPoolExecutor(max_workers=len(hosts))
    event.set()
    for index, host in zip(range(len(hosts)), hosts):
        future = pool.submit(forever_ping, host, index)
        future.add_done_callback(_raise_error)

    try:
        mainloop.run()
    finally:
        screen.tty_signal_keys(*old_signal_keys)


if __name__ == "__main__":
    multi_ping()
