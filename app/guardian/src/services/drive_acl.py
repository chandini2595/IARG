from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


def normalize_permission(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": p.get("id"),
        "type": p.get("type"),
        "emailAddress": p.get("emailAddress"),
        "domain": (p.get("domain") or "").lower() or None,
        "role": p.get("role"),
        "allowFileDiscovery": bool(p.get("allowFileDiscovery")),
    }


def find_new_permissions(old: List[Dict[str, Any]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    old_ids = {p.get("id") for p in old if p.get("id")}
    return [p for p in new if p.get("id") and p.get("id") not in old_ids]


def classify_new_permission_risk(
    perm: Dict[str, Any],
    *,
    allowed_email_domains: Set[str],
    flag_domain_shares: bool,
) -> Optional[str]:
    """
    Return a breach_category if this *new* permission is considered risky, else None.

    - ``anyone``: public / link sharing — always data_exposure.
    - ``domain``: optional (flag_domain_shares); outside allowlist => unauthorized_access.
    - ``user``: only if allowed_email_domains is non-empty and email domain not in set.
    """
    t = perm.get("type")
    if t == "anyone":
        return "data_exposure"

    if t == "domain":
        if not flag_domain_shares:
            return None
        dom = (perm.get("domain") or "").lower()
        if allowed_email_domains:
            if dom and dom not in allowed_email_domains:
                return "unauthorized_access"
            return None
        return "unauthorized_access"

    if t == "user":
        if not allowed_email_domains:
            return None
        email = (perm.get("emailAddress") or "").lower()
        if not email or "@" not in email:
            return None
        dom = email.split("@")[-1]
        if dom not in allowed_email_domains:
            return "unauthorized_access"

    return None


def build_risk_events(
    new_permissions: List[Dict[str, Any]],
    *,
    allowed_email_domains: Set[str],
    flag_domain_shares: bool,
) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for p in new_permissions:
        cat = classify_new_permission_risk(
            p,
            allowed_email_domains=allowed_email_domains,
            flag_domain_shares=flag_domain_shares,
        )
        if cat:
            events.append(
                {
                    "breach_category": cat,
                    "permission": normalize_permission(p),
                }
            )
    return events
