# pingtop [![CircleCI](https://circleci.com/gh/laixintao/pingtop.svg?style=svg)](https://circleci.com/gh/laixintao/pingtop)

Ping multiple servers and show the result in a top like terminal UI.

[![asciicast](https://asciinema.org/a/onbBCmHzhltau7iqButUGx6yu.svg)](https://asciinema.org/a/onbBCmHzhltau7iqButUGx6yu)

## Install

```
pip install pingtop
```

## Usage

Then ping mutiple server:
```
pingtop baidu.com google.com twitter.com
```

This project is using [click](https://click.palletsprojects.com/en/7.x/). Check help info with `pingtop -h`.

```
~ pingtop --help
Usage: pingtop [OPTIONS] [HOST]...

Options:
  -s, --packetsize INTEGER        specify the number of data bytes to be sent.
                                  The default is 56, which translates into 64
                                  ICMP data bytes when combined with the 8
                                  bytes of ICMP header data.  This option
                                  cannot be used with ping sweeps.  [default:
                                  56]
  -l, --logto PATH
  -v, --log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
  --help                          Show this message and exit.
```

## Why do I get `Permission denied` ?

We use ICMP socket to send ping packet without `sudo` (See [this post](https://blog.lilydjwg.me/2013/10/29/non-privileged-icmp-ping.41390.html) by lilydjwg(in Chinese)), however, who(which group) can use this feature is controled by a kernel parameter: `net.ipv4.ping_group_range`.

```
cat /proc/sys/net/ipv4/ping_group_range

1    0
```

The default value is `1 0`, this means the whose group number from 1 to 0 can use this feature(which means nobody can use this), so you get a Permission denied .

To fix this, change this variable to a proper range include your group id, like this:

```
[vagrant@centos7 pingtop]$ id
uid=1000(vagrant) gid=1000(vagrant) groups=1000(vagrant) context=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023

[vagrant@centos7 pingtop]$ sudo sysctl -w net.ipv4.ping_group_range='0 1001'
net.ipv4.ping_group_range = 0 1001
```

## Credits

- For the credits of ping.py's implementation please refer [ping.py](./ping.py).
- The UI was built on [panwid](https://github.com/tonycpsu/panwid) thanks to @tonycpsu.
- @[gzxultra](https://github.com/gzxultra) helped to solve the permission issues.
