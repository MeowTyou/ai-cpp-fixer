import subprocess
import tempfile
import os

# 单个 C++ 文件若长时间无法编译完成，应返回失败而不是一直阻塞修复流程。
COMPILE_TIMEOUT_SEC = 30

def compile_and_run(source_code: str, timeout_sec: int = 2):
    # main.py 加载 .env 后，API 密钥可能出现在 os.environ 中。
    # 这里从必要变量重新构造环境，不能用 os.environ.copy() 后再删已知密钥。
    safe_env = {
        "PATH": "/usr/bin:/bin",  #供 g++ 查找它调用的系统程序
        "LANG": "C.UTF-8",       #保持编译器诊断信息的文字编码正常
    }

    with tempfile.TemporaryDirectory() as tmpdir:   #临时文件夹路径
        cpp_path = os.path.join(tmpdir, "test.cpp")
        out_path = os.path.join(tmpdir, "test.out")

        with open(cpp_path, "w") as f:
            f.write(source_code)    #写入源代码

        # 编译阶段加入环境限制和超时处理
        try:
            comp = subprocess.run(
                ["g++", "-std=c++17", "-fsanitize=address", "-g", "-Wall", cpp_path, "-o", out_path],
                #创建g++子进程，将输出赋给comp
                #comp.returncode    子进程退出码 0编译成功 非0编译失败
                #comp.stdout    标准输出 正常编译时通常为空
                #comp.stderr    标准错误 含警告和错误诊断信息
                capture_output=True,    #拦截，防止直接输出
                text=True,              #解码为普通字符串
                env=safe_env,           #不继承 Python 进程中的 API 密钥
                timeout=COMPILE_TIMEOUT_SEC,  #编译最多等待 30 秒
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "log": f"编译超时：超过 {COMPILE_TIMEOUT_SEC} 秒",
                # 编译未完成，程序尚未运行，没有程序的实际输出。
                "stdout": "",
                "stderr": "",
            }

        if comp.returncode != 0:
            # 所有分支都返回输出字段；编译失败时 stdout 为空，stderr 保留诊断。
            return {"ok": False, "log": comp.stderr, "stdout": "", "stderr": comp.stderr}

        if "-Warray-bounds" in comp.stderr or "array subscript" in comp.stderr:     #如果检测到编译器警告和错误
            return {
                "ok": False,
                "log": comp.stderr,
                "warning_type": "compiler_warning",
                "stdout": "",
                "stderr": comp.stderr,
            }

        try:
            run = subprocess.run(
                [out_path],
                capture_output=True,
                text=True,
                # 运行程序时也使用最小环境
                env=safe_env,  #程序不能通过继承的环境变量读取 API 密钥
                timeout=timeout_sec,
            )

            # ok 只表示本次编译、运行通过，不代表功能正确。
            # 返回真实输出，供 fixer 比较修改前后的行为，并传给现有 AI 请求。
            return {
                "ok": run.returncode == 0,
                "log": run.stderr if run.returncode != 0 else "",
                "stdout": run.stdout,
                "stderr": run.stderr,
            }

        except subprocess.TimeoutExpired as e:
            # 超时时可能已经产生部分输出，保留它，但不能把它当成完整运行结果。
            # TimeoutExpired 中的输出可能是 bytes，即使 subprocess 使用了 text=True。
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return {
                "ok": False,
                "log": f"Timeout: 程序运行超过{timeout_sec}秒",
                "stdout": stdout,
                "stderr": stderr,
            }
