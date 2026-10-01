#   局部编辑
#   接收 AI 返回的 changes 列表，在原文件的基础上执行内容匹配和行号消歧的局部替换。
#   校验或匹配失败时返回 None，由上层决定终止或降级到 write 模式。
#
#   1. 内容匹配：定位的主依据是 original 的整行内容，唯一匹配时允许行号有偏差。
#       同一内容出现多次时，line 必须准确指向其中一个匹配行，不再选择最近的一行。
#   2. 空白容忍：比较时使用 strip()，容忍空格/Tab/缩进差异，不进行片段匹配。
#   3. 先校验后替换：所有修改都在本轮原始代码上定位，全部通过后才生成新代码。


def apply_changes(original_code: str, changes: list):
    """
    执行局部替换。
    参数：
        - original_code : 本轮原始代码字符串，不包含展示用行号
        - changes       : AI 返回的修改列表，每项包含 original/replacement，可包含 line
    返回：
        - 修改后的代码字符串（成功；空列表时返回原代码）
        - None（任何一处校验失败、匹配失败或定位存在歧义）
    """

    # JSON 解析成功不代表字段类型正确，先检查参数，避免后续字符串操作抛出异常。
    if not isinstance(original_code, str) or not isinstance(changes, list):
        return None

    # 空列表表示 AI 没有提出修改，不把它当成匹配失败。
    if not changes:
        return original_code

    # 将原始代码按行拆分为列表，保留换行符，方便替换后重新拼接。
    lines = original_code.splitlines(keepends=True)
    resolved_changes = []
    used_targets = set()

    # 先校验并定位整批修改，不改变调用方传入的 changes，也不提前替换任何行。
    for change in changes:
        if not isinstance(change, dict):
            return None
        if "original" not in change or "replacement" not in change:
            return None

        original = change["original"]
        replacement = change["replacement"]
        if not isinstance(original, str) or not isinstance(replacement, str):
            return None

        # 空白 original 不能可靠定位；replacement 可以为空，表示将该行内容清空。
        if not original.strip():
            return None

        # 只支持单行修改，两边都必须检查。先检查再 strip，避免末尾换行被隐藏。
        # 同时拒绝 LF 和 CR，防止多行内容或额外换行被写入候选代码。
        if any(char in original or char in replacement for char in ("\n", "\r")):
            return None

        anchor_idx = None
        if "line" in change:
            line_number = change["line"]
            # bool 是 int 的子类，使用 type(...) is int 排除 true/false。
            # 不自动把字符串或小数转换为行号，避免接受格式错误的模型输出。
            if type(line_number) is not int:
                return None
            if not 1 <= line_number <= len(lines):
                return None
            # 将 AI 给出的 1-based 行号转换为 0-based 索引。
            anchor_idx = line_number - 1

        # 所有目标均从本轮原始代码中查找，避免前一条修改影响后一条的匹配。
        target_idx = find_target_line(lines, anchor_idx, original)
        if target_idx is None:
            return None

        # 检查真正匹配到的位置，而不是只比较 AI 提供的行号。
        # 两条修改若指向同一行，拒绝整批修改，避免覆盖或依赖执行顺序。
        if target_idx in used_targets:
            return None
        used_targets.add(target_idx)
        resolved_changes.append((target_idx, replacement))

    # 全部校验成功后，在副本上执行替换；每条修改保持一行，不会改变后续行号。
    fixed_lines = lines.copy()
    for target_idx, replacement in resolved_changes:
        # 进行替换，保留原行的换行符，避免拼接后格式错乱。
        original_line = lines[target_idx]
        if original_line.endswith("\r\n"):
            newline = "\r\n"
        elif original_line.endswith("\n"):
            newline = "\n"
        elif original_line.endswith("\r"):
            newline = "\r"
        else:
            newline = ""

        # replacement 已经通过单行校验，不再删除其中的字符；保留无末尾换行的状态。
        fixed_lines[target_idx] = replacement + newline

    # 重新拼接为完整字符串。
    return "".join(fixed_lines)


def find_target_line(lines: list, anchor_idx, original: str):
    """
    在全文搜索与 original 匹配的行。
    strip() 后比较，容忍首尾空白差异；多处匹配时必须由准确的行号消歧。

    参数：
        - lines      : 本轮原始代码行列表
        - anchor_idx : 锚定行的 0-based 索引，未提供行号时为 None
        - original   : 要匹配的原始单行代码

    返回：
        - 匹配到的行的 0-based 索引
        - None（全文未找到匹配，或不能明确定位）
    """
    if not isinstance(original, str):
        return None
    target = original.strip()

    # 如果 AI 返回空白 original，不能将它当成代码目标。
    if not target:
        return None

    # 全文搜索所有匹配的行，要求整行内容相等，不使用子串或相似度猜测。
    matches = [
        idx for idx, line in enumerate(lines)
        if line.strip() == target
    ]

    # 没有任何匹配，返回 None，由上层决定终止或降级。
    if not matches:
        return None

    # 唯一匹配，直接返回，不依赖 AI 行号的精确程度。
    if len(matches) == 1:
        return matches[0]

    # 多处匹配时，行号必须准确指向其中一行；缺失或不吻合就拒绝猜测。
    if anchor_idx is not None and anchor_idx in matches:
        return anchor_idx
    return None
