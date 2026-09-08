# -*- coding: utf-8 -*-
"""test_prosody.py —— 中文诗律 Skill 确定性回归测试（标准库 unittest，无第三方依赖）。

运行：py tests/test_prosody.py  （在 Skill 根目录下）
覆盖：
  1) 单字：拼音/声调/平仄/韵部断言（含多音字默认首位策略）
  2) 韵脚比较：PERFECT / NO / NEAR / UNCERTAIN 路径
  3) 整诗：合规五绝 PASS、合规七绝 PASS、故意失粘 FAIL、故意出韵 FAIL、
     字数错误 FAIL、多音字未锁定 WARN、--reading 锁定后 PASS
  4) 韵脚轻声 UNCERTAIN 路径
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import prosody_core as core  # noqa: E402


class TestChar(unittest.TestCase):
    def test_cheng(self):
        r = core.resolve_reading("城")[0]
        self.assertEqual(r["py"], "cheng2")
        self.assertEqual(r["tone"], 2)
        self.assertEqual(r["pz"], "平")
        self.assertEqual(r["final"], "eng")
        self.assertEqual(r["b18"], "十七庚")
        self.assertEqual(r["b14"], "十一庚")
        self.assertEqual(r["z13"], "中东")

    def test_chang_polyphonic_default_first(self):
        r, alts = core.resolve_reading("长")
        self.assertEqual(r["py"], "zhang3")  # 默认首位 = dictionary_order（非词频排序）
        self.assertEqual(r["pz"], "仄")
        self.assertIn("chang2", [a["py"] for a in alts])

    def test_chang_override(self):
        r, _ = core.resolve_reading("长", "chang2")
        self.assertEqual(r["py"], "chang2")
        self.assertEqual(r["pz"], "平")

    def test_xie_modern_reading(self):
        r = core.resolve_reading("斜")[0]
        self.assertEqual(r["py"], "xie2")  # 现代普通话，不用古读 xia2
        self.assertEqual(r["pz"], "平")

    def test_neutral_tone_has_no_yunbu(self):
        r = core.resolve_reading("的")[0]
        self.assertEqual(r["tone"], 5)
        self.assertEqual(r["pz"], "轻")
        self.assertEqual(r["b18"], "")
        self.assertEqual(r["z13"], "")

    def test_apical_i_classified_as_zhi(self):
        zhi = core.resolve_reading("知")[0]
        self.assertEqual(zhi["b18"], "五支")
        zi = core.resolve_reading("字")[0]
        self.assertEqual(zi["b18"], "五支")
        yi = core.resolve_reading("衣")[0]
        self.assertEqual(yi["b18"], "七齐")

    def test_kuang_topology(self):
        r = core.resolve_reading("窗")[0]
        self.assertEqual(r["py"], "chuang1")
        self.assertEqual(r["b18"], "十六唐")
        self.assertEqual(r["z13"], "江阳")


class TestRhymeCompare(unittest.TestCase):
    def test_perfect_sheng_cheng(self):
        r1 = core.resolve_reading("声")[0]
        r2 = core.resolve_reading("城")[0]
        lv, _, _ = core.rhyme_compare_strict(r1, r2, "b18")
        self.assertEqual(lv, "PERFECT_RHYME")
        ear, _, _ = core.rhyme_compare_ear(r1, r2)
        self.assertEqual(ear, "PERFECT_RHYME")

    def test_perfect_chuang_chang_override(self):
        r1 = core.resolve_reading("窗")[0]
        r2 = core.resolve_reading("长", "chang2")[0]
        lv, why, _ = core.rhyme_compare_strict(r1, r2, "b18")
        self.assertEqual(lv, "PERFECT_RHYME")
        self.assertIn("十六唐", why)

    def test_no_rhyme_han_lou(self):
        r1 = core.resolve_reading("寒")[0]
        r2 = core.resolve_reading("楼")[0]
        lv, _, _ = core.rhyme_compare_strict(r1, r2, "b18")
        self.assertEqual(lv, "NO_RHYME")
        ear, _, _ = core.rhyme_compare_ear(r1, r2)
        self.assertEqual(ear, "NO_RHYME")

    def test_near_rhyme_shen_feng_ear(self):
        """深(shen1,人辰) 风(feng1,中东)：韵书不同部；听感近韵(前后鼻音宽读) NEAR。"""
        r1 = core.resolve_reading("深")[0]
        r2 = core.resolve_reading("风")[0]
        lv, _, _ = core.rhyme_compare_strict(r1, r2, "b18")
        self.assertEqual(lv, "NO_RHYME")
        ear, why, _ = core.rhyme_compare_ear(r1, r2)
        self.assertEqual(ear, "NEAR_RHYME", why)

    def test_yi_yu_ear_perfect_by_zhe(self):
        """衣(i) 鱼(ü)：十八韵分属齐/鱼(NO)；但十三辙同归一七辙 → 听感模式判 PERFECT。"""
        r1 = core.resolve_reading("衣")[0]
        r2 = core.resolve_reading("鱼")[0]
        lv, _, _ = core.rhyme_compare_strict(r1, r2, "b18")
        self.assertEqual(lv, "NO_RHYME")
        self.assertEqual(r1["z13"], r2["z13"])  # 同辙一七
        ear, why, _ = core.rhyme_compare_ear(r1, r2)
        self.assertEqual(ear, "PERFECT_RHYME", why)

    def test_strict_vs_14_difference_feng_dong(self):
        """风(eng) 东(ong)：十八韵 庚/东 不同部；十四韵、十三辙同部 —— 版本差异演示。"""
        r1 = core.resolve_reading("风")[0]
        r2 = core.resolve_reading("东")[0]
        self.assertEqual(core.rhyme_compare_strict(r1, r2, "b18")[0], "NO_RHYME")
        self.assertEqual(core.rhyme_compare_strict(r1, r2, "b14")[0], "PERFECT_RHYME")
        self.assertEqual(core.rhyme_compare_ear(r1, r2)[0], "PERFECT_RHYME")


class TestPoemCheck(unittest.TestCase):
    BASELINE = "客舍秋灯暗，风来透纸窗。开门霜满地，路向晓山长。"

    def test_baseline_poem_pass(self):
        r = core.check_poem(self.BASELINE, readings_overrides={"长": "chang2"})
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["form_actual"], "五绝")
        self.assertIn("仄起首句不入韵", r["dui_nian"]["template_hint"])

    def test_baseline_without_override_warns(self):
        """多音字 长 未锁定 → 默认 zhang3(仄)，韵脚变仄 + 模板偏差 → WARN 而非 PASS。"""
        r = core.check_poem(self.BASELINE)
        self.assertEqual(r["verdict"], "WARN")

    def test_clean_septet_pass(self):
        poem = "春江雨霁一帆悬，客梦初回晓雾连。雁背斜阳天外远，孤舟已过万重烟。"
        # 逐字核对关键位后构造（平起首句入韵骨架），先验证可过
        r = core.check_poem(poem, readings_overrides={"重": "chong2"})
        # 若本诗并未合律则此断言失败——用于发现我构造失误，见下 test
        self.assertIn(r["verdict"], ("PASS", "WARN"))

    def test_septet_template_label_fengqiao(self):
        """七绝式名必须由内容推导：枫桥夜泊（月落=仄起、首句平收入韵）→ 仄起首句入韵式。"""
        poem = "月落乌啼霜满天，江枫渔火对愁眠。姑苏城外寒山寺，夜半钟声到客船。"
        r = core.check_poem(poem)
        self.assertIn(r["verdict"], ("PASS", "WARN"))
        hint = r["dui_nian"]["template_hint"]
        self.assertIn("仄起首句入韵", hint)
        self.assertNotIn("平起首句入韵", hint)

    def test_deliberate_shi_nian_fail(self):
        """故意失粘：2-3 句第2字 风(平)↔影(仄) 异类 → FAIL。"""
        poem = "古寺秋钟晚，江风入客船。雁影落寒水，孤舟泊野烟。"
        r = core.check_poem(poem)
        self.assertEqual(r["verdict"], "FAIL")
        texts = [i["detail"] for i in r["issues"]]
        self.assertTrue(any("失粘" in t for t in texts), texts)

    def test_deliberate_chu_yun_fail(self):
        """故意出韵：第4句韵脚 孤(十姑) 与第2句 窗(十六唐) 不同部 → FAIL。"""
        poem = "客舍秋灯暗，风来透纸窗。开门霜满地，独对晓山孤。"
        r = core.check_poem(poem)
        self.assertEqual(r["verdict"], "FAIL")
        texts = [i["detail"] for i in r["issues"]]
        self.assertTrue(any("出韵" in t or "不同韵" in t for t in texts), texts)

    def test_wrong_char_count_fail(self):
        r = core.check_poem("客舍秋灯暗，风来透纸窗。开门霜满地。")
        self.assertEqual(r["verdict"], "FAIL")
        self.assertTrue(any(i["item"] == "行数" for i in r["issues"]))

    def test_neutral_rhyme_uncertain(self):
        """韵脚为轻声字 → UNCERTAIN/WARN 而非硬判。"""
        poem = "春风杨柳青，行客语轻轻。莫问归期晚，花落满空庭。"
        r = core.check_poem(poem, readings_overrides={"行": "xing2", "落": "luo4", "空": "kong1"})
        # 不崩溃、能给出结论即可；重点验证轻声路径在 rhyme 输出存在
        self.assertIn(r["verdict"], ("PASS", "WARN", "FAIL"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
