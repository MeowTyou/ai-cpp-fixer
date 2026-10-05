import io
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core.patch_engine import apply_patch_with_rollback, build_patch


class PatchEngineTests(unittest.TestCase):
    def setUp(self):
        # 每个测试使用自己的临时文件，绝不拿项目源码试验覆盖或失败。
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "sample.cpp"
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def apply(self, original, fixed, interactive=False):
        return apply_patch_with_rollback(str(self.source), fixed, original, interactive)

    def test_stale_candidate_does_not_overwrite_new_content(self):
        self.source.write_text("a();\n// 新修改\n", encoding="utf-8")
        self.assertIs(self.apply("a();\n", "b();\n"), False)
        self.assertEqual(self.source.read_text(encoding="utf-8"), "a();\n// 新修改\n")
        self.assertEqual(list(self.root.glob("*.bak.*")), [])

    def test_change_during_confirmation_is_preserved(self):
        self.source.write_text("a();\n", encoding="utf-8")

        def confirm(_prompt):
            # 模拟用户在阅读补丁期间编辑了源文件，然后同意应用旧候选。
            self.source.write_text("a();\n// 新修改\n", encoding="utf-8")
            return "y"

        with patch("builtins.input", side_effect=confirm):
            self.assertIs(self.apply("a();\n", "b();\n", interactive=True), False)
        self.assertIn("新修改", self.source.read_text(encoding="utf-8"))

    def test_no_final_newline_and_backup_retention(self):
        self.source.write_bytes(b"a();")
        self.assertIs(self.apply("a();", "b();"), True)
        self.assertEqual(self.source.read_bytes(), b"b();")
        backups = list(self.root.glob("sample.cpp.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"a();")
        self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_replace_failure_keeps_source_and_backup(self):
        self.source.write_bytes(b"a();\n")
        # 人为让最终替换失败，检查失败路径，而不是只测正常写入。
        with patch("core.patch_engine.os.replace", side_effect=OSError("模拟替换失败")):
            self.assertIs(self.apply("a();\n", "b();\n"), False)
        self.assertEqual(self.source.read_bytes(), b"a();\n")
        backups = list(self.root.glob("sample.cpp.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"a();\n")
        self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_cancel_does_not_change_file(self):
        self.source.write_bytes(b"a();\n")
        with patch("builtins.input", return_value="n"):
            self.assertEqual(self.apply("a();\n", "b();\n", interactive=True), "cancelled")
        self.assertEqual(self.source.read_bytes(), b"a();\n")
        self.assertEqual(list(self.root.glob("*.bak.*")), [])

    @unittest.skipUnless(shutil.which("patch"), "系统未安装 patch，跳过补丁实际应用测试")
    def test_generated_patch_preserves_newline_state(self):
        # 真正调用系统 patch，确认生成的补丁可用，而不只是检查标记文字。
        for before in ("a();", "a();\n"):
            for after in ("b();", "b();\n"):
                with self.subTest(before=before, after=after):
                    self.source.write_bytes(before.encode("utf-8"))
                    result = subprocess.run(
                        ["patch", "--batch", str(self.source)],
                        input=build_patch(before, after, "sample.cpp"),
                        capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(self.source.read_bytes(), after.encode("utf-8"))
