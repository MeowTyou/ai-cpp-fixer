import difflib
import os
import shutil
import tempfile
from colorama import Fore, Style

#1. 彩色差异对比输出（print_diff）
#2. 生成保留末尾换行符信息的补丁（build_patch）
#3. 核对原文件、备份并应用候选修改（apply_patch_with_rollback）


def build_patch(original: str, fixed: str, file_path: str = "") -> str:
    """生成补丁，并标明没有结尾换行符的源码行。"""
    #按换行符拆分为行列表，保留每行末尾的换行符
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)

    #比较original_lines和fixed_lines，生成标准diff输出
    diff = difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=file_path,
        tofile=file_path,
        n=3,  # 差异块前后显示 3 行上下文
        lineterm="\n"
    )
    # difflib 不会给无结尾换行符的内容行补换行；直接 join 会把下一行拼在一起。
    # 按 GNU patch 格式加入标记，使 --patch 生成的文件也能正确应用。
    return "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in diff
    )


def print_diff(original: str, fixed: str):
    """
    打印彩色差异对比
    红色 = 删除的行
    绿色 = 新增的行
    蓝色 = 块位置标记（显示行号范围）
    青色 = 文件头部标记
    """
    #打印分隔线
    print("\n" + "=" * 60)
    print("(红色=删除, 绿色=新增)")
    print("=" * 60)

    # 4. 逐行遍历 diff 输出，根据行首前缀添加颜色
    # 先生成完整补丁，避免无结尾换行符的行和下一行粘连。
    for line in build_patch(original, fixed).splitlines(keepends=True):
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


#安全地将 AI 修复代码应用到原文件，失败时保留可恢复的备份
# 参数：
#   - file_path     : 要修改的源文件路径
#   - fixed_code    : AI 修复后的完整代码字符串
#   - expected_code : AI 开始处理时读取的原文件内容
#   - interactive   : True 表示询问用户确认，False 表示直接应用
# 返回值：
#   - True        : 文件已更新，或内容本来一致
#   - False       : 文件未更新（出错或原文件已变化）
#   - "cancelled" : 用户取消
def apply_patch_with_rollback(
    file_path: str, fixed_code: str, expected_code: str, interactive: bool = True
):
    """先核对源文件，再通过同目录临时文件原子替换，保留独立备份。"""
    if os.path.islink(file_path):
        print("源文件是符号链接，请使用实际文件路径应用修改。")
        return False

    try:
        with open(file_path, "r") as f:
            current_code = f.read()
    except (OSError, UnicodeError) as e:
        print(f"读取源文件失败：{e}")
        return False

    # 重新读取只有在与 AI 使用的版本相同的时候才安全；不能拿旧候选覆盖用户新改的内容。
    if current_code != expected_code:
        print("原文件在 AI 处理期间已变化，拒绝应用过时的候选修改。")
        return False

    # 没有任何差异
    if current_code == fixed_code:
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

    directory = os.path.dirname(os.path.abspath(file_path))
    name = os.path.basename(file_path)
    backup_path = None
    backup_ready = False
    temporary_path = None
    try:
        # 用户看补丁并确认时可能已经编辑了文件，此时不创建无意义的备份。
        with open(file_path, "r") as f:
            if f.read() != expected_code:
                print("原文件在确认期间已变化，拒绝应用过时的候选修改。")
                return False

        #备份源文件
        # 使用唯一备份名，不覆盖用户先前留下的 .bak 文件；成功后也保留供手动恢复。
        backup_fd, backup_path = tempfile.mkstemp(prefix=name + ".bak.", dir=directory)
        os.close(backup_fd)
        shutil.copy2(file_path, backup_path)
        backup_ready = True

        # 临时文件与源文件位于同一目录，os.replace 不会留下写到一半的源文件。
        temporary_fd, temporary_path = tempfile.mkstemp(prefix=name + ".tmp.", dir=directory)
        with os.fdopen(temporary_fd, "w", newline="") as temporary_file:
            temporary_file.write(fixed_code)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        shutil.copymode(file_path, temporary_path)

        # 交互确认和准备临时文件期间，用户仍可能编辑源码；替换前再检查一次。
        with open(file_path, "r") as f:
            if f.read() != expected_code:
                print("原文件在准备写入时已变化，拒绝应用过时的候选修改。")
                return False

        os.replace(temporary_path, file_path)
        temporary_path = None
        print(f"文件已更新，原文件备份保留在 {backup_path}")
        return True
    except (OSError, UnicodeError) as e:
        # 替换前出错时源文件未改；备份仍保留，便于检查和恢复。
        print(f"应用修改失败：{e}")
        if backup_ready:
            print(f"备份保留在 {backup_path}")
        return False
    finally:
        # 清理临时文件；完整的备份不在这里删除。
        if backup_path and not backup_ready and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except OSError:
                pass
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass
