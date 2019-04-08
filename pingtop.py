# -*- coding: utf-8 -*-

import logging
import click
import urwid
import threading
import socket
from concurrent.futures import ThreadPoolExecutor
from ping import do_one
import time
import statistics

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
hosts = {}
event = threading.Event()
screen_lock = threading.Lock()


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
        padding=1,
    ),
    DataTableColumn(
        "ip",
        label="IP",
        width=3 * 4 + 3 + 2,
        align="left",
        sort_reverse=True,
        sort_icon=False,
        padding=1,
    ),
    DataTableColumn(
        "seq",
        label="Seq",
        width=4,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "real_rtt",
        label="RTT",
        width=6,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "min_rtt",
        label="Min",
        width=6,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "avg_rtt",
        label="Avg",
        width=6,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "max_rtt",
        label="Max",
        width=6,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "std",
        label="Std",
        width=7,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "lost",
        label="LOSS",
        width=5,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
    ),
    DataTableColumn(
        "lostp",
        label="LOSS%",
        width=6,
        align="right",
        sort_reverse=True,
        sort_icon=False,
        padding=0,
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
l[0] = l[3] = l[4] = "undefined"
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
    dest_ip = socket.gethostbyname(dest)
    dest_attr = hosts[dest]

    dest_attr["ip"] = dest_ip
    dest_attr.setdefault("lost", 0)
    dest_attr.setdefault("lostp", "0%")
    dest_attr.setdefault("seq", 0)
    dest_attr.setdefault("real_rtt", 999)
    dest_attr.setdefault("min_rtt", 999)
    dest_attr.setdefault("max_rtt", 999)
    dest_attr.setdefault("avg_rtt", 999)
    dest_attr.setdefault("std", 0)
    rtts = dest_attr.setdefault("rtts", [])

    while event.is_set():
        logging.info(f"ping {dest}, {index_flag}")
        delay = do_one(dest, 1, 64, index_flag)
        with screen_lock:
            dest_attr["seq"] += 1
            if delay is None:
                dest_attr["lost"] += 1
                dest_attr["lostp"] = "{0:.0%}".format(dest_attr["lost"] / dest_attr["seq"])
            else:
                delay_ms = int(delay * 1000)
                rtts.append(delay_ms)
                dest_attr["real_rtt"] = delay_ms
                dest_attr["min_rtt"] = min(dest_attr["rtts"])
                dest_attr["max_rtt"] = max(dest_attr["rtts"])
                dest_attr["avg_rtt"] = "%.1f" % (sum(dest_attr["rtts"]) / dest_attr["seq"])
                if len(rtts) >= 2:
                    dest_attr["std"] = "%2.1f" % (statistics.stdev(rtts))
            sleep_time = WAIT_TIME - delay if delay else 0
            logger.info(f"{dest}({dest_ip})Sleep for seconds {sleep_time}")
            position = tablebox.table.focus_position
            logger.info(f"Position: {position}")

            focus_host = ""
            try:
                row = tablebox.table.get_row_by_position(position)
            except IndexError:
                pass
            else:
                logger.info(f"Row: {row}")
                logger.info(f"Row: {row.values}")
                focus_host = row.values['host']

            tablebox.table.reset(reset_sort=True)
            tablebox.table.sort_by_column("real_rtt", False)
            for r in tablebox.table.filtered_rows:
                row = tablebox.table.get_row_by_position(r)
                if row.values['host'] == focus_host:
                    tablebox.table.set_focus(r)
                    break
            mainloop.draw_screen()

        time.sleep(sleep_time)


def _raise_error(future):
    exp = future.exception()
    if exp:
        logging.exception(exp)


@click.command()
@click.argument("host", nargs=-1)
def multi_ping(host):
    global hosts
    hosts = {h: {} for h in host}
    logger.info(f"Hosts: {hosts}")
    worker_num = len(hosts)
    logger.info(f"Open ThreadPoolExecutor with max_workers={worker_num}.")
    pool = ThreadPoolExecutor(max_workers=worker_num)
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
