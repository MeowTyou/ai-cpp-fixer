import subprocess
import tempfile
import os

def compile_and_run(source_code: str, timeout_sec: int = 2):
    with tempfile.TemporaryDirectory() as tmpdir:   #临时文件夹路径
        cpp_path = os.path.join(tmpdir, "test.cpp")
        out_path = os.path.join(tmpdir, "test.out")

        with open(cpp_path, "w") as f:
            f.write(source_code)    #写入源代码

        comp = subprocess.run(
            ["g++", "-std=c++17", "-fsanitize=address", "-g", cpp_path, "-o", out_path],    
            #创建g++子进程，将输出赋给comp
            #comp.returncode    子进程退出码 0编译成功 非0编译失败
            #comp.stdout    标准输出 正常编译时通常为空
            #comp.stderr    标准错误 含警告和错误诊断信息
            capture_output=True,    #拦截，防止直接输出
            text=True   #解码为普通字符串
        )

        if comp.returncode != 0:
            return {"ok": False, "log": comp.stderr}

        try:
            run = subprocess.run(
                [out_path],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )

            if run.returncode != 0:
                return {"ok": False, "log": run.stderr}

            return {"ok": True, "log": ""}

        except subprocess.TimeoutExpired:
            return {"ok": False, "log": f"Timeout: 程序运行超过{timeout_sec}秒"}