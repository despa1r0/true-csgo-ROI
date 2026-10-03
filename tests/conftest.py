"""Local shell tests use Git Bash on Windows and system Bash on Linux."""
import os
from pathlib import Path
import shutil

import pytest


@pytest.fixture
def bash_environment(monkeypatch):
    if os.name == "nt":
        git = shutil.which("git")
        candidates = [Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin"]
        if git:
            candidates.insert(0, Path(git).resolve().parents[1] / "bin")
        directory = next((path for path in candidates if (path / "bash.exe").is_file()), None)
        if directory is None:
            pytest.skip("Shell integration tests require Git Bash on Windows (WSL bash is not compatible)")
        monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))
    elif not shutil.which("bash"):
        pytest.skip("Shell integration tests require Bash")
