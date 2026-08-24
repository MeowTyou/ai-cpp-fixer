import openai
from openai import APIError, APIConnectionError, RateLimitError, AuthenticationError
import os
import re
import json
from core.sandbox import compile_and_run
import colorama
from colorama import Fore, Style
import difflib


# 初始化 colorama，确保跨平台颜色输出
colorama.init()

#防止ai在回复里偏离预定格式
def extract_code_from_response(raw: str):
    """
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

def fix_file(file_path: str):
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

    first = compile_and_run(current_code)
    if first["ok"]:
        print("程序运行正常，无需修复")
        return
    current_log = first["log"]
    error_history.append(f"首次运行报错:\n{current_log}")

    for attempt in range(1, 4):
        print(f"\n第 {attempt} 次尝试修复...")

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

        重要规则：
        1. 只输出 JSON，不要包含其他任何文字。
        2. code 字段的值必须是完整的、可编译的 C++ 源代码。
        3. 如果代码中包含双引号或反斜杠，请正确转义（例如 \\\" 和 \\\\）。
        4. 不要使用 Markdown 代码块包裹 JSON。
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
            
            #检查resp.choices列表与其第一项是否不存在或为空来检查返回内容是否为空
            if not resp.choices or not resp.choices[0].message.content:
                raise ValueError("AI 返回内容为空或格式异常")

            raw_content = resp.choices[0].message.content
            explanation, fixed_code = extract_code_from_response(raw_content)

            # 如果有解释，记录到历史（便于后续反思）
            if explanation:
                error_history.append(f"AI诊断：{explanation}")

            if not fixed_code:
                raise ValueError("提取后的代码为空")

            
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
            #彩色输出

            print("\n" + "=" * 60)
            print("(红色=删除, 绿色=新增)")
            print("=" * 60)

            original_lines = original.splitlines(keepends=True)
            fixed_lines = fixed_code.splitlines(keepends=True)

            diff = difflib.unified_diff(
                original_lines, fixed_lines,
                fromfile='原始代码',
                tofile='修复代码',
                n=3
            )
            #修改前后逐行对比

            for line in diff:
                if line.startswith('---') or line.startswith('+++'):
                    print(Fore.CYAN + line + Style.RESET_ALL, end='')
                elif line.startswith('@@'):
                    print(Fore.BLUE + line + Style.RESET_ALL, end='')
                elif line.startswith('-'):
                    print(Fore.RED + line + Style.RESET_ALL, end='')
                elif line.startswith('+'):
                    print(Fore.GREEN + line + Style.RESET_ALL, end='')
                else:
                    print(line, end='')

            print(Style.RESET_ALL)
            print("=" * 60 + "\n")

            base_name = os.path.basename(file_path)                                 #从完整路径中剥离出纯文件名
            name_without_ext = base_name.replace(".cpp", "")                        #去掉 .cpp 后缀，保留文件主名
            output_dir = os.path.join(os.getcwd(), "fixed_output")                  #拼接出输出文件夹的完整路径
            os.makedirs(output_dir, exist_ok=True)                                  #创建文件夹保存fixed文件
            fixed_path = os.path.join(output_dir, f"{name_without_ext}_fixed.cpp")  #拼接出输出文件的完整路径

            with open(fixed_path, "w") as f:
                f.write(fixed_code)
                #创建修改后文件，不修改原文件名
            print(f"修复成功，已保存至 {fixed_path}")
            return

        current_log = result["log"]
        error_history.append(f"第{attempt}次修复后仍报错:\n{current_log}")
        current_code = fixed_code

    print("3次尝试失败，请手动检查。最后一次报错：")
    print(current_log)