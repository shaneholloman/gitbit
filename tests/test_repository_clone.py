"""
Tests for the `repository_clone` module.

These tests cover various scenarios for cloning repositories, verifying that the appropriate Git commands are invoked
and handling edge cases such as nonexistent URLs, timeouts, redirects, and specific commits or branches.
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from gitingest.exceptions import AsyncTimeoutError
from gitingest.repository_clone import CloneConfig, _check_repo_exists, clone_repo


@pytest.mark.asyncio
async def test_clone_repo_with_commit() -> None:
    """
    Test cloning a repository with a specific commit hash.

    Given a valid URL and a commit hash:
    When `clone_repo` is called,
    Then the repository should be cloned and checked out at that commit.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
        commit="a" * 40,  # Simulating a valid commit hash
        branch="main",
    )

    with patch("gitingest.repository_clone._check_repo_exists", return_value=True) as mock_check:
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"error")
            mock_exec.return_value = mock_process

            await clone_repo(clone_config)

            mock_check.assert_called_once_with(clone_config.url)
            assert mock_exec.call_count == 2  # Clone and checkout calls


@pytest.mark.asyncio
async def test_clone_repo_without_commit() -> None:
    """
    Test cloning a repository when no commit hash is provided.

    Given a valid URL and no commit hash:
    When `clone_repo` is called,
    Then only the clone operation should be performed (no checkout).
    """
    query = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
        commit=None,
        branch="main",
    )

    with patch("gitingest.repository_clone._check_repo_exists", return_value=True) as mock_check:
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"error")
            mock_exec.return_value = mock_process

            await clone_repo(query)

            mock_check.assert_called_once_with(query.url)
            assert mock_exec.call_count == 1  # Only clone call


@pytest.mark.asyncio
async def test_clone_repo_nonexistent_repository() -> None:
    """
    Test cloning a nonexistent repository URL.

    Given an invalid or nonexistent URL:
    When `clone_repo` is called,
    Then a ValueError should be raised with an appropriate error message.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/nonexistent-repo",
        local_path="/tmp/repo",
        commit=None,
        branch="main",
    )
    with patch("gitingest.repository_clone._check_repo_exists", return_value=False) as mock_check:
        with pytest.raises(ValueError, match="Repository not found"):
            await clone_repo(clone_config)

            mock_check.assert_called_once_with(clone_config.url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_stdout, return_code, expected",
    [
        (b"HTTP/1.1 200 OK\n", 0, True),  # Existing repo
        (b"HTTP/1.1 404 Not Found\n", 0, False),  # Non-existing repo
        (b"HTTP/1.1 200 OK\n", 1, False),  # Failed request
    ],
)
async def test_check_repo_exists(mock_stdout: bytes, return_code: int, expected: bool) -> None:
    """
    Test the `_check_repo_exists` function with different Git HTTP responses.

    Given various stdout lines and return codes:
    When `_check_repo_exists` is called,
    Then it should correctly indicate whether the repository exists.
    """
    url = "https://github.com/user/repo"

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = AsyncMock()
        # Mock the subprocess output
        mock_process.communicate.return_value = (mock_stdout, b"")
        mock_process.returncode = return_code
        mock_exec.return_value = mock_process

        repo_exists = await _check_repo_exists(url)

        assert repo_exists is expected


@pytest.mark.asyncio
async def test_clone_repo_invalid_url() -> None:
    """
    Test cloning when the URL is invalid or empty.

    Given an empty URL:
    When `clone_repo` is called,
    Then a ValueError should be raised with an appropriate error message.
    """
    clone_config = CloneConfig(
        url="",
        local_path="/tmp/repo",
    )
    with pytest.raises(ValueError, match="The 'url' parameter is required."):
        await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_repo_invalid_local_path() -> None:
    """
    Test cloning when the local path is invalid or empty.

    Given an empty local path:
    When `clone_repo` is called,
    Then a ValueError should be raised with an appropriate error message.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="",
    )
    with pytest.raises(ValueError, match="The 'local_path' parameter is required."):
        await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_repo_with_custom_branch() -> None:
    """
    Test cloning a repository with a specified custom branch.

    Given a valid URL and a branch:
    When `clone_repo` is called,
    Then the repository should be cloned shallowly to that branch.
    """
    clone_config = CloneConfig(url="https://github.com/user/repo", local_path="/tmp/repo", branch="feature-branch")
    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)

            mock_exec.assert_called_once_with(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                "--branch",
                "feature-branch",
                clone_config.url,
                clone_config.local_path,
            )


@pytest.mark.asyncio
async def test_git_command_failure() -> None:
    """
    Test cloning when the Git command fails during execution.

    Given a valid URL, but `_run_git_command` raises a RuntimeError:
    When `clone_repo` is called,
    Then a RuntimeError should be raised with the correct message.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
    )
    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", side_effect=RuntimeError("Git command failed")):
            with pytest.raises(RuntimeError, match="Git command failed"):
                await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_repo_default_shallow_clone() -> None:
    """
    Test cloning a repository with the default shallow clone options.

    Given a valid URL and no branch or commit:
    When `clone_repo` is called,
    Then the repository should be cloned with `--depth=1` and `--single-branch`.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
    )

    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)

            mock_exec.assert_called_once_with(
                "git", "clone", "--depth=1", "--single-branch", clone_config.url, clone_config.local_path
            )


@pytest.mark.asyncio
async def test_clone_repo_commit_without_branch() -> None:
    """
    Test cloning when a commit hash is provided but no branch is specified.

    Given a valid URL and a commit hash (but no branch):
    When `clone_repo` is called,
    Then the repository should be cloned and checked out at that commit.
    """
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path="/tmp/repo",
        commit="a" * 40,  # Simulating a valid commit hash
    )
    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)

            assert mock_exec.call_count == 2  # Clone and checkout calls
            mock_exec.assert_any_call("git", "clone", "--single-branch", clone_config.url, clone_config.local_path)
            mock_exec.assert_any_call("git", "-C", clone_config.local_path, "checkout", clone_config.commit)


@pytest.mark.asyncio
async def test_check_repo_exists_with_redirect() -> None:
    """
    Test `_check_repo_exists` when a redirect (302) is returned.

    Given a URL that responds with "302 Found":
    When `_check_repo_exists` is called,
    Then it should return `False`, indicating the repo is inaccessible.
    """
    url = "https://github.com/user/repo"
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"HTTP/1.1 302 Found\n", b"")
        mock_process.returncode = 0  # Simulate successful request
        mock_exec.return_value = mock_process

        repo_exists = await _check_repo_exists(url)

        assert repo_exists is False


@pytest.mark.asyncio
async def test_check_repo_exists_with_permanent_redirect() -> None:
    """
    Test `_check_repo_exists` when a permanent redirect (301) is returned.

    Given a URL that responds with "301 Found":
    When `_check_repo_exists` is called,
    Then it should return `True`, indicating the repo may exist at the new location.
    """
    url = "https://github.com/user/repo"
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"HTTP/1.1 301 Found\n", b"")
        mock_process.returncode = 0  # Simulate successful request
        mock_exec.return_value = mock_process

        repo_exists = await _check_repo_exists(url)

        assert repo_exists


@pytest.mark.asyncio
async def test_clone_repo_with_timeout() -> None:
    """
    Test cloning a repository when a timeout occurs.

    Given a valid URL, but `_run_git_command` times out:
    When `clone_repo` is called,
    Then an `AsyncTimeoutError` should be raised to indicate the operation exceeded time limits.
    """
    clone_config = CloneConfig(url="https://github.com/user/repo", local_path="/tmp/repo")

    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = asyncio.TimeoutError
            with pytest.raises(AsyncTimeoutError, match="Operation timed out after"):
                await clone_repo(clone_config)


@pytest.mark.asyncio
async def test_clone_specific_branch(tmp_path):
    """
    Test cloning a specific branch of a repository.

    Given a valid repository URL and a branch name:
    When `clone_repo` is called,
    Then the repository should be cloned and checked out at that branch.
    """
    repo_url = "https://github.com/cyclotruc/gitingest.git"
    branch_name = "main"
    local_path = tmp_path / "gitingest"

    config = CloneConfig(url=repo_url, local_path=str(local_path), branch=branch_name)
    await clone_repo(config)

    # Assertions
    assert local_path.exists(), "The repository was not cloned successfully."
    assert local_path.is_dir(), "The cloned repository path is not a directory."

    # Check the current branch
    current_branch = os.popen(f"git -C {local_path} branch --show-current").read().strip()
    assert current_branch == branch_name, f"Expected branch '{branch_name}', got '{current_branch}'."


@pytest.mark.asyncio
async def test_clone_branch_with_slashes(tmp_path):
    """
    Test cloning a branch with slashes in the name.

    Given a valid repository URL and a branch name with slashes:
    When `clone_repo` is called,
    Then the repository should be cloned and checked out at that branch.
    """
    repo_url = "https://github.com/user/repo"
    branch_name = "fix/in-operator"
    local_path = tmp_path / "gitingest"

    clone_config = CloneConfig(url=repo_url, local_path=str(local_path), branch=branch_name)
    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)

            mock_exec.assert_called_once_with(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                "--branch",
                "fix/in-operator",
                clone_config.url,
                clone_config.local_path,
            )


@pytest.mark.asyncio
async def test_clone_repo_creates_parent_directory(tmp_path: Path) -> None:
    """
    Test that clone_repo creates parent directories if they don't exist.

    Given a local path with non-existent parent directories:
    When `clone_repo` is called,
    Then it should create the parent directories before attempting to clone.
    """
    nested_path = tmp_path / "deep" / "nested" / "path" / "repo"
    clone_config = CloneConfig(
        url="https://github.com/user/repo",
        local_path=str(nested_path),
    )

    with patch("gitingest.repository_clone._check_repo_exists", return_value=True):
        with patch("gitingest.repository_clone._run_git_command", new_callable=AsyncMock) as mock_exec:
            await clone_repo(clone_config)

            # Verify parent directory was created
            assert nested_path.parent.exists()

            # Verify git clone was called with correct parameters
            mock_exec.assert_called_once_with(
                "git",
                "clone",
                "--depth=1",
                "--single-branch",
                clone_config.url,
                str(nested_path),
            )
