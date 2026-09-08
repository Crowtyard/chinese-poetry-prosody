# -*- coding: utf-8 -*-
"""check_rhyme.py —— 韵脚比较（Skill 逻辑能力 D/I）。

用法：
    py scripts/check_rhyme.py 声 城
    py scripts/check_rhyme.py 窗 长 --reading 长=chang2      # 多音字锁定读法
    py scripts/check_rhyme.py 风 东 --profile xinyun14       # 按十四韵判定
    py scripts/check_rhyme.py 风 东 --profile modern-ear     # 听感模式判定
输出：
    押韵级别（PERFECT_RHYME / NEAR_RHYME / NO_RHYME / UNCERTAIN）
    依据（十八韵 / 十四韵 / 十三辙）与听感辅助说明。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prosody_core as core  # noqa: E402
import syllable_parser as sp  # noqa: E402


def parse_args(args):
    over = {}
    profile = "xinyun18"
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--reading" and i + 1 < len(args):
            k, _, v = args[i + 1].partition("=")
            over[k.strip()] = v.strip()
            i += 2
        elif a == "--profile" and i + 1 < len(args):
            profile = args[i + 1]
            i += 2
        else:
            rest.append(a)
            i += 1
    if profile not in core.RHYME_PROFILES:
        print(f"--profile 必须是 {'/'.join(core.RHYME_PROFILES)}")
        sys.exit(2)
    return rest, over, profile


def main(argv):
    rest, overrides, profile = parse_args(argv)
    if len(rest) < 2:
        print("用法: py check_rhyme.py <字1> <字2> [--reading 字=拼音] [--profile xinyun18|xinyun14|shisan13|modern-ear]")
        return 2
    c1, c2 = rest[0], rest[1]
    for ch in (c1, c2):
        if len(ch) != 1:
            print("只支持单字比较")
            return 2
    r1, all1 = core.resolve_reading(c1, overrides.get(c1, ""))
    r2, all2 = core.resolve_reading(c2, overrides.get(c2, ""))
    if r1 is None or r2 is None:
        for ch, r, allr in ((c1, r1, all1), (c2, r2, all2)):
            if r is None:
                if not allr:
                    print(f"「{ch}」无读音数据 → UNCERTAIN")
                else:
                    print(f"「{ch}」的 --reading 读法不在数据表中；"
                          f"可选：{', '.join(sp.display_py(a['py']) for a in allr)}")
        return 1
    if len(all1) > 1:
        print(f"提示：「{c1}」为多音字，默认取 {sp.display_py(r1['py'])}"
              f"（DEFAULT_SOURCE=dictionary_order）；候选：{'/'.join(sp.display_py(a['py']) for a in all1)}")
    if len(all2) > 1:
        print(f"提示：「{c2}」为多音字，默认取 {sp.display_py(r2['py'])}"
              f"（DEFAULT_SOURCE=dictionary_order）；候选：{'/'.join(sp.display_py(a['py']) for a in all2)}")

    print(f"比较：{c1}({sp.display_py(r1['py'])}, 韵母{r1['final']}) ↔ "
          f"{c2}({sp.display_py(r2['py'])}, 韵母{r2['final']})")
    for label, key in (("中华新韵十八韵", "b18"), ("中华新韵十四韵", "b14"), ("十三辙", "z13")):
        lv, why, _ = core.rhyme_compare_strict(r1, r2, key)
        print(f"  [{label}] {lv} — {why}")
    ear_lv, ear_why, _ = core.rhyme_compare_ear(r1, r2)
    print(f"  [MODERN_EAR 听感] {ear_lv} — {ear_why}")
    # 主判定行（跟随 --profile；结构化 status/relation，message 仅展示）
    j = core.judge_rhyme_pair(
        {"b18": r1["b18"], "b14": r1["b14"], "z13": r1["z13"], "final": r1["final"]},
        {"b18": r2["b18"], "b14": r2["b14"], "z13": r2["z13"], "final": r2["final"]},
        profile,
    )
    print(f"  [主判定 profile={profile}] status={j['status']} relation={j['relation']} — {j['message']}")
    return 0 if j["status"] == "PASS" else (1 if j["status"] == "WARN" else 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
