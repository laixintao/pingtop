from __future__ import annotations

from click.testing import CliRunner

from pingtop import cli
from pingtop.models import PingResult


def test_cli_requires_hosts() -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, [])
    assert result.exit_code != 0
    assert "Provide at least one host" in result.output


def test_cli_merges_hosts_and_infers_export_format(tmp_path, monkeypatch) -> None:
    hosts_file = tmp_path / "hosts.txt"
    hosts_file.write_text("1.1.1.1\n8.8.8.8\n1.1.1.1\n", encoding="utf-8")

    recorded = {}

    class FakeApp:
        def __init__(self, session, engine) -> None:
            recorded["session"] = session

        def run(self) -> None:
            host_id = next(iter(recorded["session"].hosts))
            recorded["session"].apply_result(
                host_id,
                PingResult(success=True, rtt_ms=9.5, resolved_ip="1.1.1.1"),
            )

    monkeypatch.setattr(cli, "PingTopApp", FakeApp)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "1.1.1.1",
            "--hosts-file",
            str(hosts_file),
            "--export",
            str(tmp_path / "out.json"),
            "--no-summary",
        ],
    )

    assert result.exit_code == 0
    session = recorded["session"]
    assert [record.config.target for record in session.hosts.values()] == ["1.1.1.1", "8.8.8.8"]
    assert (tmp_path / "out.json").exists()


def test_cli_expands_cidr_targets(tmp_path, monkeypatch) -> None:
    recorded = {}

    class FakeApp:
        def __init__(self, session, engine) -> None:
            recorded["session"] = session

        def run(self) -> None:
            return None

    monkeypatch.setattr(cli, "PingTopApp", FakeApp)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["10.22.76.19/30", "--no-summary"])

    assert result.exit_code == 0
    session = recorded["session"]
    assert [record.config.target for record in session.hosts.values()] == [
        "10.22.76.17",
        "10.22.76.18",
    ]


def test_cli_rejects_invalid_cidr(monkeypatch) -> None:
    class FakeApp:
        def __init__(self, session, engine) -> None:
            self.session = session

        def run(self) -> None:
            return None

    monkeypatch.setattr(cli, "PingTopApp", FakeApp)

    runner = CliRunner()
    result = runner.invoke(cli.main, ["10.22.76.19/99"])

    assert result.exit_code != 0
    assert "Invalid network or host" in result.output


def test_cli_rejects_non_utf8_hosts_file(tmp_path) -> None:
    hosts_file = tmp_path / "hosts.txt"
    hosts_file.write_bytes(b"1.1.1.1\n\xff\xfe bad\n")

    runner = CliRunner()
    result = runner.invoke(cli.main, ["8.8.8.8", "--hosts-file", str(hosts_file)])

    assert result.exit_code != 0
    assert "hosts file" in result.output
    assert "UTF-8" in result.output
    assert isinstance(result.exception, SystemExit)


def test_cli_requires_explicit_export_format_for_ambiguous_extension(tmp_path, monkeypatch) -> None:
    class FakeApp:
        def __init__(self, session, engine) -> None:
            self.session = session

        def run(self) -> None:
            return None

    monkeypatch.setattr(cli, "PingTopApp", FakeApp)
    runner = CliRunner()
    result = runner.invoke(cli.main, ["1.1.1.1", "--export", str(tmp_path / "out.data")])
    assert result.exit_code != 0
    assert "Unable to infer export format" in result.output
