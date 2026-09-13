#   局部编辑
#   接收 AI 返回的 changes 列表，在原文件的基础上执行行号锚定+模糊匹配的局部替换。
#   匹配失败时返回 None，由上层触发降级到 write 模式。
#
#   1. 行号锚定：以 AI 给出的 line 为目标，向外扩散搜索。AI给出的行号十分模糊不准确
#       定位的主依据从“行号”变成了“original 的内容”。
#       行号只在一个场景下起作用：当 original 在文件中出现多次时，用行号在多个候选中选择最近的那个。
#   2. 模糊匹配：比较时使用 strip()，容忍空格/Tab/缩进差异
#   3. 从底向顶替换：先替换行号大的，避免删除行导致后续行号错位

# prompt记得加上
"""
1、只支持单行匹配，如果 original 包含换行符，则说明ai试图同时修改多行，则直接触发降级
    for change in changes:
        if "\n" in change["original"].strip():
            return None
"""


def apply_changes(original_code: str, changes: list):
    """
    执行局部替换。
    参数：
        - original_code : 原始代码字符串
        - changes       : AI 返回的修改列表，每项包含 line/original/replacement
    返回：
        - 修改后的代码字符串（成功）
        - None（任何一处匹配失败）
    """

    # 如果 AI 返回空列表，说明它没找到需要修改的地方，视为失败
    if not changes:
        return None

    # 检查每一个 change 必须包含 original 和 replacement
    # line 字段改为可选，缺失时设为 0（消歧时退化为取第一个匹配）
    for change in changes:
        if "original" not in change or "replacement" not in change:
            return None
        if "line" not in change:
            change["line"] = 0

    # 只支持单行匹配，如果 original 包含换行符，则说明ai试图同时修改多行，则直接触发降级
    for change in changes:
        if "\n" in change["original"].strip():
            return None

    # 如果两个 change 锚定同一行，替换时会互相干扰，提前检测并返回 None，避免错误替换
    line_numbers = [c["line"] for c in changes]
    if len(line_numbers) != len(set(line_numbers)):     #去重后与原先项长度不一致
        return None

    # 按行号从大到小排序，从文件底部往顶部替换，避免删除行时导致后续行号前移
    changes.sort(key=lambda c: c["line"], reverse=True)

    # 将原始代码按行拆分为列表，保留换行符，方便替换后重新拼接
    lines = original_code.splitlines(keepends=True)

    # 逐个执行替换
    for change in changes:
        # 将ai给出的1-based行号转换为0-based，并防止减到0及以下
        anchor_idx = max(0, change["line"] - 1)

        # 在全文搜索目标行
        target_idx = find_target_line(lines, anchor_idx, change["original"])

        # 如果全文都找不到匹配，说明 AI 输出的片段与原文件不一致，直接返回 None
        if target_idx is None:
            return None

        # 进行替换，保留原行的换行符，避免拼接后格式错乱
        original_line = lines[target_idx]
        if original_line.endswith("\r\n"):
            newline = "\r\n"
        elif original_line.endswith("\n"):
            newline = "\n"
        else:
            newline = ""

        # 用 replacement 内容替换该行
        lines[target_idx] = change["replacement"].rstrip("\r\n") + newline

    # 重新拼接为完整字符串
    return "".join(lines)

def find_target_line(lines: list, anchor_idx: int, original: str):
    """
    在全文搜索与 original 匹配的行。
    strip() 后比较，容忍首尾空白差异。如果多处匹配，选离锚定行最近的那个。

    参数：
        - lines      : 代码行列表
        - anchor_idx : 锚定行的 0-based 索引
        - original   : 要匹配的原始代码片段

    返回：
        - 匹配到的行的 0-based 索引
        - None（全文未找到匹配）
    """
    target = original.strip()

    #如果ai返回 "original": ""，strip() 后是空字符串
    if not original.strip():
        return None

    # 全文搜索所有匹配的行
    matches = [
        idx for idx, line in enumerate(lines)
        if line.strip() == target
    ]

    # 没有任何匹配，返回 None 触发降级
    if not matches:
        return None

    # 唯一匹配，直接返回，行号完全不影响
    if len(matches) == 1:
        return matches[0]

    # 多处匹配，选离锚定行最近的那个
    return min(matches, key=lambda idx: abs(idx - anchor_idx))