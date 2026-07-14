让 AI 帮你检测并调试 C++ 内存错误
调试 C++ 内存错误对初学者和资深开发者都是令人头疼的事。本项目将本地编译器工具链（GCC + AddressSanitizer）与大语言模型相结合，对本地文件的段错误、堆越界、野指针等常见错误提供修复。

-使用 g++ 编译并运行代码，通过-fsanitize=address捕获堆越界、野指针、双重释放等运行时错误，提取崩溃日志中的行号和错误类型，为 AI 修复提供精确依据。
-通过 OpenAI 兼容 API 调用大语言模型。
-采用修复 → 编译验证修复 → 若失败则携带累积错误上下文再次修复的闭环多次尝试修复。
-修复成功后，终端自动打印 git diff 风格的彩色对比方便看清代码的修改，无需打开文件即可直观看到 AI 的改动。



如何开始：
注意：本项目不支持 Windows 原生 MinGW 环境，请使用 WSL2或原生Linux。

-安装WSL2（Windows用户）
-进入WSL，安装g++
-安装Python pip
-克隆/上传项目到 /home/你的名字/
-安装Python依赖
-安装 colorama
-配置 .env


在使用时在终端输入
wsl
cd ~/ai-cpp-fixer
source venv/bin/activate
进行准备

输入python main.py 你的文件名.cpp进行修复



注意：
ASan对越界检测设置红线有限，当超过红线过多时将无法被检测到。
例如对于int a[5]; a[100] = 0; 这样的代码，工具会返回 {"ok": True, "log": ""} 完全漏报。
