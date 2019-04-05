#!/usr/bin/python

import logging

logger = logging.getLogger(__name__)
import urwid
from urwid_datatable import *
from urwid_utils.palette import *
import os
import random
import string
from optparse import OptionParser

screen = urwid.raw_display.Screen()
# screen.set_terminal_properties(1<<24)
screen.set_terminal_properties(256)

NORMAL_FG_MONO = "white"
NORMAL_FG_16 = "light gray"
NORMAL_BG_16 = "black"
NORMAL_FG_256 = "light gray"
NORMAL_BG_256 = "g0"


def main():
    parser = OptionParser()
    parser.add_option("-v", "--verbose", action="count", default=0),
    (options, args) = parser.parse_args()

    if options.verbose:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)8s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        fh = logging.FileHandler("datatable.log")
        # fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        if options.verbose > 1:
            logger.setLevel(logging.DEBUG)
            logging.getLogger("urwid_datatable").setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
            logging.getLogger("urwid_datatable").setLevel(logging.INFO)
        logger.addHandler(fh)
        logging.getLogger("urwid_datatable").addHandler(fh)
        # logging.getLogger("raccoon.dataframe").setLevel(logging.DEBUG)
        # logging.getLogger("raccoon.dataframe").addHandler(fh)

    attr_entries = {}
    for attr in ["dark red", "dark green", "dark blue"]:
        attr_entries[attr.split()[1]] = PaletteEntry(
            mono="white", foreground=attr, background="black"
        )
    entries = DataTable.get_palette_entries(user_entries=attr_entries)
    palette = Palette("default", **entries)

    COLUMNS = [
        # DataTableColumn("uniqueid", width=10, align="right", padding=1),
        DataTableColumn(
            "foo",
            label="Foo",
            width=4,
            align="right",
            sort_key=lambda v: (v is None, v),
            attr="color",
            padding=0,
            footer_fn=lambda column, values: sum(v for v in values if v is not None),
        ),
        DataTableColumn(
            "bar",
            label="Bar",
            width=10,
            align="right",
            sort_reverse=True,
            sort_icon=False,
            padding=1,
        ),  # margin=5),
        DataTableColumn("baz", label="Baz!", width=("weight", 1)),
        DataTableColumn(
            "qux",
            label=urwid.Text([("red", "q"), ("green", "u"), ("blue", "x")]),
            width=5,
            hide=True,
        ),
        # DataTableColumn("empty", label="empty", width=5),
    ]

    class ExampleDataTable(DataTable):

        columns = COLUMNS[:]

        index = "index"

        def __init__(self, num_rows=10, *args, **kwargs):
            self.num_rows = num_rows
            # indexes = random.sample(range(self.num_rows*2), num_rows)
            self.randomize_query_data()
            self.last_rec = len(self.query_data)
            super(ExampleDataTable, self).__init__(*args, **kwargs)

        def randomize_query_data(self):
            indexes = list(range(self.num_rows))
            self.query_data = [
                self.random_row(indexes[i])
                for i in range(self.num_rows)
                # self.random_row(i) for i in range(self.num_rows)
            ]
            random.shuffle(self.query_data)

        def random_row(self, uniqueid):
            return dict(
                uniqueid=uniqueid,
                foo=random.choice(list(range(100)) + [None] * 20),
                bar=(random.uniform(0, 1000) if random.randint(0, 5) else None),
                baz=(
                    "".join(
                        random.choice(
                            string.ascii_uppercase
                            + string.ascii_lowercase
                            + string.digits
                            + " " * 10
                        )
                        for _ in range(random.randint(5, 20))
                    )
                    if random.randint(0, 5)
                    else None
                ),
                qux=urwid.Text([("red", "1"), ("green", "2"), ("blue", "3")]),
                xyzzy=(
                    "%0.1f" % (random.uniform(0, 100)) if random.randint(0, 5) else None
                ),
                baz_len=lambda r: len(r["baz"]) if r.get("baz") else 0,
                # xyzzy = random.randint(10, 100),
                empty=None,
                a=dict(b=dict(c=random.randint(0, 100))),
                d=dict(e=dict(f=random.randint(0, 100))),
                color=["red", "green", "blue"][random.randrange(3)],
            )

        def query(self, sort=(None, None), offset=None, limit=None, load_all=False):

            logger.info("query: offset=%s, limit=%s, sort=%s" % (offset, limit, sort))
            try:
                sort_field, sort_reverse = sort
            except:
                sort_field = sort
                sort_reverse = None

            if sort_field:
                kwargs = {}
                kwargs["key"] = lambda x: (
                    x.get(sort_field) is None,
                    x.get(sort_field),
                    x.get(self.index),
                )
                if sort_reverse:
                    kwargs["reverse"] = sort_reverse
                self.query_data.sort(**kwargs)
            if offset is not None:
                if not load_all:
                    start = offset
                    end = offset + limit
                    r = self.query_data[start:end]
                    logger.debug("%s:%s (%s)" % (start, end, len(r)))
                else:
                    r = self.query_data[offset:]
            else:
                r = self.query_data

            for d in r:
                yield d

        def query_result_count(self):
            return self.num_rows

        def keypress(self, size, key):
            if key == "meta r":
                self.randomize_query_data()
                self.reset(reset_sort=True)
            if key == "ctrl r":
                self.reset(reset_sort=True)
            if key == "ctrl d":
                self.log_dump(20)
            if key == "meta d":
                self.log_dump(20, columns=["foo", "baz"])
            if key == "ctrl f":
                self.focus_position = 0
            elif key == "ctrl t":
                # logger.info(self.get_row(0)[0])
                logger.info(self.selection.data["bar"])
            elif key == "meta i":
                logger.info(
                    "foo %s, baz: %s"
                    % (self.selection.get("foo"), self.selection.get("baz"))
                )
            elif (
                self.ui_sort
                and key.isdigit()
                and int(key) - 1 in range(len(self.columns))
            ):
                col = int(key) - 1
                self.sort_by_column(col, toggle=True)
            elif key == "ctrl l":
                self.load("test.json")
            elif key == "ctrl s":
                self.save("test.json")
            elif key == "0":
                # self.sort_by_column(self.index, toggle=True)
                self.sort_sorindex()
            elif key == "a":
                self.add_row(self.random_row(self.last_rec))
                self.last_rec += 1
            elif key == "A":
                self.add_row(self.random_row(self.last_rec), sort=False)
                self.last_rec += 1
            elif key == "d":
                if len(self):
                    self.delete_rows(self.df.index[self.focus_position])
            elif key == "meta a":
                name = "".join(
                    random.choice(
                        string.ascii_uppercase + string.lowercase + string.digits
                    )
                    for _ in range(5)
                )
                data = [
                    "".join(
                        random.choice(
                            string.ascii_uppercase + string.lowercase + string.digits
                        )
                        for _ in range(5)
                    )
                    for _ in range(len(self))
                ]
                col = DataTableColumn(name, label=name, width=6, padding=0)
                self.add_columns(col, data=data)
            elif key == "r":
                self.set_columns(COLUMNS)
            elif key == "t":
                self.toggle_columns("qux")
            elif key == "T":
                self.toggle_columns(["foo", "baz"])
            elif key == "D":
                self.remove_columns(len(self.columns) - 1)
            elif key == "f":
                self.apply_filters([lambda x: x["foo"] > 20, lambda x: x["bar"] < 800])
            elif key == "F":
                self.clear_filters()
            elif key == ".":
                self.toggle_details()
            elif key == "s":
                self.selection.set_attr("red")
            elif key == "S":
                self.selection.clear_attr("red")
            elif key == "k":
                self.selection[2].set_attr("red")
            elif key == "K":
                self.selection[2].clear_attr("red")
            elif key == "u":
                logger.info(self.footer.values)
            elif key == "shift left":
                self.cycle_sort_column(-1)
            elif key == "shift right":
                self.cycle_sort_column(1)
            elif self.ui_sort and key == "shift up":
                self.sort_by_column(reverse=True)
            elif self.ui_sort and key == "shift down":
                self.sort_by_column(reverse=False)
            elif key == "shift end":
                self.load_all()
                # self.listbox.focus_position = len(self) -1
            elif key == "ctrl up":
                if self.focus_position > 0:
                    self.swap_rows(self.focus_position, self.focus_position - 1, "foo")
                    self.focus_position -= 1
            elif key == "ctrl down":
                if self.focus_position < len(self) - 1:
                    self.swap_rows(self.focus_position, self.focus_position + 1, "foo")
                    self.focus_position += 1
            else:
                return super(ExampleDataTable, self).keypress(size, key)

    class ExampleDataTableBox(urwid.WidgetWrap):
        def __init__(self, *args, **kwargs):

            self.table = ExampleDataTable(*args, **kwargs)
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
            super(ExampleDataTableBox, self).__init__(self.box)

    def detail_fn(data):

        return urwid.Padding(
            urwid.Columns(
                [
                    ("weight", 1, data.get("qux")),
                    ("weight", 1, urwid.Text(str(data.get("baz_len")))),
                    ("weight", 2, urwid.Text(str(data.get("xyzzy")))),
                ]
            )
        )

    tablebox = ExampleDataTableBox(
        1000,
        index="uniqueid",
        detail_fn=detail_fn,
        detail_column="bar",
        sort_refocus=True,
        sort_icons=False,
        with_scrollbar=True,
        border=(1, "\N{VERTICAL LINE}", "blue"),
        padding=3,
        with_footer=True,
    )

    def global_input(key):
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()
        else:
            return False

    old_signal_keys = screen.tty_signal_keys()
    l = list(old_signal_keys)
    l[0] = "undefined"
    l[3] = "undefined"
    l[4] = "undefined"
    screen.tty_signal_keys(*l)

    main = urwid.MainLoop(
        urwid.Frame(urwid.Filler(tablebox)),
        palette=palette,
        screen=screen,
        unhandled_input=global_input,
    )

    try:
        main.run()
    finally:
        screen.tty_signal_keys(*old_signal_keys)


if __name__ == "__main__":
    main()
