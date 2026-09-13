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

    first = compile_and_run(current_code)
    if first["ok"]:
        print("ASan未检测到错误，正交由AI检查")
        current_log = "代码运行正常，但需要检查所有数组索引访问，确保没有越界风险。"
        error_history.append(f"安全审查请求:\n{current_log}")
        
    else:
        current_log = first["log"]
        error_history.append(f"首次运行报错:\n{current_log}")

    for attempt in range(1, 4):
        print(f"\n第 {attempt} 次尝试修复...")

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
            你是一个 C++ 调试专家。以下是一段有运行时错误的 C++ 代码及报错日志。

            【报错日志】
            {"".join(error_history)}

            【当前源码】
            {current_code}

            请修复代码中的错误，并按以下 JSON 格式输出：
            {{
                "explanation": "简要说明你诊断出的根本原因（1-2句话）",
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
            3. original 字段必须从源码中精确复制那一行的内容（不含行号和行首缩进也可以，但内容必须准确）。
            4. 只支持单行修改。original 和 replacement 都不能包含换行符。
            5. 不要使用 Markdown 代码块包裹 JSON。
            6. 只修改有问题的代码行，不要改动其他任何行。原始代码中的注释、空行、缩进必须原样保留。
            7. 对于任何数组访问（无论是 C 风格栈数组还是 std::vector），请检查所有索引访问是否越界：
                - 如果索引是常量（如 a[100]），直接修正为合法值（如 a[0]）。
                - 如果索引是变量（如 a[i]），请检查是否有边界校验（如 if (i < 5)），若没有则添加。
                - 如果数组大小由变量决定（如 int arr[n]），请改用 std::vector<int> arr(n)。
            8. 请保留 C 风格栈数组（如 int a[5]），除非数组大小是变量，才需要改为 std::vector。
            """
        else:
            # write 模式：要求 AI 返回完整代码
            prompt = f"""
            你是一个 C++ 调试专家。以下是一段有运行时错误的 C++ 代码及报错日志。

            【报错日志】
            {"".join(error_history)}

            【当前源码】
            {current_code}

            请修复代码中的错误，并按以下 JSON 格式输出：
            {{
                "explanation": "简要说明你诊断出的根本原因（1-2句话）",
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

            else:
                # write 模式：解析完整代码
                explanation, fixed_code = extract_code_from_response(raw_content)

                if explanation:
                    error_history.append(f"AI诊断：{explanation}")

                if not fixed_code:
                    raise ValueError("write 模式提取后的代码为空")

            
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
                print(f"修复成功，已保存至 {fixed_path}")
                return

        current_log = result["log"]
        error_history.append(f"第{attempt}次修复后仍报错:\n{current_log}")
        current_code = fixed_code

    print("3次尝试失败，请手动检查。最后一次报错：")
    print(current_log)