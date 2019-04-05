# -*- coding: utf-8 -*-

import time
import random
import struct
import select
import socket


# Credit: https://gist.github.com/pyos/10980172
def chk(data):
    x = sum(x << 8 if i % 2 else x for i, x in enumerate(data)) & 0xFFFFFFFF
    x = (x >> 16) + (x & 0xFFFF)
    x = (x >> 16) + (x & 0xFFFF)
    return struct.pack("<H", ~x & 0xFFFF)


# From the same gist commented above, with minor modified.
def ping(addr, timeout=1, udp=True, number=1, data=b""):
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM if udp else socket.SOCK_RAW,
        socket.IPPROTO_ICMP,
    ) as conn:
        payload = struct.pack("!HH", random.randrange(0, 65536), number) + data

        conn.connect((addr, 80))
        conn.sendall(b"\x08\0" + chk(b"\x08\0\0\0" + payload) + payload)
        start = time.time()

        while select.select([conn], [], [], max(0, start + timeout - time.time()))[0]:
            data = conn.recv(65536)
            if data[20:] == b"\0\0" + chk(b"\0\0\0\0" + payload) + payload:
                return time.time() - start


if __name__ == "__main__":
    for i in range(100):
        print(i, ping("110.75.129.5") * 1000)
