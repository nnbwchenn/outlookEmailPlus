from __future__ import annotations

import unittest

from tests._import_app import clear_login_attempts, import_web_app_module


class MailboxResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()
        cls.app = cls.module.app

    def setUp(self):
        with self.app.app_context():
            clear_login_attempts()
            from outlook_web.db import get_db

            db = get_db()
            db.execute("DELETE FROM accounts WHERE email LIKE '%@resolver.test'")
            db.commit()

    def test_resolve_mailbox_returns_account_descriptor_for_regular_account(self):
        with self.app.app_context():
            from outlook_web.db import get_db
            from outlook_web.services import mailbox_resolver

            db = get_db()
            db.execute(
                """
                INSERT INTO accounts (email, password, client_id, refresh_token, group_id, status, account_type, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "user@resolver.test",
                    "pw",
                    "cid",
                    "rt",
                    1,
                    "active",
                    "outlook",
                    "outlook",
                ),
            )
            db.commit()

            mailbox = mailbox_resolver.resolve_mailbox("user@resolver.test")

        self.assertEqual(mailbox["kind"], "account")
        self.assertEqual(mailbox["email"], "user@resolver.test")
        self.assertEqual(mailbox["read_capability"], "graph")

    def test_resolve_mailbox_supports_plus_alias_lookup(self):
        with self.app.app_context():
            from outlook_web.db import get_db
            from outlook_web.services import mailbox_resolver

            db = get_db()
            db.execute(
                """
                INSERT INTO accounts (email, password, client_id, refresh_token, group_id, status, account_type, provider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "alias@resolver.test",
                    "pw",
                    "cid",
                    "rt",
                    1,
                    "active",
                    "outlook",
                    "outlook",
                ),
            )
            db.commit()

            mailbox = mailbox_resolver.resolve_mailbox("alias+signup@resolver.test")

        self.assertEqual(mailbox["kind"], "account")
        self.assertEqual(mailbox["email"], "alias@resolver.test")


if __name__ == "__main__":
    unittest.main()
