# -*- coding: utf-8 -*-

import logging
import click
import urwid
import threading
from concurrent.futures import ThreadPoolExecutor
from ping import do_one
import time

import urwid
from urwid_datatable import *
from urwid_utils.palette import *
import os
import random
import string

logging.basicConfig(
    filename="pingtop.log",
    filemode="a",
    format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

WAIT_TIME = 1  # seconds
hosts = {
    "baidu.com": {},
    "alipay.com": {},
    "google.com": {},
    "kawabangga.com": {},
    "weibo.com": {},
    "qq.com": {},
    "taobao.com": {},
}
event = threading.Event()

screen = urwid.raw_display.Screen()
# screen.set_terminal_properties(1<<24)
screen.set_terminal_properties(256)

NORMAL_FG_MONO = "white"
NORMAL_FG_16 = "light gray"
NORMAL_BG_16 = "black"
NORMAL_FG_256 = "light gray"
NORMAL_BG_256 = "g0"

COLUMNS = [
    DataTableColumn(
        "host",
        label="Host(IP)",
        width=16,
        align="left",
        sort_key=lambda v: (v is None, v),
        attr="color",
        padding=0,
    ),
    DataTableColumn(
        "seq",
        label="Seq",
        width=10,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
    DataTableColumn(
        "real_rtt",
        label="RTT(ms)",
        width=10,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
    DataTableColumn(
        "min_rtt",
        label="Min",
        width=10,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
    DataTableColumn(
        "avg_rtt",
        label="Avg",
        width=10,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
    DataTableColumn(
        "max_rtt",
        label="Max",
        width=10,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
    DataTableColumn(
        "lost",
        label="LOSS",
        width=10,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
]


def get_palette():
    attr_entries = {}
    for attr in ["dark red", "dark green", "dark blue"]:
        attr_entries[attr.split()[1]] = PaletteEntry(
            mono="white", foreground=attr, background="black"
        )
    entries = DataTable.get_palette_entries(user_entries=attr_entries)
    palette = Palette("default", **entries)
    return palette


class PingDataTable(DataTable):

    columns = COLUMNS[:]

    index = "index"

    def __init__(self, num_rows=10, *args, **kwargs):
        self.num_rows = num_rows
        self.query_data = self.query()
        self.last_rec = len(self.query_data)
        super().__init__(*args, **kwargs)

    def query(self, sort=(None, None), offset=None, limit=None, load_all=False):
        global hosts
        rows = []
        for host, properties in hosts.items():
            temp = {"host": host}
            temp.update(properties)
            rows.append(temp)
        return rows

    def query_result_count(self):
        return len(self.query_data)


class MainBox(urwid.WidgetWrap):
    def __init__(self, *args, **kwargs):

        self.table = PingDataTable(*args, **kwargs)
        urwid.connect_signal(
            self.table,
            "select",
            lambda source, selection: logger.info("selection: %s" % (selection)),
        )
        label = "size:%d page:%s sort:%s%s hdr:%s ftr:%s sortable:%s" % (
            self.table.query_result_count(),
            self.table.limit if self.table.limit else "-",
            "-" if self.table.sort_by[1] else "+",
            self.table.sort_by[0],
            "y" if self.table.with_header else "n",
            "y" if self.table.with_footer else "n",
            "y" if self.table.ui_sort else "n",
        )
        self.pile = urwid.Pile(
            [
                ("pack", urwid.Text(label)),
                ("pack", urwid.Divider("\N{HORIZONTAL BAR}")),
                ("weight", 1, self.table),
            ]
        )
        super().__init__(self.pile)


tablebox = MainBox(
    1000,
    index="uniqueid",
    sort_refocus=True,
    sort_icons=True,
    with_scrollbar=True,
    border=(1, "\N{VERTICAL LINE}", "blue"),
    padding=3,
    with_footer=False,
)

old_signal_keys = screen.tty_signal_keys()
l = list(old_signal_keys)
l[0] = "undefined"
l[3] = "undefined"
l[4] = "undefined"
screen.tty_signal_keys(*l)


def global_input(key):
    if key in ("q", "Q"):
        # TODO Ctrl-C
        event.clear()
        raise urwid.ExitMainLoop()
    else:
        return False


mainloop = urwid.MainLoop(
    tablebox, palette=get_palette(), screen=screen, unhandled_input=global_input
)


def forever_ping(dest, index_flag):
    logging.info("start ping...")
    global hosts
    global event
    while event.is_set():
        logging.info(f"ping {dest}, {index_flag}")
        delay = do_one(dest, 1, 64, index_flag)
        dest_attr = hosts[dest]
        dest_attr.setdefault("seq", 1)
        dest_attr["seq"] += 1
        if delay is None:
            hosts[dest].setdefault("lost", 0)
            hosts[dest]["lost"] += 1
        else:
            delay_ms = int(delay * 1000)
            dest_attr.setdefault("rtts", []).append(delay_ms)
            dest_attr["real_rtt"] = delay_ms
            dest_attr["min_rtt"] = min(dest_attr["rtts"])
            dest_attr["max_rtt"] = max(dest_attr["rtts"])
            dest_attr["avg_rtt"] = "%.1f" % (sum(dest_attr["rtts"]) / dest_attr["seq"])
        sleep_time = WAIT_TIME - delay if delay else 0
        logger.info(f"Sleep for seconds {sleep_time}")
        time.sleep(sleep_time)

        tablebox.table.reset(reset_sort=False)


def _raise_error(future):
    exp = future.exception()
    if exp:
        logging.exception(exp)


def screen_painter():
    while 1:
        mainloop.draw_screen()
        time.sleep(.01)


@click.command()
def multi_ping():
    global hosts
    worker_num = len(hosts) + 10
    logger.info(f"Open ThreadPoolExecutor with max_workers={worker_num}.")
    pool = ThreadPoolExecutor(max_workers=worker_num)
    event.set()
    for index, host in zip(range(len(hosts)), hosts):
        future = pool.submit(forever_ping, host, index)
        future.add_done_callback(_raise_error)
    future = pool.submit(screen_painter)
    future.add_done_callback(_raise_error)

    try:
        mainloop.run()
    finally:
        screen.tty_signal_keys(*old_signal_keys)


if __name__ == "__main__":
    multi_ping()
