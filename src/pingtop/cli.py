from __future__ import annotations

import ipaddress
import logging
from pathlib import Path

import click

from pingtop.app import PingTopApp
from pingtop.engine.icmp import IcmpEngine
from pingtop.exporters import export_snapshot
from pingtop.models import ExportFormat, SessionConfig
from pingtop.session import PingSession, infer_export_format
from pingtop.summary import render_summary

def _configure_logging(log_level: str, log_file: str | None) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        filename=log_file,
        filemode="a",
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

def _read_hosts_file(path: str | None) -> list[str]:
    if not path:
        return []
    file_path = Path(path)
    return [
        line.strip()
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

def _merge_hosts(hosts: tuple[str, ...], hosts_file: str | None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for host in [*hosts, *_read_hosts_file(hosts_file)]:
        for expanded_host in _expand_host(host):
            key = expanded_host.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(expanded_host)
    return merged

def _expand_host(host: str) -> list[str]:
    clean_host = host.strip()
    if not clean_host:
        return []
    if "/" not in clean_host:
        return [clean_host]
    try:
        network = ipaddress.ip_network(clean_host, strict=False)
    except ValueError as exc:
        raise click.ClickException(f"Invalid network or host: {clean_host}") from exc
    return [str(address) for address in network.hosts()]

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("hosts", nargs=-1)
@click.option("-i", "--interval", type=float, default=1.0, show_default=True)
@click.option("-t", "--timeout", type=float, default=1.0, show_default=True)
@click.option("-s", "--packet-size", type=int, default=56, show_default=True)
@click.option("--hosts-file", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--summary/--no-summary", default=True)
@click.option("--export", "export_path", type=click.Path(dir_okay=False, path_type=str))
@click.option(
    "--export-format",
    type=click.Choice([fmt.value for fmt in ExportFormat], case_sensitive=False),
)
@click.option("--log-file", type=click.Path(dir_okay=False, path_type=str))
@click.option(
    "--log-level",
    type=click.Choice(["debug", "info", "warning", "error", "critical"], case_sensitive=False),
    default="info",
    show_default=True,
)
def main(
    hosts: tuple[str, ...],
    interval: float,
    timeout: float,
    packet_size: int,
    hosts_file: str | None,
    summary: bool,
    export_path: str | None,
    export_format: str | None,
    log_file: str | None,
    log_level: str,
) -> None:
    merged_hosts = _merge_hosts(hosts, hosts_file)
    if not merged_hosts:
        raise click.ClickException("Provide at least one host or --hosts-file.")
    if interval <= 0 or timeout <= 0:
        raise click.ClickException("--interval and --timeout must be greater than zero.")
    if packet_size <= 0:
        raise click.ClickException("--packet-size must be greater than zero.")

    resolved_export_format = None
    if export_path:
        try:
            resolved_export_format = infer_export_format(export_path, export_format)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    elif export_format:
        raise click.ClickException("--export-format requires --export.")

    _configure_logging(log_level, log_file)
    config = SessionConfig(
        interval=interval,
        timeout=timeout,
        packet_size=packet_size,
        summary=summary,
        export_path=export_path,
        export_format=resolved_export_format,
        log_file=log_file,
        log_level=log_level,
    )
    session = PingSession(config=config, targets=merged_hosts)
    app = PingTopApp(session=session, engine=IcmpEngine())
    app.run()

    snapshot = session.snapshot()
    exit_code = 0
    if summary:
        click.echo(render_summary(snapshot, color=True), color=True)
    if export_path and resolved_export_format:
        try:
            export_snapshot(snapshot, export_path, resolved_export_format)
        except OSError as exc:
            click.echo(f"Export failed: {exc}", err=True)
            exit_code = 2
    raise SystemExit(exit_code)
