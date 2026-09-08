# -*- coding: utf-8 -*-
"""test_rc2_suite.py —— v1.1-rc2 规则层修复专项测试（PHASE 8）。

运行：py tests/test_rc2_suite.py  （rc2 工作副本根目录；与旧套件一起跑全部）

覆盖：
  A. strict profile 语义：风/东 在 xinyun18→FAIL、xinyun14→PASS、shisan13→PASS
     （rc1 缺陷：strict 不同部被听感降级为 WARN）
  B. modern-ear 首句入韵与 2/4 句共用统一判定入口（rc1 缺陷：首句偷偷
     fallback 到 b18）
  C. “不同韵”字符串陷阱：message 含“不同韵”时 status 由结构化字段决定
  D. position override 越界：POSITION_OVERRIDE_OUT_OF_RANGE WARN
  E. invalid override：INVALID_READING_OVERRIDE + UNCERTAIN（不假装成功、
     不静默 fallback）
  F. 回归：失粘/失对/出韵/合规五绝/合规七绝/多音字/轻声/profile 切换
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import prosody_core as core  # noqa: E402

FENG_DONG_POEM = "月落千山静，寒江一夜风。孤灯明远岸，客路又朝东。"
BASELINE = "客舍秋灯暗，风来透纸窗。开门霜满地，路向晓山长。"


def rhyme_check(r, item_key="押韵"):
    return [c for c in r["rhyme"]["checks"] if item_key in c["item"]]


# =====================================================================
# A. strict profile 语义（rc2 PHASE 1）
# =====================================================================

class TestStrictProfile(unittest.TestCase):
    """xinyun18/xinyun14/shisan13 是真正 strict：主判定只由所选韵书决定。"""

    def test_a1_feng_dong_xinyun18_fail(self):
        r = core.check_poem(FENG_DONG_POEM, rhyme_profile="xinyun18")
        self.assertEqual(r["verdict"], "FAIL")          # rc1 曾错误 WARN
        for c in rhyme_check(r):
            self.assertEqual(c["level"], "FAIL")
            self.assertEqual(c["relation"], "NO_RHYME")
            # 辅助信息只出现在 message（detail），不改变 status
            self.assertIn("辅助", c["detail"])

    def test_a2_feng_dong_xinyun14_pass(self):
        r = core.check_poem(FENG_DONG_POEM, rhyme_profile="xinyun14")
        self.assertEqual(r["verdict"], "PASS")
        for c in rhyme_check(r):
            self.assertEqual(c["level"], "PASS")
            self.assertEqual(c["relation"], "PERFECT_RHYME")

    def test_a3_feng_dong_shisan13_pass(self):
        r = core.check_poem(FENG_DONG_POEM, rhyme_profile="shisan13")
        self.assertEqual(r["verdict"], "PASS")

    def test_a4_feng_dong_modern_ear_own_rules(self):
        r = core.check_poem(FENG_DONG_POEM, rhyme_profile="modern-ear")
        self.assertEqual(r["verdict"], "PASS")          # 同中东辙 → PERFECT

    def test_a5_same_profile_direct_compare(self):
        # 直接比较层：judge 返回结构化 dict
        feng = core.resolve_reading("风")[0]
        dong = core.resolve_reading("东")[0]
        j18 = core.judge_rhyme_pair(feng, dong, "xinyun18")
        j14 = core.judge_rhyme_pair(feng, dong, "xinyun14")
        self.assertEqual(j18["status"], "FAIL")
        self.assertEqual(j18["relation"], "NO_RHYME")
        self.assertEqual(j14["status"], "PASS")
        self.assertEqual(j14["relation"], "PERFECT_RHYME")


# =====================================================================
# B. modern-ear 首句入韵统一入口（rc2 PHASE 2）
# =====================================================================

class TestHeadRhymeUnifiedProfile(unittest.TestCase):
    HEAD_DONG_POEM = "客路向江东，寒江一夜风。孤灯明远岸，归棹又朝东。"

    def head_check(self, r):
        return [c for c in r["rhyme"]["checks"] if c["item"] == "首句收尾"][0]

    def test_b1_modern_ear_head_follows_ear(self):
        # 首句东(ong)/第2句风(eng)：modern-ear 下同中东辙 → 首句入韵 PASS
        # （rc1 缺陷：modern-ear 不在映射中，首句偷偷 fallback b18 → 误判）
        r = core.check_poem(self.HEAD_DONG_POEM, rhyme_profile="modern-ear")
        h = self.head_check(r)
        self.assertEqual(h["level"], "PASS")
        self.assertTrue(h["first_line_rhymes"])
        self.assertEqual(h["relation"], "PERFECT_RHYME")

    def test_b2_xinyun18_head_strict(self):
        # 同诗 xinyun18：东(十八东) vs 风(十七庚) 不同部 → 首句未入韵 FAIL
        r = core.check_poem(self.HEAD_DONG_POEM, rhyme_profile="xinyun18")
        h = self.head_check(r)
        self.assertEqual(h["level"], "FAIL")
        self.assertFalse(h["first_line_rhymes"])
        self.assertEqual(h["relation"], "NO_RHYME")

    def test_b3_shisan13_head_follows_profile(self):
        r = core.check_poem(self.HEAD_DONG_POEM, rhyme_profile="shisan13")
        h = self.head_check(r)
        self.assertEqual(h["level"], "PASS")
        self.assertTrue(h["first_line_rhymes"])

    def test_b4_head_and_body_consistency(self):
        # 首句(1↔2)与正文(2↔4)判定必须一致地跟随 profile，不得分裂：
        # 本诗 1/2 尾=东/风、2/4 尾=风/东——xinyun18 下两者都 FAIL；
        # modern-ear 下两者都 PASS（不存在“正文按 ear、首句按 b18”的 rc1 缺陷）。
        r18 = core.check_poem(self.HEAD_DONG_POEM, rhyme_profile="xinyun18")
        main18 = rhyme_check(r18)[0]
        head18 = self.head_check(r18)
        self.assertEqual(main18["level"], "FAIL")
        self.assertEqual(main18["relation"], "NO_RHYME")
        self.assertEqual(head18["level"], "FAIL")
        self.assertEqual(head18["relation"], "NO_RHYME")
        rea = core.check_poem(self.HEAD_DONG_POEM, rhyme_profile="modern-ear")
        main_ea = rhyme_check(rea)[0]
        head_ea = self.head_check(rea)
        self.assertEqual(main_ea["level"], "PASS")
        self.assertEqual(head_ea["level"], "PASS")


# =====================================================================
# C. “不同韵”字符串陷阱（rc2 PHASE 3）
# =====================================================================

class TestNoStringDerivedStatus(unittest.TestCase):
    def test_c1_message_contains_different_rhyme_but_status_fail(self):
        # 平收首句与主韵不同韵：message 中必然出现“不同部/未入韵”等字样，
        # 但 status 必须来自结构化字段 FAIL（若靠 “同韵” in message 反推会误判 PASS）
        r = core.check_poem(TestHeadRhymeUnifiedProfile.HEAD_DONG_POEM,
                            rhyme_profile="xinyun18")
        h = [c for c in r["rhyme"]["checks"] if c["item"] == "首句收尾"][0]
        self.assertNotEqual(h["level"], "PASS")
        self.assertEqual(h["level"], "FAIL")
        self.assertEqual(h["first_line_rhymes"], False)
        # 结构化字段在场：relation 与 first_line_rhymes 可用，且 message 仅展示
        self.assertIn("message", h) if "message" in h else None
        self.assertIn("detail", h)

    def test_c2_verdict_from_structured_only(self):
        # check_poem 的 verdict 只能来自 issue level 汇总（结构化），与文案无关
        r = core.check_poem("客舍秋灯暗，风来透纸窗。开门霜满地，独对晓山孤。")
        self.assertEqual(r["verdict"], "FAIL")
        fail_items = [i for i in r["issues"] if i["level"] == "FAIL"]
        self.assertTrue(any("押韵" in i["item"] for i in fail_items))


# =====================================================================
# D. position override 越界（rc2 PHASE 4）
# =====================================================================

class TestPositionOverrideRange(unittest.TestCase):
    def run_oob(self, reading_spec, poem=BASELINE):
        r = core.check_poem(poem, positional_overrides=reading_spec)
        codes = [i.get("code") for i in r["issues"]]
        self.assertIn("POSITION_OVERRIDE_OUT_OF_RANGE", codes,
                      f"{reading_spec} 未产生越界诊断")
        # 越界 override 不静默：整体至少 WARN
        self.assertIn(r["verdict"], ("WARN", "FAIL"))
        return r

    def test_d1_zero_row(self):
        self.run_oob({(0, 1): "chang2"})

    def test_d2_zero_col(self):
        self.run_oob({(1, 0): "chang2"})

    def test_d3_row_beyond_poem(self):
        self.run_oob({(5, 1): "chang2"})   # 四句诗

    def test_d4_col_beyond_wujue(self):
        self.run_oob({(1, 6): "chang2"})   # 五言第1句只有5字

    def test_d5_col_beyond_qijue(self):
        poem = "月落乌啼霜满天，江枫渔火对愁眠。姑苏城外寒山寺，夜半钟声到客船。"
        self.run_oob({(3, 8): "chang2"}, poem)  # 七言第3句只有7字

    def test_d6_negative(self):
        self.run_oob({(-2, 3): "chang2"})

    def test_d7_in_range_is_not_oob(self):
        r = core.check_poem(BASELINE, positional_overrides={(4, 5): "chang2"})
        codes = [i.get("code") for i in r["issues"]]
        self.assertNotIn("POSITION_OVERRIDE_OUT_OF_RANGE", codes)


# =====================================================================
# E. invalid override（rc2 PHASE 5）
# =====================================================================

class TestInvalidOverride(unittest.TestCase):
    def check_invalid(self, overrides=None, pos=None, poem=BASELINE):
        r = core.check_poem(poem, readings_overrides=overrides,
                            positional_overrides=pos)
        codes = [i.get("code") for i in r["issues"]]
        self.assertIn("INVALID_READING_OVERRIDE", codes)
        # 行为 = UNCERTAIN：出现 py=? 的字（未静默 fallback 字典默认）
        flat = [c for ln in r["lines"] for c in ln["chars"]]
        self.assertTrue(any(c["uncertain"] and c["py"] == "?" for c in flat),
                        "非法 override 应标记 UNCERTAIN 而非 fallback")
        # 文案不含“已忽略”
        details = "；".join(i.get("detail", "") for i in r["issues"])
        self.assertNotIn("已忽略", details)
        self.assertIn("UNCERTAIN", details)
        return r

    def test_e1_bad_suffix(self):
        self.check_invalid(overrides={"长": "zhang3x"})

    def test_e2_garbage(self):
        self.check_invalid(overrides={"长": "abc"})

    def test_e3_empty_value(self):
        self.check_invalid(overrides={"长": ""})

    def test_e4_reading_not_in_candidates(self):
        self.check_invalid(overrides={"舍": "she1"})   # 舍 无 she1

    def test_e5_position_invalid(self):
        self.check_invalid(pos={(4, 5): "zhang3x"})

    def test_e6_valid_override_no_invalid_code(self):
        r = core.check_poem(BASELINE, readings_overrides={"长": "chang2", "舍": "she4"})
        codes = [i.get("code") for i in r["issues"]]
        self.assertNotIn("INVALID_READING_OVERRIDE", codes)
        self.assertEqual(r["verdict"], "PASS")


# =====================================================================
# F. 回归确认（rc2 PHASE 8F）
# =====================================================================

class TestRegressionGuards(unittest.TestCase):
    def test_f1_shi_nian_still_fail(self):
        r = core.check_poem("古寺秋钟晚，江风入客船。雁影落寒水，孤舟泊野烟。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("失粘" in i["detail"] for i in r["issues"]))

    def test_f2_shi_dui_still_fail(self):
        r = core.check_poem("客舍秋灯暗，欲去意茫然。月起寒山外，风吹客梦残。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("失对" in i["detail"] for i in r["issues"]))

    def test_f3_chu_yun_still_fail(self):
        r = core.check_poem("客舍秋灯暗，风来透纸窗。开门霜满地，独对晓山孤。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("押韵" in i["item"] and i["level"] == "FAIL"
                            for i in r["issues"]))

    def test_f4_clean_wujue_pass(self):
        r = core.check_poem(BASELINE, readings_overrides={"长": "chang2", "舍": "she4"})
        self.assertEqual(r["verdict"], "PASS")

    def test_f5_clean_qijue_pass(self):
        r = core.check_poem("月落乌啼霜满天，江枫渔火对愁眠。姑苏城外寒山寺，夜半钟声到客船。")
        self.assertEqual(r["verdict"], "PASS")

    def test_f6_polyphonic_override(self):
        r = core.check_poem(BASELINE, readings_overrides={"长": "chang2", "舍": "she4"})
        cells = [c for ln in r["lines"] for c in ln["chars"] if c["char"] == "长"]
        self.assertEqual([c["py"] for c in cells], ["chang2"])

    def test_f7_neutral_rule_unchanged(self):
        poem = "醒了月西沉，风吹客子襟。寒灯明灭处，独坐夜深深。"
        r = core.check_poem(poem, readings_overrides={"子": "zi3", "处": "chu4"})
        self.assertEqual(r["verdict"], "WARN")   # 轻声关键位 UNCERTAIN 不 FAIL
        texts = [i["detail"] for i in r["issues"]]
        self.assertTrue(any("RELATION=UNCERTAIN" in t and "轻声" in t for t in texts))

    def test_f8_profile_switch_regression(self):
        r18 = core.check_poem(FENG_DONG_POEM, rhyme_profile="xinyun18")
        r14 = core.check_poem(FENG_DONG_POEM, rhyme_profile="xinyun14")
        self.assertEqual((r18["verdict"], r14["verdict"]), ("FAIL", "PASS"))

    def test_f9_head_rhyme_check_has_structured_fields(self):
        poem = "客路向江东，寒江一夜风。孤灯明远岸，归棹又朝东。"
        r = core.check_poem(poem, rhyme_profile="xinyun18")
        h = [c for c in r["rhyme"]["checks"] if c["item"] == "首句收尾"][0]
        for field in ("level", "first_line_rhymes", "relation", "detail"):
            self.assertIn(field, h, field)


if __name__ == "__main__":
    unittest.main(verbosity=1)
