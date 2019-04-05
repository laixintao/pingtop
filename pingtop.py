# -*- coding: utf-8 -*-

import click
import threading
from concurrent.futures import ThreadPoolExecutor
from ping import do_one
import time


hosts = {"baidu.com": {}, "alipay.com": {}}
event = threading.Event()


def forever_ping(dest, index_flag):
    global hosts
    global event
    while event.is_set():
        delay = do_one(dest, 1, 64, index_flag)
        print(dest, "\t", delay * 1000)
        if delay is None:
            hosts[dest].setdefault("lost", 0)
            hosts[dest]["lost"] += 1
        else:
            hosts[dest].setdefault("rtts", []).append(delay)
        time.sleep(1)


@click.command()
def multi_ping():
    global hosts
    try:
        pool = ThreadPoolExecutor(max_workers=len(hosts))
        event.set()
        for index, host in zip(range(len(hosts)), hosts):
            last_future = pool.submit(forever_ping, host, index)
        last_future.result()
    except KeyboardInterrupt:
        event.clear()
        print("shutdown!")
        for host in hosts:
            print(host)
            print(host, min(hosts[host]["rtts"]))
    finally:
        pool.shutdown(wait=False)
        print("shuted!")


if __name__ == "__main__":
    multi_ping()
