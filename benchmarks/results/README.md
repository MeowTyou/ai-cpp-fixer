# 手动评测结果

- `cases/`：固定的 C++ 样例；源码注释中写明程序用途、故意保留的错误和预期输出。
- `results/`：保存本次修复代码、日志和手动记录。

## 样例

| 文件 | 原始状态 | 正确修改 |
| --- | --- | --- |
| `compile_error.cpp` | 输出语句缺少分号，不能编译 | 在 `std::cout << sum << '\n'` 末尾补上分号，保留求和循环和输出语句。 |
| `array_bounds.cpp` | 数组越界 | 将循环条件 `i <= 4` 改为 `i < 4`，只访问下标 0 到 3，保留全部 4 个元素的求和和输出。 |
| `use_after_free.cpp` | 释放后访问 | 将 `delete value;` 移到读取并输出 `*value` 之后，确保读取时内存仍有效，并在使用完毕后释放。 |
| `double_free.cpp` | 重复释放 | 删除重复释放操作，使同一块内存只被释放一次，保留读取和输出，不引入内存泄漏。 |
| `correct_sum.cpp` | 已知正确 | 无需修改；若提出修改，应保留全部 4 个元素的求和和输出，不能通过删除计算或直接输出固定值来替代原功能。 |

以上是参考修改方式；等价的安全实现也可以通过，但应保留原有功能，并通过编译、运行检查。

| 样例 | 是否通过 | 失败原因 |
| --- | --- | --- |
| `compile_error.cpp` | 通过 | null |
| `array_bounds.cpp` | 通过 | null |
| `use_after_free.cpp` | 通过 | null |
| `double_free.cpp` | 通过 | null |
| `correct_sum.cpp` | 通过 | null |

样例通过数：5/5。

cd ~/ai-cpp-fixer
source venv/bin/activate
python main.py benchmarks/cases/correct_sum.cpp

