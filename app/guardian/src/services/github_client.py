from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.config import Settings, settings
from src.models.schemas import RepoVisibility


class GitHubClient:
    def __init__(self, cfg: Settings = settings):
        self.cfg = cfg
        self.base_url = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com")

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if cfg.github_token:
            headers["Authorization"] = f"token {cfg.github_token}"

        self._headers = headers
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_repo(self, *, owner: str, repo: str) -> Dict[str, Any]:
        res = await self._client.get(f"/repos/{owner}/{repo}")
        await self._raise_for_status(res)
        return res.json()

    async def count_commits_last_window(
        self, *, owner: str, repo: str, window_days: int, per_page: int = 100
    ) -> int:
        since = datetime.utcnow() - timedelta(days=window_days)
        count = 0
        for page in range(1, self.cfg.github_max_pages + 1):
            res = await self._client.get(
                f"/repos/{owner}/{repo}/commits",
                params={"since": since.isoformat() + "Z", "per_page": per_page, "page": page},
            )
            await self._raise_for_status(res)
            data = res.json()
            if not isinstance(data, list) or len(data) == 0:
                break
            count += len(data)
            if len(data) < per_page:
                break
        return count

    async def count_open_prs(self, *, owner: str, repo: str, per_page: int = 100) -> int:
        count = 0
        for page in range(1, self.cfg.github_max_pages + 1):
            res = await self._client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "open", "per_page": per_page, "page": page},
            )
            await self._raise_for_status(res)
            data = res.json()
            if not isinstance(data, list) or len(data) == 0:
                break
            count += len(data)
            if len(data) < per_page:
                break
        return count

    async def count_open_issues(self, *, owner: str, repo: str, per_page: int = 100) -> int:
        """
        Count issues excluding PRs.
        GitHub issues endpoint returns PRs as issues with `pull_request` field.
        """
        count = 0
        for page in range(1, self.cfg.github_max_pages + 1):
            res = await self._client.get(
                f"/repos/{owner}/{repo}/issues",
                params={"state": "open", "per_page": per_page, "page": page},
            )
            await self._raise_for_status(res)
            data = res.json()
            if not isinstance(data, list) or len(data) == 0:
                break
            for item in data:
                if item.get("pull_request") is None:
                    count += 1
            if len(data) < per_page:
                break
        return count

    async def get_recent_commits(
        self, *, owner: str, repo: str, limit: int, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        res = await self._client.get(
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": min(max(limit, 1), per_page)},
        )
        await self._raise_for_status(res)
        data = res.json() if isinstance(res.json(), list) else []
        items: List[Dict[str, Any]] = []
        for c in data[:limit]:
            sha = c.get("sha", "")
            message = (c.get("commit") or {}).get("message", "") or ""
            date = ((c.get("commit") or {}).get("committer") or {}).get("date")
            items.append({"sha": sha, "message": message, "date": date})
        return items

    async def get_top_open_prs(
        self, *, owner: str, repo: str, limit: int, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        # MVP: use first page ordering (GitHub default) as "top".
        for page in range(1, self.cfg.github_max_pages + 1):
            res = await self._client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={"state": "open", "per_page": per_page, "page": page},
            )
            await self._raise_for_status(res)
            data = res.json()
            if not isinstance(data, list) or not data:
                return []
            out = []
            for item in data:
                if len(out) >= limit:
                    break
                out.append({"number": item.get("number"), "title": item.get("title")})
            if out:
                return out
        return []

    async def get_top_open_issues(
        self, *, owner: str, repo: str, limit: int, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for page in range(1, self.cfg.github_max_pages + 1):
            res = await self._client.get(
                f"/repos/{owner}/{repo}/issues",
                params={"state": "open", "per_page": per_page, "page": page},
            )
            await self._raise_for_status(res)
            data = res.json()
            if not isinstance(data, list) or not data:
                break
            for item in data:
                if item.get("pull_request") is not None:
                    continue
                if len(out) >= limit:
                    break
                out.append({"number": item.get("number"), "title": item.get("title")})
            if len(out) >= limit:
                break
        return out

    async def _raise_for_status(self, res: httpx.Response) -> None:
        if res.status_code in (200, 201):
            return
        if res.status_code == 403:
            # Often rate limit
            raise RuntimeError(f"GitHub API rate limit / forbidden: {res.text[:500]}")
        raise RuntimeError(f"GitHub API error {res.status_code}: {res.text[:500]}")

    @staticmethod
    def parse_repo_visibility(repo: Dict[str, Any]) -> RepoVisibility:
        return RepoVisibility.private if repo.get("private") is True else RepoVisibility.public

