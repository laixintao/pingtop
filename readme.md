# pingtop

Ping multiple servers and show the result in a top like terminal UI.

[![asciicast](https://asciinema.org/a/2XmzAGzbLtT9DU9tTZYl61W7y.svg)](https://asciinema.org/a/2XmzAGzbLtT9DU9tTZYl61W7y)

## Usage

```
pip install pingtop
```

Then ping mutiple server:
```
sudo pingtop baidu.com google.com twitter.com
```

Why does it need `sudo` ? see [here](https://github.com/laixintao/pingtop/issues/5)

This project is using [click](https://click.palletsprojects.com/en/7.x/). Check helo info with `pingtop -h`.

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
