让 AI 帮你检测并调试 C++ 内存错误
调试 C++ 内存错误对初学者和资深开发者都是令人头疼的事。本项目将本地编译器工具链（GCC + AddressSanitizer）与大语言模型相结合，对本地文件的段错误、堆越界、野指针等常见错误提供修复。

精准错误捕获：使用 g++ -fsanitize=address 编译并运行代码，捕获堆越界、野指针、双重释放等运行时错误，提取崩溃日志中的行号和错误类型，为 AI 修复提供精确依据。

双修复模式：
edit 模式（默认）：AI 只返回被修改的行，工具在原文件基础上做精确替换，未修改的内容（注释、空行、缩进）完全保留。
write 模式：AI 返回修复后的完整代码，适合大规模重构场景。
auto 模式：edit 优先，匹配失败自动降级为 write，兼顾最小侵入与容错。
ReAct 闭环：修复 → 编译验证 → 若失败则携带累积错误上下文再次修复，最多重试 3 次。

安全补丁应用：
交互式应用补丁（--apply），预览差异后确认。
非交互式直接应用（--yes），适合自动化脚本。
应用前自动备份（.bak），失败时自动回滚。
支持仅生成 .patch 文件供手动审查。
彩色差异对比：终端自动打印 git diff 风格的彩色对比（红色=删除，绿色=新增），无需打开文件即可直观看到 AI 的改动。
多层容错解析：AI 返回内容经过 JSON → Markdown → 原文三层降级解析，容忍模型输出格式偏差。
异常分类处理：网络错误、限流、认证失败、服务器错误分别处理，不会因 API 异常导致程序崩溃。


如何开始：
注意：本项目不支持 Windows 原生 MinGW 环境，请使用 WSL2或原生Linux。

-安装WSL2（Windows用户）
-进入WSL，安装g++
-安装Python pip
-克隆/上传项目到 /home/你的名字/
-安装Python依赖
-安装 colorama
-配置 .env


命令速查表
| 命令 | 修复模式 | 操作模式 | 修改原文件 |
| :--- | :--- | :--- | :--- |
| `python main.py test.cpp` | auto | 默认 | ❌ |
| `python main.py test.cpp --apply` | auto | 交互补丁 | 确认后 |
| `python main.py test.cpp --yes` | auto | 直接补丁 | ✅ |
| `python main.py test.cpp --patch` | auto | 生成补丁 | ❌ |
| `python main.py test.cpp --diff` | auto | 显示差异 | ❌ |
| `python main.py test.cpp --edit` | edit only | 默认 | ❌ |
| `python main.py test.cpp --write` | write only | 默认 | ❌ |
| `python main.py test.cpp --apply --edit` | edit only | 交互补丁 | 确认后 |
| `python main.py test.cpp --apply --write` | write only | 交互补丁 | 确认后 |
| `python main.py test.cpp --yes --edit` | edit only | 直接补丁 | ✅ |
| `python main.py test.cpp --yes --write` | write only | 直接补丁 | ✅ |
| `python main.py test.cpp --patch --edit` | edit only | 生成补丁 | ❌ |
| `python main.py test.cpp --patch --write` | write only | 生成补丁 | ❌ |
| `python main.py test.cpp --diff --edit` | edit only | 显示差异 | ❌ |
| `python main.py test.cpp --diff --write` | write only | 显示差异 | ❌ |

参数速查

操作模式（互斥）：
`--apply` 交互补丁 / `--yes` 直接补丁 / `--patch` 生成补丁 / `--diff` 显示差异

修复模式（互斥）：
`--edit` 仅局部替换 / `--write` 强制整体覆盖 / 默认 `auto` 优先 edit，失败降级 write