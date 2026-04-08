from __future__ import annotations

from src.services.drive_acl import build_risk_events, find_new_permissions


def test_find_new_permissions() -> None:
    old = [{"id": "a", "type": "user", "emailAddress": "x@co.com"}]
    new = [
        {"id": "a", "type": "user", "emailAddress": "x@co.com"},
        {"id": "b", "type": "anyone", "role": "reader"},
    ]
    assert len(find_new_permissions(old, new)) == 1
    assert find_new_permissions(old, new)[0]["id"] == "b"


def test_anyone_triggers_data_exposure() -> None:
    new = [{"id": "z", "type": "anyone", "role": "reader"}]
    ev = build_risk_events(new, allowed_email_domains=set(), flag_domain_shares=False)
    assert len(ev) == 1
    assert ev[0]["breach_category"] == "data_exposure"


def test_user_outside_allowed_domains() -> None:
    new = [{"id": "u1", "type": "user", "emailAddress": "a@evil.com", "role": "reader"}]
    allowed = {"myorg.com"}
    ev = build_risk_events(new, allowed_email_domains=allowed, flag_domain_shares=False)
    assert len(ev) == 1
    assert ev[0]["breach_category"] == "unauthorized_access"


def test_user_inside_allowed_domains_no_event() -> None:
    new = [{"id": "u1", "type": "user", "emailAddress": "a@myorg.com", "role": "reader"}]
    allowed = {"myorg.com"}
    ev = build_risk_events(new, allowed_email_domains=allowed, flag_domain_shares=False)
    assert ev == []


def test_domain_share_when_flagged() -> None:
    new = [{"id": "d1", "type": "domain", "domain": "partner.com", "role": "reader"}]
    ev = build_risk_events(new, allowed_email_domains=set(), flag_domain_shares=True)
    assert len(ev) == 1
