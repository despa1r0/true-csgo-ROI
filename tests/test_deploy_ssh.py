import os
from pathlib import Path
import subprocess


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/ci/deploy-ssh.sh"
IMAGE_TAG = "a" * 40


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
        "grep -F -- \"$host \" \"$file\"\n"
    )
    keygen.chmod(0o755)
    for name in ("ssh", "scp"):
        command = bindir / name
        command.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$CALL_LOG"\n')
        command.chmod(0o755)
    return bindir, keygen


def run(tmp_path: Path, action: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    bindir, _ = make_tools(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "SSH_DIRECTORY": str(tmp_path / "ssh"),
        "CALL_LOG": str(tmp_path / "calls.log"),
        "VPS_SSH_KEY": "private-key-test-value",
        "VPS_KNOWN_HOSTS": "[vps.example]:2222 ssh-ed25519 AAAA-test-host-key",
        "VPS_HOST": "vps.example",
        "VPS_USER": "deploy",
        "VPS_PORT": "2222",
        "IMAGE_TAG": IMAGE_TAG,
        **overrides,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), action], cwd=REPO, env=env,
        text=True, capture_output=True, check=False,
    )


def test_configure_requires_pinned_known_hosts_secret(tmp_path: Path) -> None:
    result = run(tmp_path, "configure", VPS_KNOWN_HOSTS="")
    assert result.returncode != 0
    assert "VPS_KNOWN_HOSTS" in result.stderr
    assert not (tmp_path / "ssh").exists()
    assert not (tmp_path / "calls.log").exists()


def test_configure_refuses_host_or_port_mismatch(tmp_path: Path) -> None:
    result = run(tmp_path, "configure", VPS_KNOWN_HOSTS="other.example ssh-ed25519 AAAA")
    assert result.returncode != 0
    assert "no host key" in result.stderr
    assert not (tmp_path / "calls.log").exists()


def test_configure_uses_pinned_host_and_ssh_scp_are_strict(tmp_path: Path) -> None:
    configured = run(tmp_path, "configure")
    assert configured.returncode == 0, configured.stderr
    ssh_dir = tmp_path / "ssh"
    assert (ssh_dir / "known_hosts").read_text().startswith("[vps.example]:2222 ")
    assert (ssh_dir / "id_ed25519").stat().st_mode & 0o777 == 0o600
    assert (ssh_dir / "known_hosts").stat().st_mode & 0o777 == 0o600

    assert run(tmp_path, "copy").returncode == 0
    assert run(tmp_path, "deploy").returncode == 0
    invocations = (tmp_path / "calls.log").read_text().splitlines()
    assert sum("/scp " in invocation for invocation in invocations) == 2
    assert sum("/ssh " in invocation for invocation in invocations) == 1
    assert all("StrictHostKeyChecking=yes" in invocation for invocation in invocations)
    assert all("BatchMode=yes" in invocation for invocation in invocations)
    assert all("UserKnownHostsFile=" in invocation for invocation in invocations)
    assert "ssh-keyscan" not in "\n".join(invocations)

    cleaned = run(tmp_path, "cleanup")
    assert cleaned.returncode == 0
    assert not ssh_dir.exists()
