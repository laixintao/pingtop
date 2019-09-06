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
from panwid.datatable import DataTableColumn, DataTable
from urwid_utils.palette import PaletteEntry, Palette
import os
import random
import string

logger = logging.getLogger(__name__)

WAIT_TIME = 1  # seconds
SOCKET_TIMEOUT = 1
hosts = {}
event = threading.Event()
screen_lock = threading.Lock()
sort_keys = {
    "H": "host",
    "S": "seq",
    "R": "real_rtt",
    "I": "min_rtt",
    "A": "avg_rtt",
    "M": "max_rtt",
    "T": "std",
    "L": "lost",
}
current_sort_column = "real_rtt"
sort_reverse = False
UNICODE_BLOCKS = "▁▂▃▄▅▆▇█"


screen = urwid.raw_display.Screen()
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
        width=8,
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
        width=8,
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
        "lostp", label="LOSS%", width=6, align="right", sort_icon=False, padding=0
    ),
    DataTableColumn("stat", label="Stat", align="left", sort_icon=False, padding=0),
]


def get_last_column_width():
    screen_width = screen.get_cols_rows()[0]
    previous_all_column_width = sum(col.width_with_padding() for col in COLUMNS)
    last_column_width = screen_width - previous_all_column_width - 10
    logger.info(f"Get last_column_width = {last_column_width}.")
    return last_column_width


def get_palette():
    attr_entries = {}
    for attr in ["dark red", "dark green", "dark blue"]:
        attr_entries[attr.split()[1]] = PaletteEntry(
            mono="white", foreground=attr, background="black"
        )
    entries = DataTable.get_palette_entries(user_entries=attr_entries)
    palette = Palette("default", **entries)
    return palette


def rerender_table(loop, table):
    """
    Rerender table box from its data, and make loop redraw screen.
    Not thread safe.
    """
    # save focused host
    position = table.focus_position
    focus_host = ""
    try:
        row = table.get_row_by_position(position)
    except IndexError:
        pass
    else:
        focus_host = row.values["host"]

    # restore sort column
    table.reset(reset_sort=True)
    table.sort_by_column(current_sort_column, sort_reverse)

    # restore focused host
    for r in table.filtered_rows:
        row = table.get_row_by_position(r)
        if row.values["host"] == focus_host:
            table.set_focus(r)
            break
    loop.draw_screen()


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
    def __init__(self, packetsize, *args, **kwargs):
        self.table = PingDataTable(*args, **kwargs)
        urwid.connect_signal(
            self.table,
            "select",
            lambda source, selection: logger.info("selection: %s" % (selection)),
        )
        banner = urwid.Text("Pingtop", align="center")
        key_label = "[Sort Key] {}".format(
            " ".join("{}: {}".format(key, col) for key, col in sort_keys.items())
        )
        quit_key_label = "[Quit key] Q"
        packet_size_line = f"Sending ICMP packet with {packetsize} data bytes."
        self.pile = urwid.Pile(
            [
                ("pack", banner),
                ("pack", urwid.Text(packet_size_line)),
                ("pack", urwid.Text(key_label)),
                ("pack", urwid.Text(quit_key_label)),
                ("pack", urwid.Divider("\N{HORIZONTAL BAR}")),
                ("weight", 1, self.table),
            ]
        )
        super().__init__(self.pile)


def global_input(key):
    global current_sort_column
    global sort_reverse

    # keyboard input only
    logger.info(f"[KEY]: {key}")
    if not isinstance(key, str):
        return

    if key in ("q", "Q", "^C"):
        event.clear()
        raise urwid.ExitMainLoop()
    elif key.upper() in sort_keys:
        upper_key = key.upper()
        sort_column = sort_keys[upper_key]
        if current_sort_column == sort_column:
            sort_reverse = not sort_reverse
        else:
            sort_reverse = False
            current_sort_column = sort_column
    else:
        return False


def forever_ping(dest, index_flag, packetsize, tablebox, mainloop):
    global hosts
    global event
    last_column_width = get_last_column_width()
    try:
        dest_ip = socket.gethostbyname(dest)
    except socket.gaierror as e:
        hosts[dest]["error"] = e
        hosts[dest]["ip"] = "Unknown"
        with event.is_set() and screen_lock:
            rerender_table(mainloop, tablebox.table)
        return

    dest_attr = hosts[dest]

    dest_attr["ip"] = dest_ip
    dest_attr.setdefault("lost", 0)
    dest_attr.setdefault("lostp", "0%")
    dest_attr.setdefault("seq", 0)
    dest_attr.setdefault("real_rtt", SOCKET_TIMEOUT * 1000)
    dest_attr.setdefault("min_rtt", SOCKET_TIMEOUT * 1000)
    dest_attr.setdefault("max_rtt", SOCKET_TIMEOUT * 1000)
    dest_attr.setdefault("avg_rtt", SOCKET_TIMEOUT * 1000)
    dest_attr.setdefault("std", 0)
    dest_attr.setdefault("stat", "")
    rtts = dest_attr.setdefault("rtts", [])

    while event.is_set():
        logging.info(f"ping {dest}, {index_flag}")
        delay = do_one(dest, SOCKET_TIMEOUT, packetsize, index_flag)
        logging.info(f"[Done]ping {dest}, {index_flag} rtt={delay}")
        with screen_lock:
            dest_attr["seq"] += 1
            if delay is None:
                dest_attr["lost"] += 1
                dest_attr["lostp"] = "{0:.0%}".format(
                    dest_attr["lost"] / dest_attr["seq"]
                )
                block_mark = " "
                sleep_before_next_ping = WAIT_TIME
            else:
                delay_ms = int(delay * 1000)
                rtts.append(delay_ms)
                dest_attr["real_rtt"] = delay_ms
                dest_attr["min_rtt"] = min(dest_attr["rtts"])
                dest_attr["max_rtt"] = max(dest_attr["rtts"])
                dest_attr["avg_rtt"] = sum(dest_attr["rtts"]) / dest_attr["seq"]
                if len(rtts) >= 2:
                    dest_attr["std"] = float("%2.1f" % (statistics.stdev(rtts)))

                block_mark = UNICODE_BLOCKS[min(delay_ms // 30, 7)]
                sleep_before_next_ping = WAIT_TIME - delay
            dest_attr["stat"] = (dest_attr["stat"] + block_mark)[-last_column_width:]

        try:
            rerender_table(mainloop, tablebox.table)
        except AssertionError:
            break
        logger.info(f"{dest}({dest_ip})Sleep for seconds {sleep_before_next_ping}")
        time.sleep(max(0, sleep_before_next_ping))


def _raise_error(future):
    exp = future.exception()
    if exp:
        logging.exception(exp)


PACKETSIZE_HELP = "specify the number of data bytes to be sent.  The default is 56, which translates into 64 ICMP data bytes when combined with the 8 bytes of ICMP header data.  This option cannot be used with ping sweeps."


def config_logger(level, logfile):
    global logger
    _level = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }[level]
    logging.basicConfig(
        filename=logfile,
        filemode="a",
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        level=_level,
    )
    logger = logging.getLogger(__name__)
    return logger


def ping_statistics(data):
    """
    Render result statistics
    :return: str result string
    """
    TEMPLATE = """--- {hostname} ping statistics ---
{packet} packets transmitted, {packet_received} packets received, {packet_lost:.1f}% packet loss"""
    RTT_TEMPLATE = """\nround-trip min/avg/max/stddev = {min:3.2f}/{avg:3.2f}/{max:3.2f}/{stddev:3.2f} ms"""
    ERROR_TEMPLATE = """--- {hostname} ping statistics ---
ping: cannot resolve {hostname}: Unknown host"""
    results = []
    for hostname, value in data.items():
        if value.get("error"):
            # I could use PEP572 here
            results.append(ERROR_TEMPLATE.format(hostname=hostname))
            continue
        rtts = value["rtts"]
        if value["seq"] == 0:
            packet, packet_received, packet_lost = 0, 0, 0
        else:
            packet = value["seq"]
            packet_received = int(value["seq"]) - int(value["lost"])
            packet_lost = value["lost"] / value["seq"] * 100

        packets_info = TEMPLATE.format(
            hostname=hostname,
            packet=packet,
            packet_received=packet_received,
            packet_lost=packet_lost,
        )
        rtt_info = ""
        if rtts:
            stdev = 0
            if len(rtts) > 2:
                stdev = statistics.stdev(value["rtts"])
            rtt_info = RTT_TEMPLATE.format(
                min=min(value["rtts"]),
                avg=sum(value["rtts"]) / value["seq"],
                max=max(value["rtts"]),
                stddev=stdev,
            )
        results.append(packets_info + rtt_info)
    return "\n".join(results)


@click.command()
@click.argument("host", nargs=-1)
@click.option(
    "--packetsize", "-s", type=int, default=56, show_default=True, help=PACKETSIZE_HELP
)
@click.option("--logto", "-l", type=click.Path(), default=None)
@click.option(
    "--log-level",
    "-v",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="DEBUG",
)
@click.option(
    "--summary/--no-summary",
    default=True,
    help="Weather to print BSD compatible summary.",
)
def multi_ping(host, packetsize, logto, log_level, summary):
    global hosts
    if logto:
        config_logger(log_level, logto)
    hosts = {h: {} for h in host}
    logger.info(f"Hosts: {hosts}")
    hosts_num = len(hosts)

    if (hosts_num) == 0:
        raise click.BadParameter("Hosts were not specified.")

    # update the HOST column width to fit max length host
    max_host_length = max([len(host) for host in hosts] + [9]) + 2
    COLUMNS[0].width = max_host_length if max_host_length < 40 else 40
    # start the UI loop
    tablebox = MainBox(
        packetsize,
        1000,
        index="uniqueid",
        sort_refocus=True,
        sort_icons=True,
        with_scrollbar=True,
        border=(1, "\N{VERTICAL LINE}", "blue"),
        padding=3,
        with_footer=False,
        ui_sort=False,
    )
    mainloop = urwid.MainLoop(
        tablebox, palette=get_palette(), screen=screen, unhandled_input=global_input
    )

    # open threadpool to ping
    logger.info(f"Open ThreadPoolExecutor with max_workers={hosts_num}.")
    pool = ThreadPoolExecutor(max_workers=hosts_num)
    event.set()
    for index, host in zip(range(len(hosts)), hosts):
        future = pool.submit(forever_ping, host, index, packetsize, tablebox, mainloop)
        future.add_done_callback(_raise_error)

    # Go!
    mainloop.run()

    if summary:
        click.echo(ping_statistics(hosts))


if __name__ == "__main__":
    multi_ping()
