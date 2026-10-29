"""External bridge regression: never certify success from exit 0 or scores.

Live checks are optional when the separate backend is not installed. The native
121-test suite remains usable without Git, Cargo or the traditional backend.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import traditional_prosody as bridge


# Synthetic public-interface samples, not upstream source or dictionary data.
PATTERN = "词牌名：测试词牌\n别名：别称\n变体：定格\n格律：\n--- 中仄（韵0）"


def args_for(*argv):
    return bridge.parser().parse_args(list(argv))


class TestBoundaryContract(unittest.TestCase):
    def test_missing_title_and_missing_variant_have_distinct_diagnostics(self):
        backend = bridge.Backend("unused", "cilin")
        for command in ("cipai", "check-ci"):
            for exists in (True, False):
                with self.subTest(command=command, title_exists=exists):
                    argv = (["cipai", "测试词牌", "--variant", "未知变体"] if command == "cipai" else
                            ["check-ci", "--ci-pai", "测试词牌", "--variant", "未知变体", "--poem", "测试"])
                    with patch.object(backend, "run", return_value=PATTERN if exists else "未找到词牌: 测试词牌") as call:
                        report = bridge.make_report(args_for(*argv), backend)
                    self.assertEqual(report["code"], "VARIANT_NOT_FOUND" if exists else "CIPAI_NOT_FOUND")
                    self.assertEqual(report["requested_name"], "测试词牌")
                    self.assertEqual(report["requested_variant"], "未知变体")
                    self.assertEqual(report["available_variants"], ["定格"] if exists else [])
                    self.assertNotIn("selected_pattern", report)
                    self.assertEqual(call.call_count, 1)  # no match-ci-pai call
                    self.assertNotIn("--variant", call.call_args.args)

    def test_exit_zero_with_match_score_one_still_requires_review(self):
        backend = bridge.Backend("unused", "cilin")
        def run(*argv):
            if argv[0] == "query-ci-pai":
                return PATTERN
            if argv[0] == "query-char-rhyme":
                return "韵部: 测试部, 仄, 测试部"
            return "匹配分数：1\n+++ 测试\n--- 中仄（韵0）"
        with patch.object(backend, "run", side_effect=run):
            report = bridge.make_report(args_for("check-ci", "--ci-pai", "测试词牌",
                                                "--variant", "定格", "--poem", "测试"), backend)
        self.assertEqual(report["verdict"], "WARN")
        self.assertEqual(report["relation"], "EXTERNAL_REVIEW_REQUIRED")

    def test_mismatch_text_is_not_converted_into_native_fail(self):
        backend = bridge.Backend("unused", "cilin")
        with patch.object(backend, "run", side_effect=[PATTERN, "未找到韵律信息: 测",
                                                      "未找到韵律信息: 试", "测（平仄错）试"]):
            report = bridge.make_report(args_for("check-ci", "--ci-pai", "测试词牌",
                                                "--variant", "定格", "--poem", "测试"), backend)
        self.assertEqual(report["missing_characters"], ["测", "试"])
        self.assertEqual(report["verdict"], "WARN")

    def test_substring_title_is_not_silently_accepted(self):
        backend = bridge.Backend("unused", "cilin")
        with patch.object(backend, "run", return_value=PATTERN) as call:
            report = bridge.make_report(args_for("check-ci", "--ci-pai", "词牌",
                                                "--variant", "定格", "--poem", "测试"), backend)
        self.assertNotIn("raw_output", report)
        self.assertEqual(call.call_count, 1)  # no matching against a different title

    def test_exact_alias_is_accepted(self):
        backend = bridge.Backend("unused", "cilin")
        with patch.object(backend, "run", return_value=PATTERN):
            matches, _ = bridge.query_cipai(backend, "别称", "定格")
        self.assertEqual(len(matches), 1)

    def test_variant_is_not_silently_substituted(self):
        backend = bridge.Backend("unused", "cilin")
        with patch.object(backend, "run", return_value=PATTERN):
            matches, _ = bridge.query_cipai(backend, "测试词牌", "格一")
        self.assertEqual(matches, [])

    def test_missing_character_is_uncertain_not_no_rhyme(self):
        backend = bridge.Backend("unused", "pingshui")
        with patch.object(backend, "run", side_effect=["韵部: 测试部, 平", "未找到韵律信息: 𠮷"]):
            report = bridge.make_report(args_for("rhyme", "测", "𠮷"), backend)
        self.assertEqual(report["relation"], "UNCERTAIN")

    def test_same_name_with_different_tone_does_not_prove_same_rhyme(self):
        backend = bridge.Backend("unused", "cilin")
        with patch.object(backend, "run", side_effect=["韵部: 测试部, 平, 测试部",
                                                      "韵部: 测试部, 仄, 测试部"]):
            report = bridge.make_report(args_for("rhyme", "测", "试"), backend)
        self.assertEqual(report["relation"], "NO_SHARED_MEMBERSHIP")
        self.assertNotIn("verdict", report)

    def test_partial_new_protocol_cannot_drop_a_reading_silently(self):
        backend = bridge.Backend("unused", "pingshui")
        with patch.object(backend, "run", return_value="韵部: 测试部, 平\nnew-reading-format"):
            with self.assertRaises(bridge.BackendError):
                backend.char("测")

    def test_unknown_pattern_symbol_requires_review_not_guessed_parse(self):
        with self.assertRaises(bridge.BackendError):
            bridge.parse_cipai(PATTERN + "\n--- 平X")

    def test_explicit_missing_backend_does_not_fall_back(self):
        with patch("traditional_prosody.shutil.which", return_value=None):
            with self.assertRaises(bridge.BackendError):
                bridge.find_backend("/not-installed/rhyme-checker")

    def test_backend_errors_and_timeouts_are_not_poem_verdicts(self):
        backend = bridge.Backend("unused", "pingshui")
        for result in [subprocess.CompletedProcess([], 1, "", "unavailable"),
                       subprocess.CompletedProcess([], 0, "", "")]:
            with self.subTest(result=result), patch("traditional_prosody.subprocess.run", return_value=result):
                with self.assertRaises(bridge.BackendError):
                    backend.run("query-char-rhyme", "白")
        with patch("traditional_prosody.subprocess.run", side_effect=subprocess.TimeoutExpired([], 30)):
            with self.assertRaises(bridge.BackendError):
                backend.run("query-char-rhyme", "白")

    def test_poem_is_passed_as_data_without_shell_execution(self):
        backend = bridge.Backend("unused", "cilin")
        poem = "$(do-not-run)；`do-not-run`"
        with patch("traditional_prosody.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 0, "report", "")) as call:
            backend.run("match-ci-pai", "--", poem)
        self.assertEqual(call.call_args.args[0][-1], poem)
        self.assertNotIn("shell", call.call_args.kwargs)
        self.assertIn("--no-color", call.call_args.args[0])

    def test_missing_backend_cli_produces_json_and_nonzero(self):
        output = io.StringIO()
        with patch("traditional_prosody.find_backend", side_effect=bridge.BackendError("not installed")), redirect_stdout(output):
            code = bridge.main(["--json", "char", "白"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "UNCERTAIN")


try:
    LIVE_BACKEND = bridge.find_backend()
except bridge.BackendError:
    LIVE_BACKEND = None


@unittest.skipUnless(LIVE_BACKEND, "optional external backend is not installed")
class TestLiveTraditionalBackend(unittest.TestCase):
    def test_real_unknown_title_and_variant_are_distinguished(self):
        backend = bridge.Backend(LIVE_BACKEND, "cilin")
        for name, variant, expected in [("不存在的词牌987654321", None, "CIPAI_NOT_FOUND"),
                                        ("如梦令", "不存在的变体987654321", "VARIANT_NOT_FOUND")]:
            argv = ["cipai", name] + (["--variant", variant] if variant else [])
            report = bridge.make_report(args_for(*argv), backend)
            self.assertEqual(report["code"], expected)
            self.assertEqual(report["variants"], [])
            self.assertEqual(report["status"], "UNCERTAIN")

    def test_historical_entering_tone_and_rhyme_differ_from_modern(self):
        backend = bridge.Backend(LIVE_BACKEND, "pingshui")
        readings = backend.char("白")["memberships"]
        self.assertTrue(any(r["tone"] == "仄" and "入声" in r["name"] for r in readings))
        report = bridge.make_report(args_for("--dict", "pingshui", "rhyme", "斜", "家"), backend)
        self.assertEqual(report["relation"], "SHARED_MEMBERSHIP")
        self.assertTrue(any(r["name"] == "六麻" for r in report["shared_memberships"]))

    def test_real_cipai_variants_are_selected_explicitly(self):
        backend = bridge.Backend(LIVE_BACKEND, "cilin")
        matches, _ = bridge.query_cipai(backend, "浣溪沙")
        self.assertEqual({v["variant"] for v in matches}, {"格一", "格二（摊破浣溪沙）"})

    def test_real_classical_poem_never_receives_unearned_pass(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = bridge.main(["--backend", LIVE_BACKEND, "--json", "check-ci", "--ci-pai", "如梦令",
                                "--variant", "定格", "--poem",
                                "昨夜雨疏风骤，浓睡不消残酒。试问卷帘人，却道海棠依旧。知否，知否，应是绿肥红瘦。"])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(report["verdict"], "WARN")
        self.assertIn("匹配分数：1", report["raw_output"])
        self.assertFalse(report["missing_characters"])


if __name__ == "__main__":
    unittest.main()
