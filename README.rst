pingtop
=======

.. image:: https://github.com/laixintao/pingtop/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/laixintao/pingtop/actions/workflows/ci.yml
   :alt: CI

``pingtop`` is a fast, keyboard-first multi-host ping monitor for people who live in the terminal.
Point it at a few hosts, a whole subnet, or a host list, and get a live Textual dashboard with RTT trends, loss stats, sortable columns, and per-host drill-down details.

It is built for the moment when ``ping`` is too small, dashboards are too heavy, and you just want to see what your network is doing right now.

.. image:: https://asciinema.org/a/886189.svg
   :target: https://asciinema.org/a/886189
   :alt: asciinema demo

Why ``pingtop``
---------------

- Monitor many hosts at once in a single live TUI
- Spot latency spikes instantly with inline RTT trend bars
- Sort by host, IP, RTT, avg, max, stddev, loss, state, or trend
- Inspect a selected host in a dedicated details panel
- Add, edit, delete, pause, and reset hosts without restarting the session
- Load targets from CLI args, CIDR ranges, or a hosts file
- Export the final snapshot to JSON or CSV
- Print a clean colored summary on exit
- Use raw ICMP directly instead of shelling out to ``ping``

Feature Highlights
------------------

**Live network view**

- Real-time host table with RTT, min/avg/max, stddev, loss, state, and trend columns
- Responsive layout that keeps the table useful on both wide and narrow terminals
- Stable numeric column widths, so values stay easy to scan while data updates

**Designed for triage**

- One-key sorting across every important signal
- A details panel with an expanded RTT graph for the selected host
- Global status strip showing active hosts, paused hosts, errors, sent packets, and total loss

**Built for real sessions**

- Add or fix targets in place instead of restarting
- Pause a noisy host, pause everything, or reset stats when you want a clean measurement window
- Deduplicate repeated hosts automatically when combining CLI args and ``--hosts-file``

Install
-------

Requirements:

- Python 3.10+

::

   python -m pip install pingtop

After installation, run it directly:

::

   pingtop 1.1.1.1 8.8.8.8

Quick Start
-----------

Monitor a few public resolvers:

::

   pingtop 1.1.1.1 8.8.8.8 9.9.9.9

Use a faster sampling interval:

::

   pingtop 1.1.1.1 8.8.8.8 --interval 0.2 --timeout 0.5

Expand a CIDR block into usable hosts automatically:

::

   pingtop 10.22.76.19/30

Load hosts from a file:

::

   pingtop --hosts-file hosts.txt

``hosts.txt`` is newline-delimited. Blank lines and lines starting with ``#`` are ignored.

Common Workflows
----------------

Monitor a host list and export the final snapshot:

::

   pingtop --hosts-file hosts.txt --export snapshots/session.json

Write CSV explicitly:

::

   pingtop 1.1.1.1 8.8.8.8 --export snapshots/session.csv

Enable debug logging while troubleshooting:

::

   pingtop 10.0.0.1 10.0.0.2 --log-file pingtop.log --log-level debug

Disable the exit summary when you only want the TUI:

::

   pingtop 1.1.1.1 --no-summary

CLI Options
-----------

::

   Usage: pingtop [OPTIONS] [HOSTS]...

   Options:
     -i, --interval FLOAT            ping interval in seconds
     -t, --timeout FLOAT             timeout in seconds
     -s, --packet-size INTEGER       ICMP payload size in bytes
     --hosts-file FILE               newline-delimited host list
     --summary / --no-summary        print a colored summary on exit
     --export FILE                   export final snapshot
     --export-format [json|csv]      override export format
     --log-file FILE                 write logs to a file
     --log-level [debug|info|warning|error|critical]
     -h, --help

Keyboard Shortcuts
------------------

Session control:

- ``a`` add a host
- ``e`` edit the selected host
- ``d`` delete the selected host
- ``space`` pause or resume the selected host
- ``p`` pause or resume all hosts
- ``r`` reset statistics for the selected host
- ``ctrl+r`` reset statistics for all hosts
- ``i`` show or hide the details panel
- ``tab`` switch focus between the table and details panel
- ``h`` or ``?`` open help
- ``q`` quit

Sorting:

- ``H`` host
- ``G`` resolved IP
- ``S`` sequence
- ``R`` last RTT
- ``I`` min RTT
- ``A`` avg RTT
- ``M`` max RTT
- ``T`` stddev
- ``L`` lost packets
- ``P`` loss percentage
- ``U`` state
- ``W`` trend

Press the same sort key again to reverse the order.

What You Get On Exit
--------------------

By default, ``pingtop`` prints a compact colored summary with:

- overall status
- total hosts, tx, rx, and loss percentage
- lossy or down hosts
- top issues worth investigating first

If you export a snapshot, the file includes session config, aggregate stats, and per-host results.

Permissions
-----------

``pingtop`` uses ICMP sockets directly and does **not** require ``sudo`` or root privileges on modern systems.

- **macOS** — unprivileged ICMP is supported out of the box.
- **Linux** — most distributions ship with a permissive ``net.ipv4.ping_group_range`` by default.

If you do hit a permission error on Linux, check the current value:

::

   cat /proc/sys/net/ipv4/ping_group_range

Then widen the allowed range so your user or group can open ICMP sockets:

::

   sudo sysctl -w net.ipv4.ping_group_range='0 1001'

Development
-----------

You may need to set `poetry config virtualenvs.in-project true` for the included vscode launch.json to work.

::

   poetry install
   poetry run pytest
   poetry run ruff check .
   poetry run mypy src

Credits
-------

- The raw ICMP implementation is derived from the original ``pingtop`` project.
- The TUI is built with `Textual <https://textual.textualize.io/>`__.

If ``pingtop`` earns a place in your toolbox, star the repo.
