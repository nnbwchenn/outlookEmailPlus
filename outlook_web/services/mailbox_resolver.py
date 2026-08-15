from __future__ import annotations

from typing import Any

from outlook_web.repositories import accounts as accounts_repo
from outlook_web.security.auth import get_external_api_consumer


def _external_api_service():
    from outlook_web.services import external_api as external_api_service

    return external_api_service


def normalize_alias_email(email_addr: str | None) -> str | None:
    """剥离邮箱别名后缀，返回主地址。

    Outlook/大多数邮箱服务商支持 + 子地址：user+tag@domain → user@domain。
    本函数将 user+anything@domain 规范化为 user@domain，使系统能正确
    将别名地址回溯到主账号。

    不含 + 的地址原样返回。
    """
    if email_addr is None:
        return None
    if not email_addr or "@" not in email_addr:
        return email_addr
    local, domain = email_addr.rsplit("@", 1)
    if "+" in local:
        local = local[: local.index("+")]
    return f"{local}@{domain}"


def resolve_mailbox(email_addr: str) -> dict[str, Any]:
    external_api_service = _external_api_service()
    normalized_email = normalize_alias_email(str(email_addr or "").strip()) or ""
    if not normalized_email or "@" not in normalized_email:
        raise external_api_service.InvalidParamError("email 参数无效")

    account = accounts_repo.get_account_by_email(normalized_email)
    if account:
        return {
            "kind": "account",
            "email": normalized_email,
            "source": str(account.get("provider") or account.get("account_type") or "outlook"),
            "provider_name": (
                "imap_generic" if str(account.get("account_type") or "").strip().lower() == "imap" else "outlook_graph"
            ),
            "status": str(account.get("status") or "active"),
            "read_capability": "imap" if str(account.get("account_type") or "").strip().lower() == "imap" else "graph",
            "meta": {"account": account},
        }

    raise external_api_service.AccountNotFoundError("账号不存在", data={"email": normalized_email})


def ensure_mailbox_can_read(
    mailbox: dict[str, Any],
    *,
    consumer: dict[str, Any] | None = None,
    allow_finished: bool = False,
) -> dict[str, Any]:
    external_api_service = _external_api_service()
    consumer = consumer or get_external_api_consumer() or {}
    kind = str(mailbox.get("kind") or "")

    if kind == "account":
        allowed_emails = [str(item or "").strip().lower() for item in (consumer.get("allowed_emails") or [])]
        target_email = str(mailbox.get("email") or "").strip().lower()
        if allowed_emails and target_email not in allowed_emails:
            raise external_api_service.EmailScopeForbiddenError(
                "当前 API Key 无权访问该邮箱",
                data={
                    "email": mailbox.get("email"),
                    "consumer_id": consumer.get("id"),
                    "consumer_name": consumer.get("name"),
                },
            )
        return external_api_service.ensure_account_can_read((mailbox.get("meta") or {}).get("account") or {})

    raise external_api_service.AccountNotFoundError("账号不存在", data={"email": mailbox.get("email")})


def ensure_mailbox_can_mutate(
    mailbox: dict[str, Any],
    *,
    consumer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ensure_mailbox_can_read(mailbox, consumer=consumer, allow_finished=False)
