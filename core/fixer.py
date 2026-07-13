import openai
import os
from core.sandbox import compile_and_run
import colorama
from colorama import Fore, Style
import difflib

# 初始化 colorama，确保跨平台颜色输出
colorama.init()

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
        以下是一段C++代码及其运行时报错，请修复代码中的错误。
        历史报错记录（需全部解决）：
        {"".join(error_history)}

        当前源码：
        {current_code}

        请输出修复后的完整C++代码，不要加Markdown标记，只输出纯代码。
        """

        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是C++调试专家，只输出纯代码。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2048
        )

        fixed_code = resp.choices[0].message.content
        fixed_code = fixed_code.replace("```cpp", "").replace("```", "").strip()

        result = compile_and_run(fixed_code)
        if result["ok"]:
            # ---------- 新增的彩色输出 ----------
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