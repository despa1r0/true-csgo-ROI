import os
from pathlib import Path
import shutil
import subprocess


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/deploy/deploy-ssh.sh"
IMAGE_TAG = "a" * 40


def bash_path(path: Path) -> str:
    if os.name == "nt":
        return f"/{path.drive[0].lower()}{path.as_posix()[2:]}"
    return path.as_posix()


def make_tools(tmp_path: Path) -> tuple[Path, Path]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    keygen = bindir / "ssh-keygen"
    keygen.write_text(
        "#!/bin/sh\n"
        "host= file=\n"
        "while [ $# -gt 0 ]; do\n"
        "  case $1 in\n"
        "    -F) host=$2; shift 2 ;;\n"
        "    -f) file=$2; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "grep -Fq -- \"$host \" \"$file\" || exit 1\n"
        "grep -F -- \"$host \" \"$file\"\n",
        newline="\n",
    )
    keygen.chmod(0o755)
    scanner = bindir / "ssh-keyscan"
    scanner.write_text(
        '#!/bin/sh\n'
        'printf "%s\\n" "$0 $*" >> "$CALL_LOG"\n'
        'printf "%s\\n" "$SCANNED_HOST_KEY"\n'
        'exit "$KEYSCAN_EXIT_CODE"\n',
        newline="\n",
    )
    scanner.chmod(0o755)
    for name in ("ssh", "scp"):
        command = bindir / name
        command.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$CALL_LOG"\n', newline="\n")
        command.chmod(0o755)
    if os.name == "nt":
        # Git Bash cannot set POSIX permissions on every Windows filesystem.
        # Keep real install/chmod and permission assertions on the Linux runner.
        (bindir / "install").write_text(
            '#!/bin/sh\nfor directory do :; done\nmkdir -p "$directory"\n',
            newline="\n",
        )
        (bindir / "chmod").write_text('#!/bin/sh\nexit 0\n', newline="\n")
    return bindir, keygen


def run(tmp_path: Path, action: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    bindir, _ = make_tools(tmp_path)
    env = {
        **os.environ,
        "TEST_BIN": bash_path(bindir),
        "SSH_DIRECTORY": bash_path(tmp_path / "ssh"),
        "CALL_LOG": bash_path(tmp_path / "calls.log"),
        "VPS_SSH_KEY": "private-key-test-value",
        "SCANNED_HOST_KEY": "[vps.example]:2222 ssh-ed25519 AAAA-test-host-key",
        "KEYSCAN_EXIT_CODE": "0",
        "VPS_HOST": "vps.example",
        "VPS_USER": "deploy",
        "VPS_PORT": "2222",
        "IMAGE_TAG": IMAGE_TAG,
        **overrides,
    }
    return subprocess.run(
        [shutil.which("bash") or "bash", "-c",
         'export PATH="$TEST_BIN:$PATH"; exec bash "$@"',
         "bash", bash_path(SCRIPT), action], cwd=REPO, env=env,
        text=True, capture_output=True, check=False,
    )


def test_configure_requires_ssh_key_before_scanning(tmp_path: Path) -> None:
    result = run(tmp_path, "configure", VPS_SSH_KEY="")
    assert result.returncode != 0
    assert "VPS_SSH_KEY" in result.stderr
    assert not (tmp_path / "ssh").exists()
    assert not (tmp_path / "calls.log").exists()


def test_configure_stops_when_host_key_scan_fails(tmp_path: Path) -> None:
    result = run(tmp_path, "configure", KEYSCAN_EXIT_CODE="1")
    assert result.returncode != 0
    assert "Failed to retrieve" in result.stderr
    assert run(tmp_path, "cleanup").returncode == 0
    assert not (tmp_path / "ssh").exists()


def test_configure_refuses_empty_host_key_scan(tmp_path: Path) -> None:
    result = run(tmp_path, "configure", SCANNED_HOST_KEY="")
    assert result.returncode != 0
    assert "No SSH host key" in result.stderr


def test_configure_refuses_host_or_port_mismatch(tmp_path: Path) -> None:
    result = run(tmp_path, "configure", SCANNED_HOST_KEY="other.example ssh-ed25519 AAAA")
    assert result.returncode != 0
    assert "No SSH host key" in result.stderr
    invocations = (tmp_path / "calls.log").read_text().splitlines()
    assert len(invocations) == 1
    assert "/ssh-keyscan " in invocations[0]


def test_configure_scans_host_and_ssh_scp_are_strict(tmp_path: Path) -> None:
    configured = run(tmp_path, "configure")
    assert configured.returncode == 0, configured.stderr
    ssh_dir = tmp_path / "ssh"
    assert (ssh_dir / "known_hosts").read_text().startswith("[vps.example]:2222 ")
    if os.name != "nt":
        assert (ssh_dir / "id_ed25519").stat().st_mode & 0o777 == 0o600
        assert (ssh_dir / "known_hosts").stat().st_mode & 0o777 == 0o600

    assert run(tmp_path, "copy").returncode == 0
    assert run(tmp_path, "deploy").returncode == 0
    invocations = (tmp_path / "calls.log").read_text().splitlines()
    scans = [invocation for invocation in invocations if "/ssh-keyscan " in invocation]
    assert len(scans) == 1
    assert "-H -T 10 -p 2222 vps.example" in scans[0]
    connections = [invocation for invocation in invocations if "/scp " in invocation or "/ssh " in invocation]
    assert sum("/scp " in invocation for invocation in invocations) == 2
    assert sum("/ssh " in invocation for invocation in invocations) == 1
    assert all("StrictHostKeyChecking=yes" in invocation for invocation in connections)
    assert all("BatchMode=yes" in invocation for invocation in connections)
    assert all(f"UserKnownHostsFile={bash_path(ssh_dir)}/known_hosts" in invocation for invocation in connections)
    assert any("scripts/deploy/deploy-production.sh" in invocation for invocation in connections)
    assert all(f".{IMAGE_TAG}.staged" in invocation for invocation in connections)

    cleaned = run(tmp_path, "cleanup")
    assert cleaned.returncode == 0
    assert not ssh_dir.exists()
