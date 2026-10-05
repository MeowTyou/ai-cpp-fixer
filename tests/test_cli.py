import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core.fixer import fix_file


# 从测试文件位置推导项目目录，避免写死 /home/dev 或 Windows 用户名。
ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def cli(self, *args):
        # 真正启动命令行入口，检查操作系统得到的退出码。
        return subprocess.run(
            [sys.executable, str(ROOT / "main.py"), *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )

    def test_missing_file_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.cli(Path(directory) / "missing.cpp")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_directory_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.cli(directory)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_help_and_argument_error(self):
        self.assertEqual(self.cli("--help").returncode, 0)
        self.assertEqual(self.cli().returncode, 2)

    def test_main_forwards_repair_status(self):
        import main

        # 成功和失败状态均应传回 main；此处不运行真实模型。
        for status in (0, 1):
            with self.subTest(status=status):
                with patch.object(main, "fix_file", return_value=status):
                    with patch.object(sys, "argv", ["main.py", "sample.cpp", "--diff"]):
                        self.assertEqual(main.main(), status)

    def test_output_loss_is_rejected_without_applying(self):
        original = 'int main() { /* 原有求和和输出 */ return 0; }\n'
        candidate = 'int main() { return 0; }\n'
        first = {"ok": True, "log": "", "stdout": "10\n", "stderr": ""}
        empty = {"ok": True, "log": "", "stdout": "", "stderr": ""}
        raw = json.dumps({"code": candidate, "explanation": "模拟删除功能"})

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.cpp"
            source.write_text(original, encoding="utf-8")
            # 模拟模型及编译结果，确定地复现“候选正常退出但输出消失”。
            # 所有密钥都是假值；这个测试不会连接 API。
            with patch.dict(os.environ, {"API_KEY": "offline-test"}, clear=True):
                with patch("core.fixer.openai.OpenAI") as client:
                    client.return_value.chat.completions.create.return_value.choices[0].message.content = raw
                    with patch("core.fixer.compile_and_run", side_effect=[first, empty, empty, empty]):
                        with patch("core.fixer.apply_patch_with_rollback") as apply:
                            with redirect_stdout(io.StringIO()):
                                status = fix_file(str(source), apply_mode="apply", repair_mode="write")
            self.assertEqual(status, 1)  # 三轮都被拒绝，应报告失败。
            apply.assert_not_called()
            self.assertEqual(source.read_text(encoding="utf-8"), original)
