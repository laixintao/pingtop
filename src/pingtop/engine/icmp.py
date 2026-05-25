from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
import struct
import time

from pingtop.models import PingResult

ICMP_ECHO_REQUEST = 8
ICMP_HEADER_SIZE = 8
ICMP_ID_HEADER_OFFSET = 4

def checksum(source_bytes: bytes) -> int:
    total = 0
    count_to = (len(source_bytes) // 2) * 2
    for count in range(0, count_to, 2):
        total += source_bytes[count + 1] * 256 + source_bytes[count]
        total &= 0xFFFFFFFF
    if count_to < len(source_bytes):
        total += source_bytes[-1]
        total &= 0xFFFFFFFF
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    answer = ~total & 0xFFFF
    return answer >> 8 | ((answer << 8) & 0xFF00)

async def receive_one_ping(
        loop: asyncio.AbstractEventLoop,
        sock: socket.socket,
        packet_id: int,
        timeout: float) -> float | None:
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        try:
            received_packet = await asyncio.wait_for(loop.sock_recv(sock, 1024), remaining)
        except TimeoutError:
            return None

        time_received = time.time()

        # Determine whether we received a full IPv4 packet (with IP header)
        # or a raw ICMP packet (no IP header) as produced by SOCK_DGRAM on some systems.
        #
        # IPv4 first byte:  4 bits Version | 4 bits IHL
        # - If first_nibble (version) > 0 => looks like an IPv4/IPv6 packet (expect IP header)
        # - If first byte == 0 (0 for Echo Reply) => not an IP header
        #
        #  IPv4 packet header:
        #
        #  +---------------------+-------------------------------------------+
        #  | Byte 0              | Byte 1                                    |
        #  | V(4) | IHL(4)       | Type of Service                            |
        #  +---------------------+-------------------------------------------+
        #  | Bytes 2-3: Total Length                                   |
        #  +------------------------------------------------------------+
        #  | ... IP header (IHL*4 bytes) ...                            |
        #  +------------------------------------------------------------+
        #  | ICMP header starts here (offset = IHL*4)                   |
        #  +------------------------------------------------------------+
        #
        #  ICMP packet (no IP header):
        #
        #  +------------------------------------------------------------+
        #  | Byte 0: Type (e.g., 0 = Echo Reply)                        |
        #  +------------------------------------------------------------+
        #  | Byte 1: Code                                               |
        #  +------------------------------------------------------------+
        #  | Bytes 2-3: Checksum                                        |
        #  +------------------------------------------------------------+
        #  | Bytes 4-5: Identifier (packet_id)                          |
        #  +------------------------------------------------------------+
        #  | Bytes 6-7: Sequence number                                 |
        #  +------------------------------------------------------------+
        #  | Bytes 8-: Payload (we store a 'double' timestamp at offset 0 of payload)
        #  +------------------------------------------------------------+

        # get IP header length (IHL) in 32-bit words -> bytes = IHL * 4
        icmp_header_offset = (received_packet[0] & 0x0F) * 4

        # Sanity: Ensure we at least have ICMP header (8 bytes) + timestamp (double)
        if len(received_packet) < (icmp_header_offset + ICMP_HEADER_SIZE + struct.calcsize("d")):
            continue

        # Sanity: Ensure the checksum checks out before further parsing
        if checksum(received_packet[icmp_header_offset:]) != 0:
            continue

        # Strip IP header if present (icmp_header_offset == 0 when no IP header)
        this_packet_id = struct.unpack_from("!H",
                                             received_packet,
                                             offset=(icmp_header_offset + ICMP_ID_HEADER_OFFSET))[0]
        if this_packet_id == packet_id:
            # unpack the timestamp
            time_sent = struct.unpack_from("d",
                                            received_packet,
                                            offset=(icmp_header_offset + ICMP_HEADER_SIZE))[0]
            return time_received - time_sent

async def send_one_ping(
    loop: asyncio.AbstractEventLoop,
    sock: socket.socket,
    resolved_ip: str,
    packet_id: int,
    packet_size: int,
) -> None:
    # payload: timestamp + padding
    bytes_size = struct.calcsize("d")
    data = struct.pack("d", time.time()) + (packet_size - bytes_size) * b"Q"

    # initial header with zero checksum
    # sequence hard coded to 1 since we're not re-using the socket
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, packet_id, 1)
    my_checksum = checksum(header + data)
    header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, my_checksum, packet_id, 1)
    return await loop.sock_sendall(sock, header + data)

class IcmpEngine:
    async def ping_once(
        self, target: str, timeout: float, packet_size: int, flag: int
    ) -> PingResult:
        loop = asyncio.get_running_loop()
        try:
            resolved_ip = await self._resolve_target(loop, target)
        except socket.gaierror as exc:
            return PingResult(success=False, error_message=str(exc))

        icmp_proto = socket.getprotobyname("icmp")
        packet_id = None
        RTT = None
        try:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp_proto)
                packet_id = (os.getpid() & 0xFF00) | (flag & 0x00FF)
            except PermissionError:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, icmp_proto)
            sock.setblocking(False)
            # AF_INET requires dest port but since we're sending ICMP it doesn't matter
            sock.connect((resolved_ip, 0))
            # Using unprivileged SOCK_DGRAM the kernel will validate/overwrite the ICMP header
            # This means we do not control the packet_id and it will be set to the port used
            if packet_id is None:
                _, port = sock.getsockname()
                packet_id = port
            await send_one_ping(loop, sock, resolved_ip, packet_id, packet_size)
            RTT = await receive_one_ping(loop, sock, packet_id, timeout)
        except OSError as exc:
            return PingResult(success=False, resolved_ip=resolved_ip, error_message=str(exc))
        finally:
            sock.close()

        if RTT is None:
            return PingResult(success=False, resolved_ip=resolved_ip)
        return PingResult(success=True, rtt_ms=RTT * 1000, resolved_ip=resolved_ip)

    async def _resolve_target(
        self, loop: asyncio.AbstractEventLoop, target: str
    ) -> str:
        try:
            return str(ipaddress.ip_address(target))
        except ValueError:
            pass
        infos = await loop.getaddrinfo(
            target,
            None,
            family=socket.AF_INET,
            type=socket.SOCK_DGRAM,
        )
        if not infos:
            raise socket.gaierror(f"Unable to resolve {target}")
        return str(infos[0][4][0])
