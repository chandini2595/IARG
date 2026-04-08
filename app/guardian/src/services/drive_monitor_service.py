from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from src.config import Settings, settings
from src.services.drive_acl import build_risk_events, find_new_permissions
from src.services.drive_api_client import DriveAPIClient
from src.services.guardian_service import GuardianService
from src.services.storage import Storage

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveMonitorService:
    """
    Polls Google Drive ACLs for configured file/folder IDs, compares to last snapshot,
    and triggers ``google_drive_breach`` when new risky permissions appear.
    First successful poll per resource only establishes a baseline (no trigger).
    """

    def __init__(self, storage: Storage, guardian: GuardianService, cfg: Settings = settings):
        self.storage = storage
        self.guardian = guardian
        self.cfg = cfg

    def is_configured(self) -> bool:
        return bool(
            self.cfg.google_drive_client_id.strip()
            and self.cfg.google_drive_client_secret.strip()
            and self.cfg.google_drive_refresh_token.strip()
            and self.cfg.google_drive_monitored_ids_list
        )

    def _client(self) -> DriveAPIClient:
        return DriveAPIClient(
            client_id=self.cfg.google_drive_client_id,
            client_secret=self.cfg.google_drive_client_secret,
            refresh_token=self.cfg.google_drive_refresh_token,
        )

    def _expand_resource_ids_sync(self, client: DriveAPIClient, root_id: str) -> List[str]:
        ids: List[str] = [root_id]
        try:
            meta = client.get_file_metadata(root_id)
        except Exception:
            logger.exception("Drive get metadata failed", extra={"root_id": root_id})
            return ids
        if meta.get("mimeType") == FOLDER_MIME:
            try:
                children = client.list_folder_children(
                    root_id,
                    max_results=max(1, int(self.cfg.google_drive_folder_max_children)),
                )
                for ch in children:
                    cid = ch.get("id")
                    if cid:
                        ids.append(cid)
            except Exception:
                logger.exception("Drive list children failed", extra={"folder_id": root_id})
        return list(dict.fromkeys(ids))

    async def poll_once(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        if not self.cfg.google_drive_monitor_enabled:
            return {"ok": True, "skipped": True, "reason": "google_drive_monitor_enabled is false"}

        if not self.is_configured():
            await self.storage.set_drive_monitor_meta(
                last_poll_at=now,
                ok=False,
                error="Missing client_id, client_secret, refresh_token, or monitored IDs",
            )
            return {"ok": False, "skipped": True, "reason": "not_configured"}

        allowed: Set[str] = set(self.cfg.google_drive_allowed_email_domains_set)
        flag_domain = bool(self.cfg.google_drive_flag_domain_shares)

        def run_sync() -> Dict[str, Any]:
            client = self._client()
            all_targets: List[str] = []
            for root in self.cfg.google_drive_monitored_ids_list:
                all_targets.extend(self._expand_resource_ids_sync(client, root))
            all_targets = list(dict.fromkeys(all_targets))

            breaches_to_fire: List[Dict[str, Any]] = []
            resources_checked = 0
            errors: List[str] = []

            for rid in all_targets:
                resources_checked += 1
                try:
                    perms = client.list_permissions(rid)
                except Exception as e:
                    errors.append(f"{rid}: {e!s}")
                    continue

                row = self.storage.get_drive_acl_snapshot_sync(rid)
                old_json = row["permissions_json"] if row else "[]"
                try:
                    old_perms = json.loads(old_json)
                    if not isinstance(old_perms, list):
                        old_perms = []
                except Exception:
                    old_perms = []

                if not row:
                    self.storage.upsert_drive_acl_snapshot_sync(rid, perms, now)
                    continue

                new_only = find_new_permissions(old_perms, perms)
                events = build_risk_events(
                    new_only,
                    allowed_email_domains=allowed,
                    flag_domain_shares=flag_domain,
                )

                self.storage.upsert_drive_acl_snapshot_sync(rid, perms, now)

                if events:
                    desc_parts = []
                    for ev in events:
                        p = ev.get("permission") or {}
                        desc_parts.append(
                            f"{ev.get('breach_category')}: {p.get('type')} "
                            f"role={p.get('role')} email={p.get('emailAddress')} domain={p.get('domain')}"
                        )
                    description = "; ".join(desc_parts)
                    primary_cat = str(events[0]["breach_category"])
                    acl_block = {
                        "resource_id": rid,
                        "new_events": events,
                        "permission_count": len(perms),
                    }
                    breaches_to_fire.append(
                        {
                            "resource_id": rid,
                            "breach_category": primary_cat,
                            "description": description,
                            "acl_evidence": acl_block,
                        }
                    )

            return {
                "breaches": breaches_to_fire,
                "resources_checked": resources_checked,
                "errors": errors,
            }

        result = await asyncio.to_thread(run_sync)

        insurance_triggers = 0
        handler_failed = False
        for sb in result.get("breaches") or []:
            try:
                br = await self.guardian.google_drive_breach(
                    resource_id=sb["resource_id"],
                    breach_category=sb["breach_category"],
                    description=sb["description"],
                    detected_at=now,
                    detection_source="drive_api_poll",
                    acl_evidence=sb["acl_evidence"],
                )
                if br.get("insurance_triggered"):
                    insurance_triggers += 1
            except Exception:
                handler_failed = True
                logger.exception("google_drive_breach failed after ACL detection")

        err_parts = list(result.get("errors") or [])
        if handler_failed:
            err_parts.append("breach handler failed")
        err_text = "; ".join(err_parts)[:2000] or None
        poll_ok = not err_parts
        await self.storage.set_drive_monitor_meta(
            last_poll_at=now,
            ok=poll_ok,
            error=err_text,
        )

        return {
            "ok": poll_ok,
            "resources_checked": result.get("resources_checked", 0),
            "breach_reports": len(result.get("breaches") or []),
            "insurance_triggers": insurance_triggers,
            "errors": result.get("errors", []),
        }
