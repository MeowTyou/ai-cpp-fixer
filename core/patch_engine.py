import difflib
import shutil
import subprocess
import os
from colorama import Fore, Style

#1. 彩色差异对比输出（print_diff）
#2. 安全补丁应用与自动回滚（apply_patch_with_rollback）

def print_diff(original: str, fixed: str):
    """
    打印彩色差异对比
    红色 = 删除的行
    绿色 = 新增的行
    蓝色 = 块位置标记（显示行号范围）
    青色 = 文件头部标记
    """
    #按换行符拆分为行列表，保留每行末尾的换行符
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)

    #比较original_lines和fixed_lines，生成标准diff输出
    diff = difflib.unified_diff(
        original_lines, fixed_lines,
        n=3     # 差异块前后显示 3 行上下文
    )

    #打印分隔线
    print("\n" + "=" * 60)
    print("(红色=删除, 绿色=新增)")
    print("=" * 60)

    # 4. 逐行遍历 diff 输出，根据行首前缀添加颜色
    for line in diff:
        if line.startswith('---') or line.startswith('+++'):
            # 文件头部：青色
            print(Fore.CYAN + line + Style.RESET_ALL, end='')
        elif line.startswith('@@'):
            # 块位置标记：蓝色
            print(Fore.BLUE + line + Style.RESET_ALL, end='')
        elif line.startswith('-'):
            # 删除的行：红色
            print(Fore.RED + line + Style.RESET_ALL, end='')
        elif line.startswith('+'):
            # 新增的行：绿色
            print(Fore.GREEN + line + Style.RESET_ALL, end='')
        else:
            # 未修改的上下文行：保持默认颜色
            print(line, end='')

    # 重置颜色并打印结束分隔线
    print(Style.RESET_ALL)
    print("=" * 60 + "\n")


#安全地将 AI 修复代码应用到原文件，失败时自动回滚
# 参数：
#   - file_path    : 要修改的源文件路径
#   - fixed_code   : AI 修复后的完整代码字符串
#   - interactive  : True 表示询问用户确认，False 表示直接应用
# 返回值：
#   - True  : 补丁成功应用，文件已更新
#   - False : 补丁未应用（用户取消、出错、或回滚成功）

def apply_patch_with_rollback(file_path: str, fixed_code: str, interactive: bool = True) -> bool:
    """
    交互式补丁应用引擎
    1. 重新读取当前文件内容（防止过时补丁）
    2. 生成 diff 补丁
    3. 交互确认
    4. 备份原文件为.bak
    5. 应用补丁
    6. 失败则自动恢复.bak
    7. 清理临时文件.patch和.bak
    """

    # 防止用户在 AI 修复期间手动修改了文件，导致补丁基于过时内容，先重新读取当前文件内容
    try:
        with open(file_path, "r") as f:
            current_code = f.read()
    except FileNotFoundError:
        print(f"文件 {file_path} 不存在，补丁无法应用")
        return False

        # 确保两个字符串末尾都有换行符
    if current_code and not current_code.endswith("\n"):
        current_code += "\n"
    if fixed_code and not fixed_code.endswith("\n"):
        fixed_code += "\n"

    # 比较current_code和fixed_code，生成描述两者差异的unified diff补丁
    diff = difflib.unified_diff(
        current_code.splitlines(keepends=True),
        fixed_code.splitlines(keepends=True),
        fromfile=file_path,
        tofile=file_path
    )
    patch_content = ''.join(diff)

    # 没有任何差异
    if not patch_content:
        print("ℹ文件内容与修复版本一致，无需应用补丁")
        return True

    # 交互确认，如果 interactive=True，打印补丁内容并等待用户输入 y/n
    if interactive:
        print("\n" + "=" * 60)
        print("补丁内容预览：")
        print_diff(current_code, fixed_code)
        confirm = input("是否应用此补丁？(y/n): ").strip().lower()
        if confirm != 'y':
            print("操作已取消，补丁未应用。")
            return "cancelled"
    else:
        # 非交互模式：直接应用
        print("非交互模式：自动应用补丁...")


    backup_path = file_path + ".bak"
    patch_path = file_path + ".patch"
    
    #备份源文件
    try:
        shutil.copy2(file_path, backup_path)
        print(f"已备份原文件至 {backup_path}")
    except Exception as e:
        print(f"备份失败：{str(e)}")
        return False

    #写入补丁文件
    try:
        with open(patch_path, "w") as f:
            f.write(patch_content)
    except Exception as e:
        print(f"写入补丁文件失败：{str(e)}")
        # 写入失败时恢复备份文件
        shutil.copy2(backup_path, file_path)
        return False

    #应用补丁
    try:
        result = subprocess.run(
            ["patch", "-p0", "-i", patch_path, file_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            # 根据 patch 命令的错误信息，分类处理
            stderr = result.stderr
            if "No file to patch" in stderr or "file not found" in stderr:
                raise RuntimeError("补丁与当前文件不匹配，文件可能已被修改")
            elif "Permission denied" in stderr:
                raise RuntimeError("权限不足，无法修改文件")
            else:
                raise RuntimeError(f"patch 命令执行失败：{stderr}")

        print("补丁应用成功。")
        return True

    except subprocess.TimeoutExpired:
        # 补丁超时
        print("补丁应用超时")
        shutil.copy2(backup_path, file_path)
        return False

    except Exception as e:
        # 其他任何异常
        print(f"补丁应用出错：{str(e)}")
        shutil.copy2(backup_path, file_path)
        return False

    finally:
        # 清理临时文件
        # 无论成功还是失败，都尝试删除 .patch 和 .bak 临时文件
        for path in [patch_path, backup_path, file_path + ".orig"]:     #.orig 备份文件,一起删除
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        print("已清理临时文件。")