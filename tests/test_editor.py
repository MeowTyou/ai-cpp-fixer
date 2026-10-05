import copy
import unittest

from core.editor import apply_changes


class EditorTests(unittest.TestCase):
    def test_multiline_text_is_rejected(self):
        # 即使换行只出现在末尾，也不符合“单行替换”的要求。
        for field in ("original", "replacement"):
            for ending in ("\n", "\r", "\r\n"):
                change = {"line": 1, "original": "a();", "replacement": "b();"}
                change[field] += ending
                with self.subTest(field=field, ending=ending):
                    self.assertIsNone(apply_changes("a();\n", [change]))

    def test_invalid_field_types_are_rejected(self):
        # bool 在 Python 中属于 int 的子类，但不能作为 AI 给出的行号。
        invalid = [
            None,
            {"original": 123, "replacement": "b();"},
            {"original": "a();", "replacement": None},
            {"original": "a();", "replacement": "b();", "line": True},
            {"original": "a();", "replacement": "b();", "line": "1"},
            {"original": "a();", "replacement": "b();", "line": 0},
            {"original": "a();", "replacement": "b();", "line": 2},
            {"original": " ", "replacement": "b();"},
        ]
        for change in invalid:
            with self.subTest(change=change):
                self.assertIsNone(apply_changes("a();\n", [change]))
        self.assertIsNone(apply_changes("a();\n", {}))

    def test_duplicate_lines_require_exact_anchor(self):
        source = "a();\nx();\na();\n"
        change = {"line": 3, "original": "a();", "replacement": "b();"}
        self.assertEqual(apply_changes(source, [change]), "a();\nx();\nb();\n")
        # 重复内容存在时，行号指向其他内容或未提供行号，都应拒绝猜测。
        for anchor in (2, None):
            change["line"] = anchor
            with self.subTest(anchor=anchor):
                self.assertIsNone(apply_changes(source, [change]))

    def test_unique_line_allows_offset(self):
        # 内容只出现一次时，允许有效范围内的行号偏差，通过内容唯一定位。
        change = {"line": 1, "original": "b();", "replacement": "c();"}
        self.assertEqual(apply_changes("a();\nb();\n", [change]), "a();\nc();\n")

    def test_same_target_cannot_be_changed_twice(self):
        # 两个不同的 AI 行号最终定位到同一行，也必须拒绝整批修改。
        changes = [
            {"line": 1, "original": "a();", "replacement": "b();"},
            {"line": 2, "original": "a();", "replacement": "c();"},
        ]
        self.assertIsNone(apply_changes("a();\nx();\n", changes))

    def test_batch_uses_original_snapshot(self):
        # 第一项会制造重复内容；第二项仍应按修改前的源码定位。
        changes = [
            {"line": 1, "original": "a();", "replacement": "b();"},
            {"line": 2, "original": "b();", "replacement": "c();"},
        ]
        before = copy.deepcopy(changes)
        self.assertEqual(apply_changes("a();\nb();\n", changes), "b();\nc();\n")
        self.assertEqual(changes, before)  # 不得修改调用者传入的数据。

    def test_line_endings_are_preserved(self):
        for ending in ("\n", "\r\n", ""):
            with self.subTest(ending=ending):
                changes = [{"original": "a();", "replacement": "b();"}]
                self.assertEqual(apply_changes("a();" + ending, changes), "b();" + ending)

    def test_empty_changes_and_empty_replacement(self):
        self.assertEqual(apply_changes("a();\n", []), "a();\n")
        # 空 replacement 是合法的整行清空，与“缺少 replacement 字段”不同。
        self.assertEqual(
            apply_changes("a();\n", [{"original": "a();", "replacement": ""}]),
            "\n",
        )
