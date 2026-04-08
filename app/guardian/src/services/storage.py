from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4


class Storage:
    """
    Simple SQLite persistence layer.

    Uses synchronous `sqlite3` but exposes async methods by running operations
    in a thread via `asyncio.to_thread` to keep FastAPI event loop responsive.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL;")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS monitor_state (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    candidate_repos_json TEXT NOT NULL DEFAULT '[]',
                    selected_repo TEXT,
                    last_scan_at TEXT,
                    latest_risk_score REAL,
                    latest_risk_level TEXT,
                    latest_risk_json TEXT
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_history (
                    scan_id TEXT PRIMARY KEY,
                    repo_full_name TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    commits_last_window INTEGER NOT NULL,
                    open_prs INTEGER NOT NULL,
                    open_issues INTEGER NOT NULL,
                    visibility TEXT NOT NULL,
                    repo_size_kb INTEGER NOT NULL,
                    last_pushed_at TEXT,
                    risk_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,
                    risk_explanation_json TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insurance_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    purchase_id TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS insurance_purchases (
                    purchase_id TEXT PRIMARY KEY,
                    repo_full_name TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    policy_name TEXT NOT NULL,
                    triggered_risk_score REAL NOT NULL,
                    triggered_risk_level TEXT NOT NULL,
                    premium REAL NOT NULL,
                    payout REAL NOT NULL,
                    status TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    evidence_id TEXT
                );
                """
            )

            conn.execute(
                """
                INSERT OR IGNORE INTO monitor_state
                    (id, candidate_repos_json, selected_repo, last_scan_at, latest_risk_score, latest_risk_level, latest_risk_json)
                VALUES
                    (1, '[]', NULL, NULL, NULL, NULL, NULL)
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drive_acl_snapshots (
                    resource_id TEXT PRIMARY KEY,
                    permissions_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS drive_monitor_meta (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    last_poll_at TEXT,
                    last_poll_ok INTEGER,
                    last_error TEXT
                );
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO drive_monitor_meta (id, last_poll_at, last_poll_ok, last_error)
                VALUES (1, NULL, NULL, NULL)
                """
            )

            conn.commit()
        finally:
            conn.close()

    async def upsert_monitor_state(
        self,
        *,
        candidate_repos: List[str],
        selected_repo: str,
        last_scan_at: datetime,
        latest_risk_score: float,
        latest_risk_level: str,
        latest_risk_json: Dict[str, Any],
    ) -> None:
        await asyncio.to_thread(
            self._upsert_monitor_state_sync,
            candidate_repos,
            selected_repo,
            last_scan_at,
            latest_risk_score,
            latest_risk_level,
            latest_risk_json,
        )

    def _upsert_monitor_state_sync(
        self,
        candidate_repos: List[str],
        selected_repo: str,
        last_scan_at: datetime,
        latest_risk_score: float,
        latest_risk_level: str,
        latest_risk_json: Dict[str, Any],
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE monitor_state
                SET candidate_repos_json = ?,
                    selected_repo = ?,
                    last_scan_at = ?,
                    latest_risk_score = ?,
                    latest_risk_level = ?,
                    latest_risk_json = ?
                WHERE id = 1
                """,
                (
                    json.dumps(candidate_repos),
                    selected_repo,
                    last_scan_at.isoformat(),
                    latest_risk_score,
                    latest_risk_level,
                    json.dumps(latest_risk_json, default=str),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def get_monitor_summary(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self._get_monitor_summary_sync)

    def _get_monitor_summary_sync(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM monitor_state WHERE id = 1").fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    async def record_risk_history(
        self,
        *,
        scan_id: UUID,
        repo_full_name: str,
        scanned_at: datetime,
        metrics: Dict[str, Any],
        risk_score: float,
        risk_level: str,
        risk_explanation_json: Dict[str, Any],
    ) -> None:
        await asyncio.to_thread(
            self._record_risk_history_sync,
            scan_id,
            repo_full_name,
            scanned_at,
            metrics,
            risk_score,
            risk_level,
            risk_explanation_json,
        )

    def _record_risk_history_sync(
        self,
        scan_id: UUID,
        repo_full_name: str,
        scanned_at: datetime,
        metrics: Dict[str, Any],
        risk_score: float,
        risk_level: str,
        risk_explanation_json: Dict[str, Any],
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO risk_history (
                    scan_id,
                    repo_full_name,
                    scanned_at,
                    commits_last_window,
                    open_prs,
                    open_issues,
                    visibility,
                    repo_size_kb,
                    last_pushed_at,
                    risk_score,
                    risk_level,
                    risk_explanation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(scan_id),
                    repo_full_name,
                    scanned_at.isoformat(),
                    int(metrics["commits_last_window"]),
                    int(metrics["open_prs"]),
                    int(metrics["open_issues"]),
                    str(metrics["visibility"]),
                    int(metrics["repo_size_kb"]),
                    metrics.get("last_pushed_at"),
                    float(risk_score),
                    str(risk_level),
                    json.dumps(risk_explanation_json, default=str),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def get_last_purchase_for_repo(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_last_purchase_for_repo_sync, repo_full_name)

    def _get_last_purchase_for_repo_sync(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM insurance_purchases
                WHERE repo_full_name = ?
                  AND status = 'triggered'
                ORDER BY triggered_at DESC
                LIMIT 1
                """,
                (repo_full_name,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    async def create_purchase_with_evidence(
        self,
        *,
        repo_full_name: str,
        policy_id: str,
        policy_name: str,
        triggered_risk_score: float,
        triggered_risk_level: str,
        premium: float,
        payout: float,
        triggered_at: datetime,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self._create_purchase_with_evidence_sync,
            repo_full_name,
            policy_id,
            policy_name,
            triggered_risk_score,
            triggered_risk_level,
            premium,
            payout,
            triggered_at,
            evidence,
        )

    def _create_purchase_with_evidence_sync(
        self,
        repo_full_name: str,
        policy_id: str,
        policy_name: str,
        triggered_risk_score: float,
        triggered_risk_level: str,
        premium: float,
        payout: float,
        triggered_at: datetime,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        purchase_id = uuid4()
        evidence_id = uuid4()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO insurance_evidence (
                    evidence_id,
                    purchase_id,
                    evidence_json,
                    created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (str(evidence_id), str(purchase_id), json.dumps(evidence, default=str), triggered_at.isoformat()),
            )

            conn.execute(
                """
                INSERT INTO insurance_purchases (
                    purchase_id,
                    repo_full_name,
                    policy_id,
                    policy_name,
                    triggered_risk_score,
                    triggered_risk_level,
                    premium,
                    payout,
                    status,
                    triggered_at,
                    evidence_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(purchase_id),
                    repo_full_name,
                    policy_id,
                    policy_name,
                    float(triggered_risk_score),
                    str(triggered_risk_level),
                    float(premium),
                    float(payout),
                    "triggered",
                    triggered_at.isoformat(),
                    str(evidence_id),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {"purchase_id": purchase_id, "evidence_id": evidence_id}

    async def list_purchases(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._list_purchases_sync, limit, offset)

    def _list_purchases_sync(self, limit: int, offset: int) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM insurance_purchases
                ORDER BY triggered_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    async def get_purchase_detail(self, purchase_id: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        return await asyncio.to_thread(self._get_purchase_detail_sync, purchase_id)

    def _get_purchase_detail_sync(
        self, purchase_id: str
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        conn = self._connect()
        try:
            purchase_row = conn.execute(
                """
                SELECT *
                FROM insurance_purchases
                WHERE purchase_id = ?
                """,
                (purchase_id,),
            ).fetchone()
            if not purchase_row:
                return None

            evidence_id = purchase_row["evidence_id"]
            evidence_row = conn.execute(
                """
                SELECT *
                FROM insurance_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
            return (dict(purchase_row), dict(evidence_row) if evidence_row else {})
        finally:
            conn.close()

    def get_drive_acl_snapshot_sync(self, resource_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM drive_acl_snapshots WHERE resource_id = ?",
                (resource_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def upsert_drive_acl_snapshot_sync(
        self,
        resource_id: str,
        permissions: List[Dict[str, Any]],
        updated_at: datetime,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO drive_acl_snapshots (resource_id, permissions_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(resource_id) DO UPDATE SET
                    permissions_json = excluded.permissions_json,
                    updated_at = excluded.updated_at
                """,
                (resource_id, json.dumps(permissions, default=str), updated_at.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def set_drive_monitor_meta_sync(
        self,
        *,
        last_poll_at: datetime,
        ok: bool,
        error: Optional[str],
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE drive_monitor_meta
                SET last_poll_at = ?, last_poll_ok = ?, last_error = ?
                WHERE id = 1
                """,
                (last_poll_at.isoformat(), 1 if ok else 0, error),
            )
            conn.commit()
        finally:
            conn.close()

    def get_drive_monitor_meta_sync(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM drive_monitor_meta WHERE id = 1").fetchone()
            return dict(row) if row else {}
        finally:
            conn.close()

    async def set_drive_monitor_meta(
        self,
        *,
        last_poll_at: datetime,
        ok: bool,
        error: Optional[str],
    ) -> None:
        await asyncio.to_thread(
            self.set_drive_monitor_meta_sync,
            last_poll_at=last_poll_at,
            ok=ok,
            error=error,
        )

    async def get_drive_monitor_meta(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self.get_drive_monitor_meta_sync)

