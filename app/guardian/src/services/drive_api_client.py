from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


class DriveAPIClient:
    """Sync Google Drive API v3 client (call from asyncio.to_thread)."""

    def __init__(self, *, client_id: str, client_secret: str, refresh_token: str):
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._refresh_token = refresh_token.strip()
        self._creds: Optional[Credentials] = None

    def _credentials(self) -> Credentials:
        if self._creds and self._creds.valid:
            return self._creds
        self._creds = Credentials(
            token=None,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=[DRIVE_READONLY_SCOPE],
        )
        self._creds.refresh(Request())
        return self._creds

    def service(self):
        return build("drive", "v3", credentials=self._credentials(), cache_discovery=False)

    def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        svc = self.service()
        return (
            svc.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType",
                supportsAllDrives=True,
            )
            .execute()
        )

    def list_permissions(self, file_id: str) -> List[Dict[str, Any]]:
        svc = self.service()
        out: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            req = (
                svc.permissions()
                .list(
                    fileId=file_id,
                    supportsAllDrives=True,
                    pageSize=100,
                    pageToken=page_token,
                    fields="nextPageToken, permissions(id,type,emailAddress,domain,role,allowFileDiscovery)",
                )
            )
            try:
                resp = req.execute()
            except HttpError as e:
                logger.warning("Drive permissions.list failed", extra={"file_id": file_id, "error": str(e)})
                raise
            out.extend(resp.get("permissions") or [])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def list_folder_children(self, folder_id: str, *, max_results: int) -> List[Dict[str, Any]]:
        svc = self.service()
        out: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        q = f"'{folder_id}' in parents and trashed = false"
        while len(out) < max_results:
            page_size = min(100, max_results - len(out))
            resp = (
                svc.files()
                .list(
                    q=q,
                    pageSize=page_size,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    fields="nextPageToken, files(id,name,mimeType)",
                )
                .execute()
            )
            batch = resp.get("files") or []
            out.extend(batch)
            page_token = resp.get("nextPageToken")
            if not page_token or len(out) >= max_results:
                break
        return out[:max_results]
