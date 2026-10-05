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
应用时检查原文件是否在 AI 处理期间发生变化，避免覆盖用户的新修改。
写入前保存唯一的 .bak.* 备份，成功后仍保留；通过同目录临时文件替换，避免写入一半留下损坏的源码。
支持仅生成 .patch 文件供手动审查。
彩色差异对比：终端自动打印 git diff 风格的彩色对比（红色=删除，绿色=新增），无需打开文件即可直观看到 AI 的改动。
多层容错解析：AI 返回内容经过 JSON → Markdown → 原文三层降级解析，容忍模型输出格式偏差。
异常分类处理：网络错误、限流、认证失败、服务器错误分别处理，不会因 API 异常导致程序崩溃。


## 如何开始

运行环境：

- Windows 用户使用 WSL2，或使用原生 Linux；不支持 Windows 原生 MinGW 环境。
- 当前开发环境为 Python 3.12，建议使用同一版本。
- 系统中需要安装 g++，支持 C++17 和 AddressSanitizer。
- Python 需要可用的 pip 和 venv 组件。

将项目克隆或复制到 WSL/Linux 的用户目录，例如 `/home/你的用户名/ai-cpp-fixer`。
在项目根目录创建并激活虚拟环境，安装依赖：

```bash
cd ~/ai-cpp-fixer
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

如果已有项目虚拟环境，激活后执行安装命令即可。
`requirements.txt` 固定项目直接使用的 Python 依赖版本；pip 会同时安装它们需要的间接依赖。
g++ 属于系统依赖，需要单独安装。

最后按照 `.env.example` 配置本地 `.env`，然后运行项目。


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


## 测试与持续集成

在项目根目录、激活虚拟环境后运行自动化测试：

```bash
python -m unittest discover -s tests -v
```

测试使用 Python 自带的 `unittest`。模型请求使用测试替身，不调用真实 AI，也不需要 API 密钥。
测试覆盖模型回复校验、重复行定位、补丁与备份、超时和子进程环境、CLI 退出码及输出丢失拦截。
系统的 `patch` 命令用于补丁实际应用测试；未安装时该项测试会跳过，CI 会安装它。

GitHub Actions 配置位于 `.github/workflows/ci.yml`：

- 推送代码或提交、更新 PR 时自动运行，也可从仓库的 Actions 页面手动启动。
- 使用 Ubuntu 24.04 和 Python 3.12，安装系统工具和 `requirements.txt` 中的依赖，再运行测试。
- 测试失败时，CI 任务显示失败；详细日志可在 Actions 页面查看。

需要将工作流、`tests/` 和 `requirements.txt` 一起提交并推送到 GitHub，才能在远端运行。
这些测试属于回归检查，不代表真实 AI 的修复效果评测或完整的程序逻辑验证。
