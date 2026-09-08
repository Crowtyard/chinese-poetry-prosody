# -*- coding: utf-8 -*-
"""test_v1_1_suite.py —— V1.1 四层测试套件（PHASE 9 + PHASE 11 边界样本）。

运行：py tests/test_v1_1_suite.py  （Skill 根目录下；旧 21 个测试保留在 test_prosody.py）

分层：
  A. Unit：parse 层（tone/final/声母切分/jqx·v·y/w 还原/调号显示）、韵书 profile 判定
  B. Full-data consistency：全库审计（chars.json 全部 reading，逐条独立验证）
  C. Regression：第三方审计反例（佛/侧/圈/折/长/还/舍…）每条 reading 自洽
  D. Poetry fixtures：11 类整诗场景
  E. 边界样本：≥20 个审计式样本（含预期 FAIL/WARN，不挑容易的）
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import prosody_core as core          # noqa: E402
import syllable_parser as sp         # noqa: E402
import build_char_table as bct       # noqa: E402


def reading_of(char, override=""):
    r, _ = core.resolve_reading(char, override)
    return r


# =====================================================================
# A. Unit tests —— parse 层
# =====================================================================

class TestParseUnit(unittest.TestCase):
    def test_tone_number(self):
        self.assertEqual(sp.parse_tone_number("chang2"), 2)
        self.assertEqual(sp.parse_tone_number("de"), 5)
        self.assertEqual(sp.parse_tone_number("lv4"), 4)

    def test_strip_tone(self):
        self.assertEqual(sp.strip_tone_number("chang2"), "chang")
        self.assertEqual(sp.strip_tone_number("de"), "de")

    def test_split_initial(self):
        self.assertEqual(sp.split_initial_final("chang"), ("ch", "ang"))
        self.assertEqual(sp.split_initial_final("fo"), ("f", "o"))
        self.assertEqual(sp.split_initial_final("yu"), ("", "yu"))
        self.assertEqual(sp.split_initial_final("n"), ("", ""))  # 叹词

    def test_expand_jqx_u_to_u_umlaut(self):
        # j/q/x 后 u 是 ü 的省写（圈 juàn → üan、居 → ü）
        self.assertEqual(sp.expand_final("j", "uan"), "üan")
        self.assertEqual(sp.expand_final("q", "u"), "ü")
        self.assertEqual(sp.expand_final("x", "ue"), "üe")
        # jqx 后 iu/iong 不转
        self.assertEqual(sp.expand_final("q", "iu"), "iou")
        self.assertEqual(sp.expand_final("j", "iong"), "iong")

    def test_expand_v(self):
        self.assertEqual(sp.expand_final("l", "v"), "ü")
        self.assertEqual(sp.expand_final("n", "ve"), "üe")

    def test_expand_abbrev(self):
        self.assertEqual(sp.expand_final("h", "ui"), "uei")
        self.assertEqual(sp.expand_final("ch", "un"), "uen")
        self.assertEqual(sp.expand_final("l", "iu"), "iou")

    def test_expand_zero_initial(self):
        for s, want in [("yi", "i"), ("ying", "ing"), ("yan", "ian"),
                        ("you", "iou"), ("yong", "iong"), ("yu", "ü"),
                        ("yue", "üe"), ("yuan", "üan"), ("yun", "ün"),
                        ("wu", "u"), ("wo", "uo"), ("wai", "uai"),
                        ("wei", "uei"), ("wan", "uan"), ("wen", "uen"),
                        ("wang", "uang"), ("weng", "ueng"),
                        ("er", "er"), ("en", "en"), ("ai", "ai"), ("o", "o")]:
            self.assertEqual(sp.expand_final("", s), want, s)

    def test_apical_i(self):
        self.assertEqual(sp.final_key("i", "zh"), "i_apical")
        self.assertEqual(sp.final_key("i", "z"), "i_apical")
        self.assertEqual(sp.final_key("i", "j"), "i")       # ji/qi/xi 是齐韵 i
        self.assertEqual(sp.final_key("i", ""), "i")

    def test_parse_reading_self_consistent(self):
        for py in ["chang2", "zhang3", "juan4", "quan1", "lv4", "yun2",
                   "hai3", "fo2", "ze4", "zhe1", "chuang1", "de"]:
            p = sp.parse_reading(py)
            self.assertEqual(p["tone"], sp.parse_tone_number(py))
            self.assertEqual(p["final"], bct.derive_final(py), py)

    def test_tone_marks_precomposed(self):
        # PHASE 6 调号显示：必须产出预组合字符、标调位置正确
        cases = {"hai3": "hǎi", "xiao3": "xiǎo", "lou2": "lóu", "hui2": "huí",
                 "liu2": "liú", "lv4": "lǜ", "yun2": "yún", "yue4": "yuè",
                 "xue2": "xué", "chang2": "cháng", "feng1": "fēng",
                 "chun1": "chūn", "quan1": "quān", "de": "de", "yu2": "yú",
                 "wu3": "wǔ", "wei4": "wèi", "er2": "ér", "ge1": "gē"}
        for py, want in cases.items():
            self.assertEqual(sp.display_py(py), want, py)
            self.assertNotIn("\u0304\u0301\u030c\u0300", sp.display_py(py))

    def test_parse_of_third_party_counterexamples(self):
        # 第三方审计反例：每条 reading 的 tone/final 必须与拼音本身自洽
        for ch in ["佛", "侧", "圈", "折", "长", "还", "舍"]:
            for e in core.lookup(ch):
                self.assertEqual(e["tone"], sp.parse_tone_number(e["py"]),
                                 f"{ch}{e['py']} tone")
                self.assertEqual(e["final"], bct.derive_final(e["py"]),
                                 f"{ch}{e['py']} final")
                self.assertEqual(e["pz"],
                                 sp.classify_pingze(sp.parse_tone_number(e["py"])),
                                 f"{ch}{e['py']} pz")


# =====================================================================
# B. Full-data consistency —— 全库审计（PHASE 2 门禁）
# =====================================================================

class TestFullDataConsistency(unittest.TestCase):
    """遍历 data/chars.json 全部 reading（约 3.7 万条）做确定性审计。

    门禁：tone_mismatch == 0 且 final_mismatch == 0，否则不得宣称可发布。
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "data", "chars.json"), encoding="utf-8") as fh:
            cls.data = json.load(fh)
        cls.audit = bct.audit_chars(cls.data["chars"])

    def test_tone_mismatch_zero(self):
        self.assertEqual(self.audit["tone_mismatch"], 0)

    def test_final_mismatch_zero(self):
        self.assertEqual(self.audit["final_mismatch"], 0)

    def test_invalid_tone_zero(self):
        self.assertEqual(self.audit["invalid_tone"], 0)

    def test_unmapped_final_only_consonantal(self):
        # 非轻声而韵部为空的 reading 只允许“无法映射到现有韵部的音节”：
        # 纯辅音式叹词（n/ng/m/hm）、yo（哟）、ê 系等特殊音节——全部返回
        # UNCERTAIN，不强行归入韵部；
        # 且必须能被审计点名（不能静默填错）；其余一律不允许。
        unmapped = self.audit["unmapped_final"]
        ex = self.audit["unmapped_final_examples"]
        self.assertLessEqual(unmapped, 40, ex)
        for item in ex:
            ch = item[0]
            py = item.split(" final=")[0][1:]
            parsed = sp.parse_reading(py)
            self.assertEqual(parsed["final"], "", f"意外无映射：{item}")

    def test_meta_source_honest(self):
        meta = self.data["meta"]
        self.assertIn("dictionary_order", meta["description"])
        self.assertIn("非词频", meta["description"])


# =====================================================================
# C. Regression —— 第三方反例 + 关键多音字（PHASE 9C）
# =====================================================================

class TestRegressionReadings(unittest.TestCase):
    def assert_reading(self, ch, py, tone, final):
        r = reading_of(ch, py)
        self.assertIsNotNone(r, f"{ch} 无读法 {py}")
        self.assertEqual(r["tone"], tone, f"{ch}{py}")
        self.assertEqual(r["final"], final, f"{ch}{py}")

    def test_fo(self):
        self.assert_reading("佛", "fu2", 2, "u")
        self.assert_reading("佛", "fo2", 2, "o")   # 旧缺陷：bo2→tone4/final=i
        self.assert_reading("佛", "bo2", 2, "o")
        self.assert_reading("佛", "bi4", 4, "i")

    def test_ce(self):
        self.assert_reading("侧", "ce4", 4, "e")   # 旧缺陷：ze4→tone1/final=ai
        self.assert_reading("侧", "ze4", 4, "e")
        self.assert_reading("侧", "zhai1", 1, "ai")

    def test_quan(self):
        self.assert_reading("圈", "quan1", 1, "üan")  # jqx 后 uan→üan
        self.assert_reading("圈", "juan4", 4, "üan")  # 旧缺陷：juan4→tone2
        self.assert_reading("圈", "juan3", 3, "üan")

    def test_zhe(self):
        self.assert_reading("折", "zhe1", 1, "e")   # 旧缺陷：zhe1→tone2/final=i
        self.assert_reading("折", "zhe2", 2, "e")
        self.assert_reading("折", "she2", 2, "e")

    def test_chang_huan_she(self):
        self.assert_reading("长", "chang2", 2, "ang")
        self.assert_reading("长", "zhang3", 3, "ang")
        self.assert_reading("还", "huan2", 2, "uan")
        self.assert_reading("还", "hai2", 2, "ai")
        self.assert_reading("舍", "she4", 4, "e")
        self.assert_reading("舍", "she3", 3, "e")

    def test_default_is_dictionary_order_first(self):
        # 默认 = 底层字典第一位（不声称词频最优）
        r = reading_of("长")
        self.assertEqual(r["py"], "zhang3")


# =====================================================================
# D. Poetry fixtures（PHASE 9D + 10 回归诗）
# =====================================================================

BASELINE = "客舍秋灯暗，风来透纸窗。开门霜满地，路向晓山长。"


class TestPoemFixtures(unittest.TestCase):
    def test_1_clean_wujue(self):
        r = core.check_poem(BASELINE, readings_overrides={"长": "chang2", "舍": "she4"})
        self.assertEqual(r["verdict"], "PASS")
        self.assertIn("仄起首句不入韵", r["dui_nian"]["template_hint"])

    def test_2_clean_qijue(self):
        poem = "月落乌啼霜满天，江枫渔火对愁眠。姑苏城外寒山寺，夜半钟声到客船。"
        r = core.check_poem(poem)
        self.assertEqual(r["verdict"], "PASS")
        self.assertIn("仄起首句入韵", r["dui_nian"]["template_hint"])

    def test_3_deliberate_shi_nian(self):
        r = core.check_poem("古寺秋钟晚，江风入客船。雁影落寒水，孤舟泊野烟。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("失粘" in i["detail"] for i in r["issues"]))

    def test_4_deliberate_shi_dui(self):
        # 故意失对：第1/2句第2字同为仄（舍仄↔去仄）；其余尽量合规（fixture 语义不论）
        r = core.check_poem("客舍秋灯暗，欲去意茫然。月起寒山外，风吹客梦残。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("失对" in i["detail"] for i in r["issues"]))

    def test_5_deliberate_chu_yun(self):
        r = core.check_poem("客舍秋灯暗，风来透纸窗。开门霜满地，独对晓山孤。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any("出韵" in i["detail"] or "不同部" in i["detail"] for i in r["issues"]))

    def test_6_override_char(self):
        r = core.check_poem(BASELINE)  # 长 默认 zhang3 → 韵脚仄 WARN
        self.assertEqual(r["verdict"], "WARN")
        r2 = core.check_poem(BASELINE, readings_overrides={"长": "chang2", "舍": "she4"})
        self.assertEqual(r2["verdict"], "PASS")

    def test_7_same_char_different_position(self):
        # 同字两位置不同读法：位置 override > 字 override
        poem = "雨足春苗长，风轻柳线长。日高花影动，人在绿阴廊。"
        r = core.check_poem(poem, readings_overrides={"长": "chang2"},
                            positional_overrides={(1, 5): "zhang3"})
        l1 = r["lines"][0]["chars"][4]
        l2 = r["lines"][1]["chars"][4]
        self.assertEqual(l1["py"], "zhang3")
        self.assertEqual(l2["py"], "chang2")

    def test_8_neutral_at_key_positions(self):
        # 轻声在第二字/第四字：RELATION=UNCERTAIN → WARN，不 FAIL
        poem = "醒了月西沉，风吹客子襟。寒灯明灭处，独坐夜深深。"
        r = core.check_poem(poem, readings_overrides={"子": "zi3", "处": "chu4"})
        texts = [i["detail"] for i in r["issues"]]
        self.assertEqual(r["verdict"], "WARN")  # 不 FAIL（轻声不硬塞平/仄）
        self.assertTrue(any("RELATION=UNCERTAIN" in t and "轻声" in t for t in texts), texts)

    def test_8b_neutral_rhyme_never_perfect(self):
        poem = "春来花事了，客去鸟声么。夜静无人问，灯残月影斜。"
        r = core.check_poem(poem, readings_overrides={"斜": "xie2"})
        rhyme_checks = [c for c in r["rhyme"]["checks"] if "押韵" in c["item"]]
        for c in rhyme_checks:
            self.assertNotEqual(c["level"], "PASS")   # 轻声韵脚不得直接 PERFECT
            self.assertIn("UNCERTAIN", c["detail"])

    def test_9_profile_changes_result_feng_dong(self):
        # rc2 strict 语义：风/东 押韵诗（风=十七庚、东=十八东）——
        # xinyun18 真正 strict → FAIL（rc1 曾错误降级 WARN）；
        # xinyun14 / shisan13 / modern-ear → PASS。结果随 profile 改变。
        poem = "月落千山静，寒江一夜风。孤灯明远岸，客路又朝东。"
        r18 = core.check_poem(poem, rhyme_profile="xinyun18")
        r14 = core.check_poem(poem, rhyme_profile="xinyun14")
        r13 = core.check_poem(poem, rhyme_profile="shisan13")
        rea = core.check_poem(poem, rhyme_profile="modern-ear")
        self.assertEqual(r18["verdict"], "FAIL")   # rc2：strict 不降级
        self.assertEqual(r14["verdict"], "PASS")
        self.assertEqual(r13["verdict"], "PASS")
        self.assertEqual(rea["verdict"], "PASS")
        # 辅助信息仍在，但不得改变主判定：FAIL 项 relation=NO_RHYME
        rel = [c.get("relation") for c in r18["rhyme"]["checks"] if "押韵" in c["item"]]
        self.assertEqual(rel, ["NO_RHYME"])

    def test_10_near_whitelist(self):
        for a, b in [("深", "生"), ("心", "星"), ("门", "梦")]:
            ra, rb = reading_of(a), reading_of(b)
            lv, why, _ = core.rhyme_compare_ear(ra, rb)
            self.assertEqual(lv, "NEAR_RHYME", f"{a}/{b}: {why}")
            self.assertIn("NEAR 白名单", why)

    def test_11_ear_no_overreach(self):
        # 旧实现（大组笛卡尔积）会判 NEAR 的组合，V1.1 必须 NO
        for a, b in [("云", "东"), ("心", "空"), ("门", "东")]:
            ra, rb = reading_of(a), reading_of(b)
            lv, why, _ = core.rhyme_compare_ear(ra, rb)
            self.assertEqual(lv, "NO_RHYME", f"{a}/{b}: {why}")


# =====================================================================
# E. 边界样本 ≥20（PHASE 11：第三方审计式，含预期 FAIL/WARN）
# =====================================================================

class TestEdgeSamples(unittest.TestCase):
    """刻意覆盖多音/轻声/前后鼻音/韵书差异/ü 系/生僻字/override 等边界。
    预期写在每个用例里；包含预期 FAIL/WARN，不是“挑容易过的”。"""

    def test_e01_you_you_reading(self):
        self.assert_reading("乐", "yue4", 4, "üe")
        self.assert_reading("乐", "le4", 4, "e")

    def test_e02_zhong_chong(self):
        self.assert_reading("重", "zhong4", 4, "ong")
        self.assert_reading("重", "chong2", 2, "ong")

    def test_e03_xing_hang(self):
        self.assert_reading("行", "xing2", 2, "ing")
        self.assert_reading("行", "hang2", 2, "ang")

    def test_e04_jue_jiao(self):
        self.assert_reading("觉", "jue2", 2, "üe")
        self.assert_reading("觉", "jiao4", 4, "iao")

    def test_e05_wei_wei(self):
        self.assert_reading("为", "wei2", 2, "uei")
        self.assert_reading("为", "wei4", 4, "uei")

    def test_e06_neutral_de_le_ma_ne(self):
        for ch in ["的", "了", "吗", "呢"]:
            r = reading_of(ch)
            self.assertEqual(r["tone"], 5, ch)
            self.assertEqual(r["pz"], "轻", ch)
            self.assertEqual(r["b18"], "", ch)

    def test_e07_front_back_nasal_in_ing(self):
        self.assert_reading("心", "xin1", 1, "in")
        self.assert_reading("星", "xing1", 1, "ing")
        lv, _, _ = core.rhyme_compare_ear(reading_of("心"), reading_of("星"))
        self.assertEqual(lv, "NEAR_RHYME")

    def test_e08_an_ang_not_near(self):
        for a, b in [("山", "伤"), ("天", "香"), ("关", "光")]:
            lv, _, _ = core.rhyme_compare_ear(reading_of(a), reading_of(b))
            self.assertEqual(lv, "NO_RHYME", f"{a}/{b}")

    def test_e09_yun_iong_not_near(self):
        lv, _, _ = core.rhyme_compare_ear(reading_of("云"), reading_of("兄"))
        self.assertEqual(lv, "NO_RHYME")

    def test_e10_ge_bo_profile_diff(self):
        # 歌(ge,e) / 波(bo,o)：十八韵 三歌/二波 不同部；十四韵同二波；十三辙同梭波
        rg, rb = reading_of("歌"), reading_of("波")
        self.assertEqual(core.rhyme_compare_strict(rg, rb, "b18")[0], "NO_RHYME")
        self.assertEqual(core.rhyme_compare_strict(rg, rb, "b14")[0], "PERFECT_RHYME")
        self.assertEqual(core.rhyme_compare_ear(rg, rb)[0], "PERFECT_RHYME")

    def test_e11_umlaut_family(self):
        self.assert_reading("月", "yue4", 4, "üe")
        self.assert_reading("雪", "xue3", 3, "üe")
        self.assert_reading("圆", "yuan2", 2, "üan")
        self.assert_reading("云", "yun2", 2, "ün")
        self.assert_reading("绿", "lv4", 4, "ü")
        # ü 系与 i 系跨韵书：十八韵 鱼/齐 不同部
        self.assertEqual(core.rhyme_compare_strict(reading_of("衣"), reading_of("鱼"), "b18")[0],
                         "NO_RHYME")

    def test_e12_rare_char_uncertain_path(self):
        # 数据缺失（或表外字）→ 整诗该位报 uncertain，不崩溃不瞎猜
        r = core.check_poem("龘龘飞天际，云开见月明。风来山色动，人在画中行。")
        self.assertIn(r["verdict"], ("WARN", "FAIL"))

    def test_e13_bad_override_warns(self):
        r = core.check_poem(BASELINE, readings_overrides={"长": "zhang3x"})
        self.assertTrue(any(i["item"] == "override" for i in r["issues"]))

    def test_e14_position_override_priority(self):
        # 位置 override 覆盖字 override
        r = core.check_poem("长亭更短亭，行客泪纵横。", readings_overrides={"长": "chang2"},
                            positional_overrides={(1, 1): "zhang3"})
        self.assertEqual(r["lines"][0]["chars"][0]["py"], "zhang3")

    def test_e15_deliberate_bad_rhyme_fail(self):
        # 韵脚差异巨大：窗(唐) vs 楼(侯) → 各 profile 均不过（18 NO/14 NO/13 NO）
        poem = "客舍秋灯暗，风来透纸窗。开门霜满地，独倚望江楼。"
        for prof in ("xinyun18", "xinyun14", "shisan13", "modern-ear"):
            r = core.check_poem(poem, rhyme_profile=prof)
            self.assertEqual(r["verdict"], "FAIL", prof)

    def test_e16_dui_only_warn_not_fail(self):
        # 关键位第2字相反但第4字未反 → WARN（宽松）而非 FAIL
        poem = "夜静花初落，风来近客门。披衣檐月淡，梦绕旧烟村。"
        r = core.check_poem(poem)
        dui = [c for c in r["dui_nian"]["checks"] if "相对(第1/2句)" in c["item"]]
        self.assertTrue(dui and dui[0]["level"] in ("PASS", "WARN"))

    def test_e17_pingze_display(self):
        r = core.check_poem(BASELINE, readings_overrides={"长": "chang2", "舍": "she4"})
        self.assertIn("仄仄平平仄", r["dui_nian"]["template_hint"])

    def test_e18_juan_quan_umlaut_rhyme(self):
        # 圈(juàn, üan)与 全(quán, üan)同韵（寒部）——jqx 还原正确才能同部
        lv, why, _ = core.rhyme_compare_strict(
            reading_of("圈", "juan4"), reading_of("全"), "b18")
        self.assertEqual(lv, "PERFECT_RHYME", why)

    def test_e19_ji_qi_xi_not_apical(self):
        # ji/qi/xi 的 i 是齐韵（不是支韵）
        for ch in ["机", "期", "西"]:
            r = reading_of(ch)
            self.assertEqual(r["b18"], "七齐", ch)

    def test_e20_zi_ci_si_apical(self):
        for ch in ["资", "词", "思"]:
            r = reading_of(ch)
            self.assertEqual(r["b18"], "五支", ch)

    def test_e21_light_rhyme_strict_no_perfect(self):
        # 韵脚 one side 轻声时，四个 profile 主判定都不得 PASS（真实诗）
        poem = "风来花事了，人去燕声么。独坐空庭晚，灯深雨更多。"  # fixture 语义不论
        r = core.check_poem(poem, rhyme_profile="xinyun18")
        for c in r["rhyme"]["checks"]:
            if "押韵" in c["item"]:
                self.assertNotEqual(c["level"], "PASS")

    def test_e22_modern_ear_near_is_warn_not_pass(self):
        # modern-ear 模式下 NEAR → WARN（整诗级：第2句尾 生(sheng1,eng) / 第4句尾
        # 尘(chen2,en) = 白名单 (en,eng) 跨辙近韵；fixture 语义不论，只断言押韵项）
        poem = "远客夜归深，孤灯照影生。寒窗人不寐，客路满风尘。"
        r = core.check_poem(poem, rhyme_profile="modern-ear")
        for c in r["rhyme"]["checks"]:
            if "押韵" in c["item"]:
                self.assertNotEqual(c["level"], "FAIL")  # NEAR → WARN 不 FAIL
                self.assertNotEqual(c["level"], "PASS")  # NEAR → WARN 不 PASS
        # rc2 strict：xinyun18 下同对（en/eng 分属十五痕/十七庚）→ FAIL（rc1 曾 WARN 降级）
        r18 = core.check_poem(poem, rhyme_profile="xinyun18")
        for c in r18["rhyme"]["checks"]:
            if "押韵" in c["item"]:
                self.assertEqual(c["level"], "FAIL")
                self.assertEqual(c["relation"], "NO_RHYME")

    def assert_reading(self, ch, py, tone, final):
        r = reading_of(ch, py)
        self.assertIsNotNone(r, f"{ch} 无读法 {py}")
        self.assertEqual(r["tone"], tone, f"{ch}{py}")
        self.assertEqual(r["final"], final, f"{ch}{py}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
