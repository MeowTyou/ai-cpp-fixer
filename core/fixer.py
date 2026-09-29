import openai
from openai import APIError, APIConnectionError, RateLimitError, AuthenticationError
import os
import re
import json
from core.sandbox import compile_and_run
import colorama
from colorama import Fore, Style
import difflib
from core.patch_engine import print_diff, apply_patch_with_rollback
from core.editor import apply_changes

# 初始化 colorama，确保跨平台颜色输出
colorama.init()

#防止ai在回复里偏离预定格式
def extract_code_from_response(raw: str):
    """
    write模式

    从 AI 返回的原始文本中提取 explanation 和 code。
    返回: (explanation_str, code_str)
    """
    # 第一层：假设ai回答严格按照格式，尝试用json.loads解析
    try:
        data = json.loads(raw)      #把一个符合JSON语法的字符串，转换成Python的数据结构
        return data.get("explanation", ""), data.get("code", "")
        #分别取explanation与code，取不到则设置为空

    except json.JSONDecodeError:        #解析失败则开始降级
        pass

    # 第二层：Markdown 代码块提取安全边界
    match = re.search(r"```(?:cpp|c\+\+|c)?\s*\n?(.*?)```", raw, re.DOTALL)
    if match:
        return "", match.group(1).strip()

    # 第三层：放弃解析，原样返回，让编译器编译后将报错信息返回给ai
    return "", raw.strip()

def extract_changes(raw: str):
    """
    edit模式

    从 AI 返回的原始文本中提取 explanation 和 changes 数组。
    返回: (explanation_str, changes_list 或 None)
    """
    # 第一层：标准 JSON 解析
    try:
        data = json.loads(raw)
        explanation = data.get("explanation", "")
        changes = data.get("changes", None)
        return explanation, changes

    except json.JSONDecodeError:
        pass

    # 第二层：Markdown 代码块提取
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            explanation = data.get("explanation", "")
            changes = data.get("changes", None)
            return explanation, changes
        except json.JSONDecodeError:
            pass

    # 第三层：解析失败，返回 None
    return "", None


def extract_logic_report(raw: str):
    """
    从 AI 原本就会返回的 JSON 中读取逻辑分析，不额外调用一次 AI。
    返回字典中的文字只代表 AI 的推测，不能当作编译器或运行结果。
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 与原项目的解析方式一致：允许 AI 偶尔把 JSON 包在 Markdown 代码块里。
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    # JSON 也可能是数组等类型；只有对象才有下面的分析字段。
    if not isinstance(data, dict):
        data = {}

    report = {}
    for field in ("original_logic", "explanation", "change_effect", "remaining_risks"):
        value = data.get(field)
        # 缺失时显示“未提供”，避免程序替 AI 编造分析结论。
        report[field] = value.strip() if isinstance(value, str) and value.strip() else "未提供"
    return report


def print_logic_report(report: dict, validation: dict):
    """将 AI 的推测与本地编译、运行的真实结果分开打印。"""
    print("\n========== 修复分析 ==========")
    print(f"推测原代码逻辑：{report['original_logic']}")
    print(f"判断的问题：{report['explanation']}")
    print(f"修改后的效果：{report['change_effect']}")
    print(f"剩余风险：{report['remaining_risks']}")

    if validation["ok"]:
        # 这里只能证明当前编译和运行没有报错，不能证明所有输入的输出都正确。
        print("实际检查：编译通过，本次运行未发现错误。")
    else:
        # 失败原因来自本地工具，不用 AI 的判断覆盖真实错误日志。
        print(f"实际检查：未通过。\n{validation['log']}")

    print("==============================\n")


def fix_file(file_path: str, apply_mode: str = None, repair_mode: str = "auto"):

    if not os.path.exists(file_path):
        print(f"错误：文件 '{file_path}' 不存在。")
        return
    if not os.path.isfile(file_path):
        print(f"错误：'{file_path}' 不是一个文件。")
        return

    with open(file_path, "r") as f:
        original = f.read()

    # 从环境变量读取配置，若未设置则使用默认值
    api_key = os.getenv("API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("API_BASE_URL", "https://api.deepseek.com/v1")
    model_name = os.getenv("MODEL_NAME", "deepseek-coder")

    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    error_history = []
    current_code = original
    current_log = ""
    current_mode = "edit"   #初始模式默认为edit

    # 在此进行修改：区分首次运行结果与 AI 审查请求
    first = compile_and_run(current_code)
    # 保存最近一次真实检查结果，供 AI 未提出修改时展示；不把 AI 意见写进真实日志。
    last_result = first
    if first["ok"]:
        print("本次编译和运行通过，正在请 AI 检查可能的逻辑问题。")
        # 原项目在没有检测到错误时也会调用 AI；这里明确告诉 AI 可以不修改。
        error_history.append(
            "首次编译和运行通过。请根据源码推测功能、审查可能的问题；"
            "如果没有足够证据确认问题，可以不修改代码。"
        )
    else:
        current_log = first["log"]
        error_history.append(f"首次运行报错:\n{current_log}")

    for attempt in range(1, 4):
        print(f"\n第 {attempt} 次尝试修复...")

        # 把历次真实错误和 AI 诊断分段传给模型
        history_text = "\n\n".join(error_history)

        # 重试时当前源码可能已经是上次的候选代码，需要同时保留最初的源码供 AI 判断原意。
        original_context = f"【原始源码】\n{original}\n\n" if current_code != original else ""

        # 根据 current_mode 构建对应的 Prompt
        # edit 模式：要求 AI 返回 changes 数组（只返回被修改的行）
        # write 模式：要求 AI 返回完整代码（用于降级或强制 write）
        
        if attempt == 1:
            if repair_mode == "write":
                current_mode = "write"
            else:
                current_mode = "edit"

        if current_mode == "edit":
            prompt = f"""
            你是一个 C++ 调试专家。请根据源码和真实日志，先推测原意、定位问题，
            再提出最小修改，并在同一次回复中检查修改是否符合你推测的原意。

            【编译、运行及修复记录】
            {history_text}

            {original_context}【当前源码】
            {current_code}

            请按需修复确有依据的问题，并按以下 JSON 格式输出：
            {{
                "original_logic": "根据源码推测作者想实现的功能；不确定时明确说明",
                "explanation": "诊断出的错误原因，或审查时发现的具体疑点",
                "change_effect": "说明这次修改对程序行为的影响",
                "remaining_risks": "说明哪些逻辑无法仅凭源码和本次运行确认",
                "changes": [
                    {{
                        "line": 目标行号（从 1 开始计数）,
                        "original": "需要被替换的原始代码片段",
                        "replacement": "替换后的新代码片段"
                    }}
                ]
            }}

            重要规则（必须严格遵守）：
            1. 只输出 JSON，不要包含其他任何文字。
            2. changes 数组中每一项代表一处修改。
               如果没有足够依据确认存在问题，返回空数组，不要为了修改而修改。
            3. original 字段必须从源码中精确复制那一行的内容（不含行号和行首缩进也可以，但内容必须准确）。
            4. 只支持单行修改。original 和 replacement 都不能包含换行符。
            5. 不要使用 Markdown 代码块包裹 JSON。
            6. 只修改有问题的代码行，不要改动其他任何行。原始代码中的注释、空行、缩进必须原样保留。
            7. 对于任何数组访问（无论是 C 风格栈数组还是 std::vector），请检查所有索引访问是否越界：
                - 如果索引是常量（如 a[100]），直接修正为合法值（如 a[0]）。
                - 如果索引是变量（如 a[i]），请检查是否有边界校验（如 if (i < 5)），若没有则添加。
                - 如果数组大小由变量决定（如 int arr[n]），请改用 std::vector<int> arr(n)。
            8. 请保留 C 风格栈数组（如 int a[5]），除非数组大小是变量，才需要改为 std::vector。
            9. original_logic 是推测，不要写成已证实的需求；remaining_risks 必须如实说明未验证之处。
            10. 输出前自行核对 changes 与你推测的原意是否一致；不要声称已经运行过修改后的代码。
            """
        else:
            # write 模式：要求 AI 返回完整代码
            prompt = f"""
            你是一个 C++ 调试专家。请根据源码和真实日志，先推测原意、定位问题，
            再提出最小修改，并在同一次回复中检查修改是否符合你推测的原意。

            【编译、运行及修复记录】
            {history_text}

            {original_context}【当前源码】
            {current_code}

            请按需修复确有依据的问题，并按以下 JSON 格式输出：
            {{
                "original_logic": "根据源码推测作者想实现的功能；不确定时明确说明",
                "explanation": "诊断出的错误原因，或审查时发现的具体疑点",
                "change_effect": "说明这次修改对程序行为的影响",
                "remaining_risks": "说明哪些逻辑无法仅凭源码和本次运行确认",
                "code": "修复后的完整 C++ 代码（不包含任何额外解释）"
            }}

            重要规则（必须严格遵守）：
            1. 只输出 JSON，不要包含其他任何文字。
            2. code 字段的值必须是完整的、可编译的 C++ 源代码。
            3. 如果代码中包含双引号或反斜杠，请正确转义（例如 \\" 和 \\\\）。
            4. 不要使用 Markdown 代码块包裹 JSON。
            5. 【注释保留规则】请完整保留原始代码中的所有注释、空行和缩进。只修改有问题的代码行，不要改动其他任何行。
            6. 对于任何数组访问（无论是 C 风格栈数组还是 std::vector），请检查所有索引访问是否越界：
                - 如果索引是常量（如 a[100]），直接修正为合法值（如 a[0]）。
                - 如果索引是变量（如 a[i]），请检查是否有边界校验（如 if (i < 5)），若没有则添加。
                - 如果数组大小由变量决定（如 int arr[n]），请改用 std::vector<int> arr(n)。
            7. 请保留 C 风格栈数组（如 int a[5]），除非数组大小是变量，才需要改为 std::vector。
            8. 如果没有足够依据确认存在问题，code 返回与当前源码完全相同的内容，不要为了修改而修改。
            9. original_logic 是推测，不要写成已证实的需求；remaining_risks 必须如实说明未验证之处。
            10. 输出前自行核对 code 与你推测的原意是否一致；不要声称已经运行过修改后的代码。
            """
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "你是C++调试专家，严格按照JSON格式输出。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2048,
                timeout=15.0   #超时后触发APIConnectionError
            )

            #从这里开始进行异常处理
            
            # 检查resp.choices列表与其第一项是否不存在或为空来检查返回内容是否为空
            if not resp.choices or not resp.choices[0].message.content:
                raise ValueError("AI 返回内容为空或格式异常")

            raw_content = resp.choices[0].message.content

            # 修复代码和分析文字来自同一次请求，不会额外消耗一次 AI 调用。
            report = extract_logic_report(raw_content)


            if current_mode == "edit":
                # edit 模式：解析 changes 数组，应用到 current_code
                explanation, changes = extract_changes(raw_content)

                if explanation:
                    error_history.append(f"AI诊断：{explanation}")

                if changes is None:
                    if repair_mode == "edit":
                        print("edit 模式解析失败。")
                        return
                    print("edit 模式解析失败，使用 write 模式...")
                    error_history.append("edit 模式解析失败，现在请改用完整代码模式输出。")
                    current_mode = "write"
                    continue

                # 允许 AI 审查后明确表示无需修改，返回空changes
                # 原版 editor.py 把空 changes 当成匹配失败；此处先拦截，避免误降级。
                if changes == []:
                    print_logic_report(report, last_result)
                    if last_result["ok"]:
                        print("AI 未提出有明确依据的修改，原文件保持不变。")
                    else:
                        print("AI 未提出修复，但实际错误仍存在；本次未生成修复文件。")
                    return

                # 应用 changes 到当前代码，得到修复后的完整代码
                fixed_code = apply_changes(current_code, changes)

                # 匹配失败时（暂未实现降级，先触发异常）
                if fixed_code is None:
                    if repair_mode == "edit":
                        print("edit 模式匹配失败。")
                        return
                    print("edit 模式匹配失败，使用 write 模式...")
                    error_history.append("edit 模式匹配失败，现在请改用完整代码模式输出。")
                    current_mode = "write"
                    continue

                # AI 给出修改项但内容没有变化时，不把它当成一次成功修复。
                if fixed_code == current_code:
                    print_logic_report(report, last_result)
                    if last_result["ok"]:
                        print("AI 未提出有明确依据的修改，原文件保持不变。")
                    else:
                        print("AI 未提出修复，但实际错误仍存在；本次未生成修复文件。")
                    return

            else:
                # write 模式：解析完整代码
                explanation, fixed_code = extract_code_from_response(raw_content)

                if explanation:
                    error_history.append(f"AI诊断：{explanation}")

                if not fixed_code:
                    raise ValueError("write 模式提取后的代码为空")

                if fixed_code == current_code:
                    print_logic_report(report, last_result)
                    if last_result["ok"]:
                        print("AI 未提出有明确依据的修改，原文件保持不变。")
                    else:
                        print("AI 未提出修复，但实际错误仍存在；本次未生成修复文件。")
                    return

            
        except openai.APIConnectionError as e:
            current_log = f"网络连接错误（请检查网络）：{str(e)}"
            error_history.append(f"第{attempt}次修复连接失败:\n{current_log}")
            if attempt == 3:
                print(f"网络连接连续失败，请检查网络后重试。")
                return
            continue  # 网络问题可能恢复，继续重试
            
        except openai.RateLimitError as e:
            current_log = f"API 请求频率超限 ：{str(e)}"
            error_history.append(f"第{attempt}次修复限流:\n{current_log}")
            print(f"DeepSeek API 限流，请稍后重试。")
            return  # 限流重试无效，直接退出
            
        except openai.AuthenticationError as e:
            current_log = f"API Key 认证失败（请检查 .env）：{str(e)}"
            error_history.append(f"第{attempt}次修复认证失败:\n{current_log}")
            print(f"API Key 无效，请检查 .env 配置。")
            return  # 认证错误必须手动修复，直接退出
            
        except openai.APIError as e:
            current_log = f"API 服务器内部错误：{str(e)}"
            error_history.append(f"第{attempt}次修复服务器错误:\n{current_log}")
            if attempt == 3:
                print(f"API 服务器连续报错，请稍后重试。")
                return
            continue  # 服务器可能临时故障，尝试重试
            
        except Exception as e:
            current_log = f"未知异常：{str(e)}"
            error_history.append(f"第{attempt}次修复未知错误:\n{current_log}")
            if attempt == 3:
                print(f"调试信息：未知异常详情 -> {str(e)}")
                print(f"发生未知错误，自动修复终止。")
                return
            continue


        result = compile_and_run(fixed_code)
        print_logic_report(report, result)
        # 重试时，如果 AI 不再提出修改，应显示最近一次候选代码的实际结果。
        last_result = result
        if result["ok"]:
            # 根据 apply_mode 决定行为
            if apply_mode == "diff":
                print_diff(original, fixed_code)
                return

            elif apply_mode == "patch":
                # 生成补丁文件
                # 该函数比较两个文本序列（行列表），生成标准 diff 格式的输出
                diff = difflib.unified_diff(
                    original.splitlines(keepends=True),
                    fixed_code.splitlines(keepends=True),
                    #.splitlines(keepends=True) 按换行符拆分成列表，并保留每行的换行符（\n）
                    fromfile=file_path,
                    tofile=file_path
                    # 两者路径相同，表示这是一个就地修改的补丁
                )
                patch_content = ''.join(diff)
                #将diff中内容按照''分割储存
                patch_path = file_path + ".patch"
                with open(patch_path, "w") as f:
                    f.write(patch_content)
                print(f"补丁已保存至 {patch_path}")
                print(f"手动应用命令: patch -p0 < {patch_path}")
                return

            elif apply_mode in ("apply", "prompt"):
                #--apply   → apply_mode == "prompt"  → interactive = True  → 需要询问用户
                #--yes     → apply_mode == "apply"   → interactive = False → 直接执行
                interactive = (apply_mode == "prompt")
                success = apply_patch_with_rollback(file_path, fixed_code, interactive=interactive)
                if success == True:
                    print("文件已更新。")
                elif success == "cancelled":
                    print("原文件未修改。")
                else:
                    print("补丁应用失败。")
                return

            else:
                # 默认模式：生成 _fixed.cpp
                print_diff(original, fixed_code)
                base_name = os.path.basename(file_path)
                name_without_ext = base_name.replace(".cpp", "")
                output_dir = os.path.join(os.getcwd(), "fixed_output")
                os.makedirs(output_dir, exist_ok=True)
                fixed_path = os.path.join(output_dir, f"{name_without_ext}_fixed.cpp")
                with open(fixed_path, "w") as f:
                    f.write(fixed_code)
                # 编译和本次运行通过后保存候选文件，逻辑仍需参考上方 AI 分析。
                print(f"候选修复已保存至 {fixed_path}")
                return

        current_log = result["log"]
        error_history.append(f"第{attempt}次修复后仍报错:\n{current_log}")
        current_code = fixed_code

    print("3次尝试失败，请手动检查。最后一次报错：")
    print(current_log)
