# -*- coding: utf-8 -*-
"""check_char.py —— 单字音韵查询（Skill 逻辑能力 A/B/C/D）。

用法：
    py scripts/check_char.py 城
    py scripts/check_char.py 长          # 显示全部候选读音 + 默认读音来源
输出：拼音(带调号)/声调/平仄/韵母/韵部（十八韵、十四韵、十三辙）+ 候选读音。

V1.1 变化（PHASE 6/7）：
  - 调号显示改由 syllable_parser.apply_tone_mark 按汉语拼音标调规则生成
    （有 a 标 a / 无 a 有 o 标 o / 无 a,o 有 e 标 e / i,u,ü 并列标在后），
    不再使用“从右往左找第一个元音”的错误算法（海→hǎi、小→xiǎo）。
  - 默认读音明确标注 DEFAULT_SOURCE = dictionary_order（底层字典返回的第一
    读音，非词频/通用度排序），并列出全部候选供人工或 --reading 覆盖。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prosody_core as core  # noqa: E402
import syllable_parser as sp  # noqa: E402


def main(argv):
    if len(argv) < 1:
        print("用法: py check_char.py <汉字>")
        return 2
    ch = argv[0]
    if len(ch) != 1:
        print("只支持单字查询")
        return 2
    all_r = core.lookup(ch)
    if not all_r:
        print(f"「{ch}」：当前数据表中无该字读音数据。")
        print("当前版本不能通过 --reading 为完全未知字符新增读音，因此返回 UNCERTAIN。")
        return 1
    print(f"字：{ch}")
    tone_desc = {1: "阴平(一声)", 2: "阳平(二声)", 3: "上声(三声)", 4: "去声(四声)", 5: "轻声"}
    for i, r in enumerate(all_r):
        tag = "默认" if i == 0 else f"候选{i+1}"
        print(f"  [{tag}] {sp.display_py(r['py'])} ｜ 声调 {r['tone']}({tone_desc[r['tone']]}) ｜ "
              f"平仄 {r['pz']} ｜ 韵母 {r['final']} ｜ "
              f"十八韵 {r['b18'] or '?'} ｜ 十四韵 {r['b14'] or '?'} ｜ 十三辙 {r['z13'] or '?'}")
    if len(all_r) > 1:
        print(f"多音字提示：默认读音 {sp.display_py(all_r[0]['py'])} 的 "
              f"DEFAULT_SOURCE = dictionary_order（底层字典返回的第一读音，"
              f"不等于严格词频最优）。")
        print(f"候选读音：{' / '.join(sp.display_py(a['py']) for a in all_r)}")
        print("诗中语义明确时，建议在整诗检查用 --reading 字=拼音 或 行:列=拼音 锁定。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
