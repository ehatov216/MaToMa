"""
TidalController のテスト
========================
起動エラー検出のヒューリスティックが動くかを確認する。
"""

from backend.tidal_controller import TidalController


class TestBootErrorDetection:
    def test_detects_missing_module_error(self):
        assert TidalController._looks_like_boot_error(
            "Could not find module 'Sound.Tidal.Boot'"
        )

    def test_detects_not_in_scope_error(self):
        assert TidalController._looks_like_boot_error(
            "<interactive>:2:1: error: Variable not in scope: d1"
        )

    def test_ignores_normal_log_lines(self):
        assert not TidalController._looks_like_boot_error(
            "MATOMA_READY"
        )
