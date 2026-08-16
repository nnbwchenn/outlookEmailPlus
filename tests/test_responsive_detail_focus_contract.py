"""响应式 detail-focus 机制与 groups 折叠 — 前端契约测试

覆盖范围:
  - HTML 结构: btnToggleGroups、tempEmailDetailSection 默认 display:none、CSS 版本号
  - CSS 契约: 平板/移动端断点中 detail-focus 和 groups-expanded 规则存在
  - JS 契约: emails.js 导出 setMailboxDetailFocus/setTempDetailFocus、main.js 导出 toggleGroupsColumn
  - i18n 契约: 「展开分组」「收起分组」翻译词条
"""

from __future__ import annotations

import re
import unittest

from tests._import_app import import_web_app_module


class ResponsiveDetailFocusContractTests(unittest.TestCase):
    """响应式 detail-focus 机制前端契约测试"""

    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()
        cls.app = cls.module.app

    def _login(self, client, password: str = "testpass123"):
        resp = client.post("/login", json={"password": password})
        self.assertEqual(resp.status_code, 200)

    def _get_index_html(self) -> str:
        client = self.app.test_client()
        self._login(client)
        resp = client.get("/")
        try:
            return resp.data.decode("utf-8")
        finally:
            resp.close()

    # ==================== HTML 结构测试 ====================

    def test_btn_toggle_groups_exists_in_accounts_column(self):
        """btnToggleGroups 按钮应存在于 accounts-column header 中"""
        html = self._get_index_html()
        self.assertIn('id="btnToggleGroups"', html)
        self.assertIn("toggleGroupsColumn()", html)
        self.assertIn("btn-toggle-groups", html)

    def test_email_detail_section_default_hidden(self):
        """emailDetailSection 应默认 display:none（移动端/平板端由 JS 控制）"""
        html = self._get_index_html()
        self.assertIn('id="emailDetailSection"', html)
        section = re.search(r'id="emailDetailSection"[^>]*>', html)
        self.assertIsNotNone(section)
        self.assertIn("display:none", section.group(0))

    def test_email_list_panel_exists(self):
        """emailListPanel 应存在于 mailbox workspace 中"""
        html = self._get_index_html()
        self.assertIn('id="emailListPanel"', html)

    def test_css_version_includes_resp_suffix(self):
        """CSS 引用应包含 -resp 版本标识"""
        html = self._get_index_html()
        self.assertIn("-resp", html)

    # ==================== JS 函数导出测试 ====================

    def test_emails_js_contains_detail_focus_functions(self):
        """emails.js 应包含 setMailboxDetailFocus"""
        from pathlib import Path

        emails_js = Path("static/js/features/emails.js").read_text(encoding="utf-8")
        self.assertIn("function setMailboxDetailFocus", emails_js)
        self.assertIn("function isNarrowWorkspaceViewport", emails_js)

    def test_main_js_contains_toggle_groups_column(self):
        """main.js 应包含 toggleGroupsColumn 和 handleResponsiveGroups"""
        from pathlib import Path

        main_js = Path("static/js/main.js").read_text(encoding="utf-8")
        self.assertIn("function toggleGroupsColumn", main_js)
        self.assertIn("function handleResponsiveGroups", main_js)

    # ==================== CSS 断点规则测试 ====================

    def test_css_tablet_has_detail_focus_rules(self):
        """平板断点 (769-1024px) 应包含 detail-focus 和 groups 折叠规则"""
        from pathlib import Path

        css = Path("static/css/main.css").read_text(encoding="utf-8")
        tablet_section = re.search(
            r"@media\s*\(max-width:\s*1024px\)\s+and\s+\(min-width:\s*769px\).*?(?=@media)",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(tablet_section, "应找到平板断点 @media 块")
        tablet = tablet_section.group(0)
        self.assertIn("detail-focus", tablet)
        self.assertIn("groups-column", tablet)
        self.assertIn("groups-expanded", tablet)
        self.assertIn("btn-toggle-groups", tablet)

    def test_css_mobile_has_detail_focus_rules(self):
        """移动端断点 (<=768px) 应包含 detail-focus 规则"""
        from pathlib import Path

        css = Path("static/css/main.css").read_text(encoding="utf-8")
        mobile_section = re.search(
            r"@media\s*\([^)]*max-width:\s*768px[^)]*\).*",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(mobile_section, "应找到移动端断点 @media 块")
        mobile = mobile_section.group(0)
        self.assertIn("detail-focus", mobile)

    def test_css_desktop_hides_toggle_groups_button(self):
        """桌面端全局样式应隐藏 btn-toggle-groups"""
        from pathlib import Path

        css = Path("static/css/main.css").read_text(encoding="utf-8")
        self.assertIn(".btn-toggle-groups { display: none; }", css)

    # ==================== i18n 翻译词条测试 ====================

    def test_i18n_contains_groups_toggle_translations(self):
        """i18n.js 应包含「展开分组」和「收起分组」翻译"""
        from pathlib import Path

        i18n = Path("static/js/i18n.js").read_text(encoding="utf-8")
        self.assertIn("'展开分组': 'Expand Groups'", i18n)
        self.assertIn("'收起分组': 'Collapse Groups'", i18n)

    # ==================== 交互逻辑契约测试 ====================

    def test_accounts_js_resets_detail_focus_on_switch(self):
        """accounts.js 切换账户时应重置 detail-focus 状态"""
        from pathlib import Path

        accounts_js = Path("static/js/features/accounts.js").read_text(encoding="utf-8")
        self.assertIn("setMailboxDetailFocus(false)", accounts_js)

    def test_emails_js_show_email_list_resets_focus(self):
        """emails.js showEmailList 应重置 mailbox focus"""
        from pathlib import Path

        emails_js = Path("static/js/features/emails.js").read_text(encoding="utf-8")
        show_list_section = re.search(
            r"function showEmailList\(\).*?(?=function\s)",
            emails_js,
            re.DOTALL,
        )
        self.assertIsNotNone(show_list_section)
        self.assertIn("setMailboxDetailFocus(false)", show_list_section.group(0))


class ResponsiveThreeTierContractTests(unittest.TestCase):
    """三端自适应(PC/平板/手机)下钻式导航前端契约测试"""

    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()
        cls.app = cls.module.app

    def _login(self, client):
        resp = client.post("/login", json={"password": "testpass123"})
        self.assertEqual(resp.status_code, 200)

    def _get_index_html(self) -> str:
        client = self.app.test_client()
        self._login(client)
        resp = client.get("/")
        try:
            return resp.data.decode("utf-8")
        finally:
            resp.close()

    # ==================== 断点统一契约 ====================

    def test_js_narrow_breakpoint_matches_css_tablet_breakpoint(self):
        """isNarrowWorkspaceViewport 应使用 1024px,与 CSS 平板断点一致"""
        from pathlib import Path

        emails_js = Path("static/js/features/emails.js").read_text(encoding="utf-8")
        self.assertIn("window.innerWidth <= 1024", emails_js)

    # ==================== 移动端下钻函数契约 ====================

    def test_main_js_contains_mobile_drilldown_functions(self):
        """main.js 应包含移动端下钻层级管理函数"""
        from pathlib import Path

        main_js = Path("static/js/main.js").read_text(encoding="utf-8")
        for fn in [
            "function isMobileWorkspaceViewport",
            "function setMobileMailboxLevel",
            "function mobileMailboxBack",
            "function mobileEnterAccountList",
            "function mobileEnterEmailList",
            "function handleResponsiveMailboxLevel",
        ]:
            self.assertIn(fn, main_js)

    def test_groups_js_calls_mobile_enter_account_list(self):
        """selectGroup 应触发移动端进入账号列表层"""
        from pathlib import Path

        groups_js = Path("static/js/features/groups.js").read_text(encoding="utf-8")
        self.assertIn("mobileEnterAccountList", groups_js)

    def test_accounts_js_calls_mobile_enter_email_list(self):
        """selectAccount 应触发移动端进入邮件列表层"""
        from pathlib import Path

        accounts_js = Path("static/js/features/accounts.js").read_text(encoding="utf-8")
        self.assertIn("mobileEnterEmailList", accounts_js)

    # ==================== HTML 返回按钮契约 ====================

    def test_index_html_has_mobile_back_buttons(self):
        """accounts 列与 emails 列应包含移动端返回按钮"""
        html = self._get_index_html()
        self.assertEqual(html.count("mobile-back-btn"), 2)
        self.assertIn("mobileMailboxBack()", html)

    def test_css_mobile_back_button_hidden_by_default_on_desktop(self):
        """mobile-back-btn 应全局默认隐藏,仅在移动端下钻层级显示"""
        from pathlib import Path

        css = Path("static/css/main.css").read_text(encoding="utf-8")
        self.assertIn(".mobile-back-btn { display: none; }", css)

    # ==================== CSS 下钻规则契约 ====================

    def test_css_mobile_has_drilldown_level_rules(self):
        """移动端断点应包含 mobile-level-1/2 下钻显示规则"""
        from pathlib import Path

        css = Path("static/css/main.css").read_text(encoding="utf-8")
        mobile_section = re.search(
            r"@media\s*\([^)]*max-width:\s*768px[^)]*\).*",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(mobile_section)
        mobile = mobile_section.group(0)
        self.assertIn("mobile-level-1", mobile)
        self.assertIn("mobile-level-2", mobile)
        self.assertIn("mobile-back-btn", mobile)
        self.assertIn("#page-mailbox", mobile)


if __name__ == "__main__":
    unittest.main()
