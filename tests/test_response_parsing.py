import json
import unittest

from core.fixer import (
    add_line_numbers,
    extract_changes,
    extract_code_from_response,
    extract_logic_report,
    parse_json_object,
)


class ResponseParsingTests(unittest.TestCase):
    def test_plain_and_fenced_json(self):
        for raw in ('{"changes": []}', '```json\n{"changes": []}\n```'):
            with self.subTest(raw=raw):
                self.assertEqual(parse_json_object(raw), {"changes": []})

    def test_invalid_or_non_object_json(self):
        # JSON 数组、数字、null 虽然能解析，但不是项目接受的回复结构。
        for raw in (None, "", "[]", "null", "1", "{broken}", "普通说明"):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_json_object(raw))

    def test_edit_fields(self):
        self.assertEqual(extract_changes('{"changes": []}'), ("", []))
        for data in ({"changes": {}}, {"explanation": 1, "changes": []}, {}):
            with self.subTest(data=data):
                self.assertEqual(extract_changes(json.dumps(data)), ("", None))

    def test_write_fields_and_source_preservation(self):
        # 提取代码时不能 strip 掉缩进或末尾换行。
        code = "  int main() { return 0; }\n"
        self.assertEqual(extract_code_from_response(json.dumps({"code": code})), ("", code))
        for data in ({"code": " "}, {"code": []}, {"code": code, "explanation": 1}):
            with self.subTest(data=data):
                self.assertEqual(extract_code_from_response(json.dumps(data)), ("", ""))
        # 不能把不符合 JSON 格式的说明文字或 C++ 代码块直接当作候选源码。
        self.assertEqual(extract_code_from_response("```cpp\nint main(){}\n```"), ("", ""))

    def test_missing_report_fields_are_not_invented(self):
        report = extract_logic_report('{"original_logic": " 求和 ", "explanation": 123}')
        self.assertEqual(report["original_logic"], "求和")
        for field in ("explanation", "change_effect", "remaining_risks"):
            self.assertEqual(report[field], "未提供")

    def test_line_numbers_include_blank_lines(self):
        # 空行也占行号，否则模型提供的行号会与实际源码错位。
        self.assertEqual(add_line_numbers("a();\n\nb();\n"), "1: a();\n2: \n3: b();")
