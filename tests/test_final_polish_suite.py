# -*- coding: utf-8 -*-
"""test_final_polish_suite.py —— v1.1 Final Polish 专项测试。

运行：py tests/test_final_polish_suite.py（skill 根目录）
覆盖：
  1. check_char 已知字 → exit 0
  2. check_char 未知字 → 输出 UNCERTAIN 且 exit 1（CLI contract）
  3. xinyun18 examples：河 ∈ 三歌（final=e）
  4. xinyun18 examples：夜 ∈ 四皆（final=ie）
  5. references/scripts/SKILL.md 无过时"轻声默认按平"等表述
  6. unknown char 文案不声称 "--reading 可新增未知字读音"
  7. GPL 措辞：无"传染性/不允许复制"式扩张表述
  8. unmapped 描述：无"全部是无元音叹词"式不准确表述
"""
import io
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOC_FILES = [
    os.path.join(ROOT, "SKILL.md"),
] + [os.path.join(ROOT, "references", f) for f in os.listdir(os.path.join(ROOT, "references"))]
PY_FILES = [os.path.join(ROOT, "scripts", f) for f in os.listdir(os.path.join(ROOT, "scripts"))
            if f.endswith(".py")]


def run_cli(args, cwd=ROOT):
    proc = subprocess.run([sys.executable] + args, cwd=cwd,
                          capture_output=True, encoding="utf-8")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class TestCheckCharExitCode(unittest.TestCase):
    def test_known_char_cheng_exit0(self):
        code, out = run_cli(["scripts/check_char.py", "城"])
        self.assertEqual(code, 0)
        self.assertIn("城", out)

    def test_polyphonic_char_chang_exit0(self):
        code, out = run_cli(["scripts/check_char.py", "长"])
        self.assertEqual(code, 0)
        self.assertIn("dictionary_order", out)

    def test_unknown_char_uncertain_exit1(self):
        # U+20BB7（𠮷）在数据表覆盖区外 → UNCERTAIN 且 exit 1（CLI contract：1=WARN/UNCERTAIN）
        code, out = run_cli(["scripts/check_char.py", "\U00020BB7"])
        self.assertEqual(code, 1)
        self.assertIn("UNCERTAIN", out)
        self.assertNotIn("可用 --reading 提供读音", out)
        # 文案必须说明：不能通过 --reading 为未知字新增读音
        self.assertIn("不能通过 --reading", out)


class TestXinyun18Examples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with io.open(os.path.join(DATA, "xinyun18.json"), encoding="utf-8") as f:
            cls.data = json.load(f)
        with io.open(os.path.join(DATA, "chars.json"), encoding="utf-8") as f:
            cls.chars = json.load(f)["chars"]
        cls.by_no = {g["no"]: g for g in cls.data["groups"]}

    def test_he_in_sange(self):
        # 河 hé final=e → 三歌（曾在二波，错误）
        self.assertIn("河", self.by_no["三歌"]["examples"])
        self.assertNotIn("河", self.by_no["二波"]["examples"])

    def test_ye_in_sijie(self):
        # 夜 yè final=ie → 四皆（曾在三歌，错误）
        self.assertIn("夜", self.by_no["四皆"]["examples"])
        self.assertNotIn("夜", self.by_no["三歌"]["examples"])

    def test_examples_match_finals(self):
        # 每个 examples 字的 final 必须落在该组 finals 内（展示数据自洽）
        for g in self.data["groups"]:
            finals = set(g["finals"])
            for ch in g["examples"]:
                entry = self.chars.get(ch)
                self.assertIsNotNone(entry, f"{g['no']} 例字 {ch} 无读音数据")
                r = entry[0]
                # 例字必须落在该组的韵部（b18 为最终查表结果；final 显示层
                # 对 i_apical 记 'i'，因此直接断言韵部归属最准确）
                self.assertEqual(r["b18"], g["no"],
                                 f"{g['no']} 例字 {ch} b18={r['b18']}")


class TestDocHygiene(unittest.TestCase):
    def scan(self, patterns, paths):
        hits = []
        for p in paths:
            with io.open(p, encoding="utf-8") as f:
                text = f.read()
            for pat in patterns:
                if pat in text:
                    hits.append((os.path.basename(p), pat))
        return hits

    def test_no_stale_neutral_wording(self):
        hits = self.scan(["轻声默认按平", "轻声按平", "默认平声",
                          "轻声.*按“平”宽松", "按“平”宽松处理"], DOC_FILES + PY_FILES)
        self.assertEqual(hits, [], f"过时轻声表述残留: {hits}")

    def test_no_gpl_overreach_wording(self):
        hits = self.scan(["GPL-3.0 传染性", "GPL 不允许复制", "GPL 代码不能使用",
                          "不允许复制不兼容许可证"], DOC_FILES)
        self.assertEqual(hits, [], f"GPL 扩张表述残留: {hits}")
        # 准确表述在场（sources.md）
        with io.open(os.path.join(ROOT, "references", "sources.md"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("为避免在本项目的分发与衍生实现中引入 GPL-3.0 所附带的许可义务", src)
        self.assertIn("未复制其代码或数据", src)

    def test_no_inaccurate_unmapped_wording(self):
        hits = self.scan(["全部是无元音叹词", "32 条全部为无元音", "全为无元音"], DOC_FILES + PY_FILES)
        self.assertEqual(hits, [], f"unmapped 不准确表述残留: {hits}")

    def test_dictionary_order_wording_present(self):
        # 正式表述统一为 DEFAULT_SOURCE = dictionary_order
        # 文档层：凡描述默认读音性质处必须带“非词频”否定说明（scripts 的
        # CLI 提示行仅陈述 DEFAULT_SOURCE 来源，无词频声称，不在此列）
        for p in DOC_FILES:
            with io.open(p, encoding="utf-8") as f:
                text = f.read()
            if "dictionary_order" in text:
                self.assertTrue(("非词频" in text) or ("词频" in text),
                                f"{p} 含 dictionary_order 却无词频否定说明")
        with io.open(os.path.join(ROOT, "references", "pingze.md"), encoding="utf-8") as f:
            self.assertIn("DEFAULT_SOURCE = dictionary_order", f.read())

    def test_references_only_no_local_abs_path_in_readme_targets(self):
        # SKILL.md 与 references 中不得出现本机用户目录绝对路径（发布卫生）
        hits = []
        for p in DOC_FILES:
            with io.open(p, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if "C:\\Users" in line or "/c/Users/" in line:
                        hits.append((os.path.basename(p), i))
        self.assertEqual(hits, [], f"发布文档含本机绝对路径: {hits}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
