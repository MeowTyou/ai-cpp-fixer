import os
import subprocess
import unittest
from unittest.mock import patch

from core.sandbox import COMPILE_TIMEOUT_SEC, compile_and_run


def completed(code=0, stdout="", stderr=""):
    # 构造子进程结果，模拟编译器或待修复程序，不实际运行任意 C++。
    return subprocess.CompletedProcess([], code, stdout, stderr)


class SandboxTests(unittest.TestCase):
    def test_output_and_environment(self):
        with patch.dict(os.environ, {"API_KEY": "fake-secret", "CUSTOM_SECRET": "fake-secret"}):
            with patch("core.sandbox.subprocess.run", side_effect=[completed(), completed(stdout="10\n")]) as run:
                result = compile_and_run("int main(){}", timeout_sec=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "10\n")
        # 编译和运行均显式传入环境，未知名称的密钥同样不能被继承。
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"], {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        self.assertEqual(run.call_args_list[0].kwargs["timeout"], COMPILE_TIMEOUT_SEC)
        self.assertEqual(run.call_args_list[1].kwargs["timeout"], 3)

    def test_compile_failure_does_not_run_program(self):
        with patch("core.sandbox.subprocess.run", return_value=completed(1, stderr="编译失败")) as run:
            result = compile_and_run("broken")
        self.assertFalse(result["ok"])
        self.assertEqual(result["stderr"], "编译失败")
        self.assertEqual(run.call_count, 1)

    def test_compile_timeout(self):
        with patch("core.sandbox.subprocess.run", side_effect=subprocess.TimeoutExpired("g++", 30)):
            result = compile_and_run("int main(){}")
        self.assertFalse(result["ok"])
        self.assertIn("编译超时", result["log"])

    def test_runtime_failure(self):
        results = [completed(), completed(1, stdout="部分输出", stderr="运行错误")]
        with patch("core.sandbox.subprocess.run", side_effect=results):
            result = compile_and_run("int main(){}")
        self.assertFalse(result["ok"])
        self.assertEqual(result["log"], "运行错误")
        self.assertEqual(result["stdout"], "部分输出")

    def test_runtime_timeout_preserves_partial_output(self):
        # 即使 text=True，TimeoutExpired 的部分输出仍可能是 bytes。
        timeout = subprocess.TimeoutExpired("program", 2, output=b"partial\n", stderr=b"error\n")
        with patch("core.sandbox.subprocess.run", side_effect=[completed(), timeout]):
            result = compile_and_run("int main(){}")
        self.assertFalse(result["ok"])
        self.assertEqual(result["stdout"], "partial\n")
        self.assertEqual(result["stderr"], "error\n")
