from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def clone_repository(repo_url: str, clone_root: Path | None = None, branch: str | None = None) -> tuple[Path, bool]:
    """Clone a repository and return the checkout path plus whether it is temporary."""
    temporary_clone = clone_root is None
    if temporary_clone:
        temp_root = _default_clone_root()
        temp_root.mkdir(parents=True, exist_ok=True)
        base_dir = Path(tempfile.mkdtemp(prefix="rp-", dir=str(temp_root)))
    else:
        base_dir = clone_root.expanduser().resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    repo_name = _repo_name_from_url(repo_url)
    destination = base_dir / (_temporary_destination_name(repo_name) if temporary_clone else repo_name)
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    command = ["git", "-c", "core.longpaths=true", "clone", "--depth", "1", "--no-checkout"]
    if branch:
        command.extend(["--branch", branch])
    command.extend([repo_url, str(destination)])

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "-C", str(destination), "config", "core.longpaths", "true"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(destination), "checkout", "-f", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() or error.stdout.strip() or str(error)
        raise RuntimeError(f"git clone failed: {stderr}") from error

    return destination, temporary_clone


def cleanup_clone(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def detect_git_branch(repo_path: Path) -> str | None:
    command = ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "HEAD"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return None

    branch = result.stdout.strip()
    return branch if branch and branch != "HEAD" else None


def list_remote_branches(repo_url: str) -> tuple[str | None, list[str]]:
    command = ["git", "ls-remote", "--symref", repo_url, "HEAD", "refs/heads/*"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() or error.stdout.strip() or str(error)
        raise RuntimeError(f"git branch lookup failed: {stderr}") from error

    default_branch: str | None = None
    branch_names: list[str] = []

    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "ref:" and parts[2] == "HEAD":
            default_branch = parts[1].removeprefix("refs/heads/")
            continue
        if len(parts) >= 2 and parts[1].startswith("refs/heads/"):
            branch_names.append(parts[1].removeprefix("refs/heads/"))

    unique_branches = sorted(set(branch_names), key=lambda item: (item != default_branch, item.lower()))
    return default_branch, unique_branches


def github_blob_url(repo_url: str, branch: str | None, relative_path: str) -> str | None:
    if "github.com/" not in repo_url or not branch:
        return None

    normalized = repo_url.removesuffix(".git").rstrip("/")
    return f"{normalized}/blob/{branch}/{relative_path}"


def _default_clone_root() -> Path:
    workspace_root = Path(__file__).resolve().parents[1]
    drive_root = Path(workspace_root.anchor)
    if drive_root.exists():
        return drive_root / "repomap-cache" / "c"
    return workspace_root / ".codex-temp-cache" / "clones"


def _repo_name_from_url(repo_url: str) -> str:
    name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".git") else name


def _temporary_destination_name(repo_name: str) -> str:
    suffix = "".join(character for character in repo_name.lower() if character.isalnum())[:6]
    return f"r{suffix or 'repo'}"
