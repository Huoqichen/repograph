from pathlib import Path

from repomap.repository import _default_clone_root, clone_repository


def test_default_clone_root_prefers_drive_root() -> None:
    clone_root = _default_clone_root()

    assert clone_root.drive.upper().startswith("D:")
    assert str(clone_root).lower().endswith(r"repomap-cache\c")


def test_clone_repository_uses_longpath_safe_checkout(monkeypatch, tmp_path: Path) -> None:
    recorded_commands = []

    def fake_run(command, check, capture_output, text):
        recorded_commands.append(command)
        return type("CompletedProcess", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr("repomap.repository.subprocess.run", fake_run)

    destination, temporary_clone = clone_repository(
        "https://github.com/vercel/next.js",
        clone_root=tmp_path,
        branch="canary",
    )

    assert temporary_clone is False
    assert destination == tmp_path / "next.js"
    assert recorded_commands[0][:6] == ["git", "-c", "core.longpaths=true", "clone", "--depth", "1"]
    assert "--no-checkout" in recorded_commands[0]
    assert recorded_commands[1] == ["git", "-C", str(destination), "config", "core.longpaths", "true"]
    assert recorded_commands[2] == ["git", "-C", str(destination), "checkout", "-f", "HEAD"]
