import os
from pathlib import Path
import shlex
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.usefixtures("bash_environment")

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/deploy/deploy-production.sh"
IMAGE_TAG = "a" * 40


def bash_path(path: Path) -> str:
    if os.name == "nt":
        return f"/{path.drive[0].lower()}{path.as_posix()[2:]}"
    return path.as_posix()


@pytest.mark.parametrize("failure", ["", "pull", "worker"])
def test_deployment_exit_cleans_up_and_preserves_result(tmp_path: Path, failure: str) -> None:
    app_dir = tmp_path / "production"
    app_dir.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    docker_config = tmp_path / "anonymous docker's config"

    # Keep the real deployment logic; only redirect the fixed VPS directory.
    script = SCRIPT.read_text().replace(
        'readonly APP_DIRECTORY="/opt/true-roi"',
        f"readonly APP_DIRECTORY={shlex.quote(bash_path(app_dir))}",
    )
    staged_compose = app_dir / f"docker-compose.prod.yml.{IMAGE_TAG}.staged"
    staged_script = app_dir / f"deploy-production.sh.{IMAGE_TAG}.staged"
    staged_compose.write_text("test compose\n", newline="\n")
    staged_script.write_text(script, newline="\n")
    installed_compose = app_dir / "docker-compose.prod.yml"
    installed_compose.write_text("previous compose\n", newline="\n")

    commands = {
        "flock": "exit 0\n",
        "mktemp": 'mkdir -p "$TEST_DOCKER_CONFIG"\nprintf "%s\\n" "$TEST_DOCKER_CONFIG"\n',
        "docker": r'''case "$1" in
    compose)
        for argument do
            if [ "$argument" = pull ] && [ "$FAILURE" = pull ]; then
                exit 37
            fi
        done
        ;;
    inspect)
        case "$3" in
            *Config.Env*)
                printf '%s\n' POSTGRES_USER=test POSTGRES_DB=test POSTGRES_PASSWORD=test
                ;;
            *State.Health*) echo healthy ;;
            *State.Status*)
                if [ "$FAILURE" = worker ] && [ "$4" = true-roi-csmoney-crawler ]; then
                    echo exited
                else
                    echo running
                fi
                ;;
            *) echo healthy ;;
        esac
        ;;
    exec) cat >/dev/null ;;
    *) exit 99 ;;
esac
''',
    }
    for name, body in commands.items():
        command = bindir / name
        command.write_text("#!/bin/sh\nset -eu\n" + body, newline="\n")
        command.chmod(0o755)

    result = subprocess.run(
        [shutil.which("bash") or "bash", "-c",
         'export PATH="$TEST_BIN:$PATH"; exec bash "$@"',
         "bash", bash_path(staged_script), IMAGE_TAG],
        cwd=REPO,
        env={
            **os.environ,
            "TEST_BIN": bash_path(bindir),
            "TEST_DOCKER_CONFIG": bash_path(docker_config),
            "FAILURE": failure,
        },
        text=True, capture_output=True, check=False,
    )

    assert "unbound variable" not in result.stderr
    assert not staged_compose.exists()
    assert not staged_script.exists()
    assert not docker_config.exists()
    if failure == "pull":
        assert result.returncode == 37, result.stderr
        assert installed_compose.read_text() == "previous compose\n"
        assert not (app_dir / "deploy-production.sh").exists()
    elif failure == "worker":
        assert result.returncode == 1, result.stderr
        assert "true-roi-csmoney-crawler is not running" in result.stderr
        assert not (app_dir / "deploy-production.sh").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert f"Deployment healthy: {IMAGE_TAG}" in result.stdout
        assert installed_compose.read_text() == "test compose\n"
        assert (app_dir / "deploy-production.sh").read_text() == script
