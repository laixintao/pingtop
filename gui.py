#!/usr/bin/python

import logging

logger = logging.getLogger(__name__)
import urwid
from urwid_datatable import *
from urwid_utils.palette import *
import os
import random
import string

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
        "real_rtt",
        label="RTT(ms)",
        width=10,
        align="left",
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
        # indexes = random.sample(range(self.num_rows*2), num_rows)
        self.one = {"host": "www.baidu.com", "real_rtt": 100}
        self.query_data = [
            self.one,
            {"host": "www.google.com", "real_rtt": 200},
        ]

        self.last_rec = len(self.query_data)
        super(PingDataTable, self).__init__(*args, **kwargs)

    def query(self, sort=(None, None), offset=None, limit=None, load_all=False):
        return self.query_data

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
                ("pack", urwid.Divider("-")),
                ("weight", 1, self.table),
            ]
        )
        self.box = urwid.BoxAdapter(urwid.LineBox(self.pile), 25)
        super().__init__(self.box)


tablebox = MainBox(
    1000,
    index="uniqueid",
    sort_refocus=True,
    sort_icons=False,
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
