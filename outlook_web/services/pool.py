"""
邮箱池服务层（PRD-00009 MT-1）

职责：
- 输入校验（caller_id / task_id / lease_seconds / result / detail 长度）
- 读取 settings（在 Flask app_context 下用 get_db，或直接接受 conn）
- 调用 repositories/pool.py 的原子操作
- 将 repository 层的异常转换为业务错误码
"""

from __future__ import annotations

import logging

from outlook_web.db import create_sqlite_connection
from outlook_web.repositories import pool as pool_repo

logger = logging.getLogger(__name__)

CALLER_ID_MAX_LEN = 64
TASK_ID_MAX_LEN = 128
PROJECT_KEY_MAX_LEN = 128
EMAIL_DOMAIN_MAX_LEN = 128
REASON_MAX_LEN = 256
DETAIL_MAX_LEN = 512

VALID_RESULTS = set(pool_repo.RESULT_TO_POOL_STATUS.keys())

# 支持的 provider 白名单（空字符串视为 None，不做校验）
VALID_PROVIDERS = {"outlook", "imap", "custom"}


def _validate_provider(provider: str | None) -> str | None:
    """
    校验 provider 参数。

    - 空字符串视为 None
    - 非空时校验是否在 VALID_PROVIDERS 中
    - 返回规范化后的 provider（None 或有效值）
    """
    if provider is None:
        return None
    p = provider.strip()
    if not p:
        return None
    if p not in VALID_PROVIDERS:
        raise PoolServiceError(
            f"provider 必须是 {sorted(VALID_PROVIDERS)} 之一，或留空",
            "invalid_provider",
        )
    return p


class PoolServiceError(Exception):
    """业务错误，包含 HTTP 状态码和错误码。"""

    def __init__(self, message: str, error_code: str, http_status: int = 400):
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status


def _validate_caller_id(caller_id: str) -> None:
    if not caller_id or not caller_id.strip():
        raise PoolServiceError("caller_id 不能为空", "caller_id_empty")
    if len(caller_id) > CALLER_ID_MAX_LEN:
        raise PoolServiceError(f"caller_id 超过最大长度 {CALLER_ID_MAX_LEN}", "caller_id_too_long")


def _validate_task_id(task_id: str) -> None:
    if not task_id or not task_id.strip():
        raise PoolServiceError("task_id 不能为空", "task_id_empty")
    if len(task_id) > TASK_ID_MAX_LEN:
        raise PoolServiceError(f"task_id 超过最大长度 {TASK_ID_MAX_LEN}", "task_id_too_long")


def _validate_lease_seconds(lease_seconds: int, max_lease: int = 3600) -> None:
    if lease_seconds <= 0:
        raise PoolServiceError("lease_seconds 必须大于 0", "lease_seconds_invalid")
    if lease_seconds > max_lease:
        raise PoolServiceError(f"lease_seconds 不能超过 {max_lease} 秒", "lease_seconds_too_large")


def _validate_project_key(project_key: str | None) -> str | None:
    if project_key is None:
        return None
    pk = project_key.strip()
    if not pk:
        return None
    if len(pk) > PROJECT_KEY_MAX_LEN:
        raise PoolServiceError(f"project_key 超过最大长度 {PROJECT_KEY_MAX_LEN}", "project_key_too_long")
    return pk


def _validate_email_domain(email_domain: str | None) -> str | None:
    if email_domain is None:
        return None
    d = email_domain.strip().lower()
    if not d:
        return None
    if len(d) > EMAIL_DOMAIN_MAX_LEN:
        raise PoolServiceError(f"email_domain 超过最大长度 {EMAIL_DOMAIN_MAX_LEN}", "email_domain_too_long")
    return d


def _read_settings_via_conn(conn) -> dict:
    """在独立连接场景下直接从 settings 表读取池相关配置。"""
    rows = conn.execute(
        "SELECT key, value FROM settings WHERE key IN (?, ?)",
        ("pool_cooldown_seconds", "pool_default_lease_seconds"),
    ).fetchall()
    result = {"pool_cooldown_seconds": 86400, "pool_default_lease_seconds": 600}
    for row in rows:
        try:
            result[row["key"]] = int(row["value"])
        except (TypeError, ValueError):
            pass
    return result


def _is_project_reuse_eligible_account(
    *,
    claimed_project_key: str | None,
) -> bool:
    """判定账号是否适用项目维度成功复用路径 (FD §2.1)。

    门控：claimed_project_key 非空 — 必须在 claim 时显式传入
    """
    return claimed_project_key


def claim_random(
    *,
    caller_id: str,
    task_id: str,
    provider: str | None = None,
    project_key: str | None = None,
    email_domain: str | None = None,
) -> dict:
    _validate_caller_id(caller_id)
    _validate_task_id(task_id)
    provider = _validate_provider(provider)
    project_key = _validate_project_key(project_key)
    email_domain = _validate_email_domain(email_domain)

    conn = create_sqlite_connection()
    try:
        settings = _read_settings_via_conn(conn)
        default_lease = settings["pool_default_lease_seconds"]
        _validate_lease_seconds(default_lease)

        try:
            account = pool_repo.claim_atomic(
                conn,
                caller_id=caller_id,
                task_id=task_id,
                lease_seconds=default_lease,
                provider=provider,
                project_key=project_key,
                email_domain=email_domain,
            )
        except pool_repo.PoolRepositoryError as e:
            # 将 Repository 层异常转换为 Service 层异常
            raise PoolServiceError(str(e), e.error_code, http_status=500) from e

        if account is not None:
            return account

        raise PoolServiceError("池中没有符合条件的可用邮箱", "no_available_account", http_status=200)
    finally:
        conn.close()


def _validate_claim_ownership(
    row: dict | None,
    *,
    action: str,
    claim_token: str,
    caller_id: str,
    task_id: str,
) -> None:
    """校验 release/complete 的领取归属。"""
    if row is None:
        raise PoolServiceError("账号不存在", "account_not_found", http_status=400)
    if row.get("pool_status") != "claimed":
        raise PoolServiceError(
            f"账号当前状态为 '{row.get('pool_status')}'，无法 {action}",
            "not_claimed",
            http_status=409,
        )
    if row.get("claim_token") != claim_token:
        raise PoolServiceError("claim_token 不匹配", "token_mismatch", http_status=403)
    if row.get("claimed_by") != f"{caller_id}:{task_id}":
        raise PoolServiceError(
            "caller_id 或 task_id 与领取记录不一致",
            "caller_mismatch",
            http_status=403,
        )


def release_claim(
    *,
    account_id: int,
    claim_token: str,
    caller_id: str,
    task_id: str,
    reason: str | None = None,
) -> None:
    """释放已领取的邮箱账号（不计入成功/失败统计，直接回 available）。"""
    _validate_caller_id(caller_id)
    _validate_task_id(task_id)
    if not claim_token or not claim_token.strip():
        raise PoolServiceError("claim_token 不能为空", "claim_token_empty")
    if reason and len(reason) > REASON_MAX_LEN:
        raise PoolServiceError(f"reason 超过最大长度 {REASON_MAX_LEN}", "reason_too_long")

    conn = create_sqlite_connection()
    try:
        row = conn.execute(
            "SELECT id, claim_token, claimed_by, pool_status FROM accounts WHERE id = ?",
            (account_id,),
        ).fetchone()
        _validate_claim_ownership(
            dict(row) if row is not None else None,
            action="release",
            claim_token=claim_token,
            caller_id=caller_id,
            task_id=task_id,
        )

        pool_repo.release(conn, account_id, claim_token, caller_id, task_id, reason)
    finally:
        conn.close()


def complete_claim(
    *,
    account_id: int,
    claim_token: str,
    caller_id: str,
    task_id: str,
    result: str,
    detail: str | None = None,
) -> str:
    """
    标记领取结果并驱动状态机流转。

    返回账号的新 pool_status。
    """
    _validate_caller_id(caller_id)
    _validate_task_id(task_id)
    if not claim_token or not claim_token.strip():
        raise PoolServiceError("claim_token 不能为空", "claim_token_empty")
    if result not in VALID_RESULTS:
        raise PoolServiceError(
            f"result 必须是 {sorted(VALID_RESULTS)} 之一",
            "invalid_result",
        )
    if detail and len(detail) > DETAIL_MAX_LEN:
        raise PoolServiceError(f"detail 超过最大长度 {DETAIL_MAX_LEN}", "detail_too_long")

    conn = create_sqlite_connection()
    try:
        row = conn.execute(
            """
            SELECT id, email, provider, account_type,
                   claimed_project_key,
                   claim_token, claimed_by, pool_status
            FROM accounts
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()
        _validate_claim_ownership(
            dict(row) if row is not None else None,
            action="complete",
            claim_token=claim_token,
            caller_id=caller_id,
            task_id=task_id,
        )

        # 从 claim 上下文读取 claimed_project_key，而非依赖 API 入参
        # 保证 claim-complete 即使未传 project_key 也能正确判定复用路径（TDD §4.1 N-03）
        claimed_project_key = str(row["claimed_project_key"] or "").strip() or None
        enable_project_reuse = _is_project_reuse_eligible_account(
            claimed_project_key=claimed_project_key,
        )

        # complete 先更新本地状态（事务内）
        new_status = pool_repo.complete(
            conn,
            account_id,
            claim_token,
            caller_id,
            task_id,
            result,
            detail,
            claimed_project_key=claimed_project_key,
            enable_project_reuse=enable_project_reuse,
        )

        return new_status
    finally:
        conn.close()


def get_claim_context(*, claim_token: str) -> dict | None:
    """
    根据 claim_token 查询领取上下文（email / claimed_at / email_domain 等）。
    返回 dict 或 None（token 不存在时）。
    """
    if not claim_token or not claim_token.strip():
        return None
    conn = create_sqlite_connection()
    try:
        return pool_repo.get_claim_context(conn, claim_token.strip())
    finally:
        conn.close()


def append_claim_read_context(
    *,
    account_id: int,
    claim_token: str,
    caller_id: str,
    task_id: str,
    detail: str | None = None,
) -> None:
    """
    追加一条读取上下文日志（claim 邮箱被用于邮件读取时记录）。
    """
    if not claim_token or not claim_token.strip():
        return
    conn = create_sqlite_connection()
    try:
        pool_repo.append_claim_read_context(conn, account_id, claim_token, caller_id, task_id, detail)
    finally:
        conn.close()


def get_pool_stats() -> dict:
    """返回池状态统计（不修改任何数据）。"""
    conn = create_sqlite_connection()
    try:
        return pool_repo.get_stats(conn)
    finally:
        conn.close()
