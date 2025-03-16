"""Utility classes to manipulate GitLib repositories."""

import logging
import os
from functools import cached_property
from typing import Any, Dict, Generator, Tuple

import requests
from git import GitCommandError, Repo


class RepositoryManager():
    """Class to manage a local clone of a Gitlab repository."""

    def __init__(
            self,
            repo_id: str,
            commit_hash: str = None,
            access_token: str = None,
            local_dir: str = None,
            inclusion_file: str = None,
            exclusion_file: str = None,
            gitlab_base_url: str = None,
    ):
        """
        Args:
            repo_id: The identifier of the repository in owner/repo format, e.g. "Storia-AI/sage".
            commit_hash: Optional commit hash to checkout. If not specified, we pull the latest version of the repo.
            access_token: A GitLab access token to use for cloning private repositories. Not needed for public repos.
            local_dir: The local directory where the repository will be cloned.
            inclusion_file: A file with a lists of files/directories/extensions to include. Each line must be in one of
                the following formats: "ext:.my-extension", "file:my-file.py", or "dir:my-directory".
            exclusion_file: A file with a lists of files/directories/extensions to exclude. Each line must be in one of
                the following formats: "ext:.my-extension", "file:my-file.py", or "dir:my-directory".
            gitlab_base_url: The base URL of the GitLab instance (defaults to https://gitlab.com).

        """
        if not gitlab_base_url:
            raise ValueError("gitlab_base_url 不能为空，请提供有效的 GitLab 地址。")

        self.repo_id = repo_id
        self.commit_hash = commit_hash
        self.access_token = access_token
        self.gitlab_base_url = gitlab_base_url

        self.local_dir = local_dir or "/tmp/"
        if not os.path.exists(self.local_dir):
            os.makedirs(self.local_dir)
        self.local_path = os.path.join(self.local_dir, repo_id)

        self.log_dir = os.path.join(self.local_dir, "logs", repo_id)
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        if inclusion_file and exclusion_file:
            raise ValueError("Only one of inclusion_file or exclusion_file should be provided.")

        self.inclusions = self._parse_filter_file(inclusion_file) if inclusion_file else None
        self.exclusions = self._parse_filter_file(exclusion_file) if exclusion_file else None

    @cached_property
    def default_branch(self) -> str:
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        response = requests.get(
            f"{self.gitlab_base_url}/api/v4/projects/{self.repo_id.replace('/', '%2F')}",
            headers=headers,
        )
        if response.status_code == 200:
            branch = response.json().get("default_branch", "main")
        else:
            # Fallback to "main" if the API call fails.
            logging.warning(f"Unable to fetch default branch for {self.repo_id}: {response.text}")
            branch = "main"
        return branch

    def download(self) -> bool:
        """Clones the repository to the local directory, if it's not already cloned."""
        if os.path.exists(self.local_path):
            logging.info(f"Repository already exists at {self.local_path}, pulling latest changes.")
            return self.pull()

        if not self.access_token:
            raise ValueError(f"Access token is required to clone {self.repo_id}.")

        clone_url = f"https://oauth2:{self.access_token}@{self.gitlab_base_url.replace('https://', '')}/{self.repo_id}.git"

        try:
            if self.commit_hash:
                repo = Repo.clone_from(clone_url, self.local_path)
                repo.git.checkout(self.commit_hash)
            else:
                Repo.clone_from(clone_url, self.local_path, depth=1, single_branch=True)
        except GitCommandError as e:
            logging.error("Unable to clone %s from %s. Error: %s", self.repo_id, clone_url, e)
            return False
        return True

    def pull(self) -> bool:
        """Pulls the latest changes from the remote repository to the local directory."""
        if not os.path.exists(self.local_path):
            # The repository is not cloned yet, cannot pull.
            logging.error("Repository not found at %s.", self.local_path)
            return False

        if not self.access_token:
            raise ValueError(f"Access token is required to pull from {self.repo_id}.")

        try:
            repo = Repo(self.local_path)
            # Fetch the latest changes
            origin = repo.remotes.origin
            origin.fetch()  # Get the latest updates from the remote

            # Checkout the correct commit if provided (optional)
            if self.commit_hash:
                repo.git.checkout(self.commit_hash)

            # Pull the latest changes from the remote branch
            origin.pull()

        except GitCommandError as e:
            logging.error("Unable to pull from %s. Error: %s", self.repo_id, e)
            return False

        return True

    def _parse_filter_file(self, file_path: str) -> bool:
        """Parses a file with files/directories/extensions to include/exclude.

        Lines are expected to be in the format:
        # Comment that will be ignored, or
        ext:.my-extension, or
        file:my-file.py, or
        dir:my-directory
        """
        with open(file_path, "r") as f:
            lines = f.readlines()

        parsed_data = {"ext": [], "file": [], "dir": []}
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):  # 跳过空行和注释行
                # This is a comment line.
                continue
            key, value = line.strip().split(":")
            if key in parsed_data:
                parsed_data[key].append(value)
            else:
                logging.error("Unrecognized key in line: %s. Skipping.", line)

        return parsed_data

    def _should_include(self, file_path: str) -> bool:
        """Checks whether the file should be indexed."""
        # Exclude symlinks.
        if os.path.islink(file_path):
            return False

        # Exclude hidden files and directories.
        if any(part.startswith(".") for part in file_path.split(os.path.sep)):
            return False

        if not self.inclusions and not self.exclusions:
            return True

        # Filter based on file extensions, file names and directory names.
        _, extension = os.path.splitext(file_path)
        extension = extension.lower()
        file_name = os.path.basename(file_path)
        dirs = os.path.dirname(file_path).split("/")

        if self.inclusions:
            return (
                    extension in self.inclusions.get("ext", [])
                    or file_name in self.inclusions.get("file", [])
                    or any(d in dirs for d in self.inclusions.get("dir", []))
            )
        elif self.exclusions:
            return (
                    extension not in self.exclusions.get("ext", [])
                    and file_name not in self.exclusions.get("file", [])
                    and all(d not in dirs for d in self.exclusions.get("dir", []))
            )
        return True

    def walk(self, get_content: bool = True) -> Generator[Tuple[Any, Dict], None, None]:
        """Walks the local repository path and yields a tuple of (content, metadata) for each file.
        The filepath is relative to the root of the repository (e.g. "org/repo/your/file/path.py").

        Args:
            get_content: When set to True, yields (content, metadata) tuples. When set to False, yields metadata only.
        """
        # We will keep appending to these files during the iteration, so we need to clear them first.
        repo_name = self.repo_id.replace("/", "_")
        included_log_file = os.path.join(self.log_dir, f"included_{repo_name}.txt")
        excluded_log_file = os.path.join(self.log_dir, f"excluded_{repo_name}.txt")
        if os.path.exists(included_log_file):
            os.remove(included_log_file)
            logging.info("Logging included files at %s", included_log_file)
        if os.path.exists(excluded_log_file):
            os.remove(excluded_log_file)
            logging.info("Logging excluded files at %s", excluded_log_file)

        for root, _, files in os.walk(self.local_path):
            file_paths = [os.path.join(root, file) for file in files]
            included_file_paths = [f for f in file_paths if self._should_include(f)]

            with open(included_log_file, "a") as f:
                for path in included_file_paths:
                    f.write(path + "\n")

            excluded_file_paths = set(file_paths).difference(set(included_file_paths))
            with open(excluded_log_file, "a") as f:
                for path in excluded_file_paths:
                    f.write(path + "\n")

            for file_path in included_file_paths:
                relative_file_path = file_path[len(self.local_dir) + 1:]
                metadata = {
                    "file_path": relative_file_path,
                    "url": self.url_for_file(relative_file_path),
                }

                if not get_content:
                    yield metadata
                    continue

                contents = self.read_file(relative_file_path)
                if contents:
                    yield contents, metadata

    def url_for_file(self, file_path: str) -> str:
        """Converts a repository file path to a GitLab link."""
        file_path = file_path[len(self.repo_id.replace("/", "_")) + 1:]
        return f"{self.gitlab_base_url}/{self.repo_id}/-/blob/{self.default_branch}/{file_path}"

    def read_file(self, relative_file_path: str) -> str:
        """Reads the contents of a file in the repository."""
        absolute_file_path = os.path.join(self.local_dir, relative_file_path)
        with open(absolute_file_path, "r") as f:
            try:
                contents = f.read()
                return contents
            except UnicodeDecodeError:
                logging.warning("Unable to decode file %s.", absolute_file_path)
                return None
