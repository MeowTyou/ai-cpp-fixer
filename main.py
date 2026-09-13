import os
import sys
import argparse
from dotenv import load_dotenv
from core.fixer import fix_file

load_dotenv() 

if "/mnt/c/" in os.getcwd():
    print("错误：请将项目移至 WSL 内部路径（如 /home/用户名/），不要放在 /mnt/c/ 下。")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="AI驱动的C++运行时错误自动修复工具",        #在终端输入 python main.py --help 时，显示在信息顶部
        epilog="示例: python main.py test.cpp --apply"        #显示在信息底部
    )
    #带--是选项参数，不带的是位置参数，如--apply与file
    parser.add_argument("file", help="要修复的C++源文件路径")       #将第一个不带--的参数存入args.file
    #help只负责当用户输入 --help 时，把help后的说明打印在屏幕上
    
    #读取选项
    mode_group = parser.add_mutually_exclusive_group()      #以下选项只能确认一个，减少歧义
    #如提供字符串"--apply"会自动对应操作args.apply
    #action="store_true"将对应的args.XXX值设置为true
    mode_group.add_argument("--apply", action="store_true", help="交互式应用补丁（需手动确认）")
    mode_group.add_argument("--yes", "-y", action="store_true", help="非交互式直接应用补丁（无需手动确认）")
    mode_group.add_argument("--patch", action="store_true", help="仅生成 .patch 补丁文件")
    mode_group.add_argument("--diff", action="store_true", help="仅显示差异")
    # 修复模式，与apply_mode可以组合使用
    # 例如：python main.py test.cpp --apply --write
    repair_group = parser.add_mutually_exclusive_group()
    repair_group.add_argument("--edit", action="store_true", help="仅使用局部替换模式")
    repair_group.add_argument("--write", action="store_true", help="强制使用整体覆盖模式")
    
    args = parser.parse_args()
    
    # 将命令行参数映射为 apply_mode 变量
    if args.yes:
        apply_mode = "apply"    #直接运用
    elif args.apply:
        apply_mode = "prompt"   #手动确认后运用
    elif args.patch:
        apply_mode = "patch"    #生成补丁
    elif args.diff:
        apply_mode = "diff"     #颜色差异
    else:
        apply_mode = None       #默认模式（生成 _fixed.cpp）

    if args.write:
        repair_mode = "write"   #强制 write，跳过 edit
    elif args.edit:
        repair_mode = "edit"    #仅 edit
    else:
        repair_mode = "auto"    #默认：edit优先，失败则使用write
    
    # 调用修复引擎，传入模式参数
    fix_file(args.file, apply_mode=apply_mode, repair_mode=repair_mode)

if __name__ == "__main__":
    main()