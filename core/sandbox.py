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
            }

        if comp.returncode != 0:
            return {"ok": False, "log": comp.stderr}

        if "-Warray-bounds" in comp.stderr or "array subscript" in comp.stderr:     #如果检测到编译器警告和错误
            return {
                "ok": False,
                "log": comp.stderr,
                "warning_type": "compiler_warning"
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

            if run.returncode != 0:
                return {"ok": False, "log": run.stderr}

            return {"ok": True, "log": ""}

        except subprocess.TimeoutExpired:
            return {"ok": False, "log": f"Timeout: 程序运行超过{timeout_sec}秒"}
