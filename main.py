import os
from dotenv import load_dotenv
load_dotenv()
import sys
from core.fixer import fix_file

if "/mnt/c/" in os.getcwd():    #此时运行速度慢且易出错
    print("错误：请将项目移至 WSL 内部路径（如 /home/用户名/），不要放在 /mnt/c/ 下。")
    sys.exit(1)

if len(sys.argv) < 2:
    print("用法: python main.py <你的cpp文件路径>")
    sys.exit(1)

fix_file(sys.argv[1])