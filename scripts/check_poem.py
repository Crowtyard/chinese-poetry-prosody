# -*- coding: utf-8 -*-
"""check_poem.py —— 完整诗歌扫描（Skill 逻辑能力 E-J）。

用法：
    py scripts/check_poem.py --poem "客舍秋灯暗，风来透纸窗。开门霜满地，路向晓山长。"
    py scripts/check_poem.py --poem "…" --form jueju5
    py scripts/check_poem.py --poem "…" --reading 长=chang2        # 按字全局锁定读法
    py scripts/check_poem.py --poem "…" --reading 4:5=chang2       # 位置级锁定（第4句第5字）
    py scripts/check_poem.py --poem "…" --rhyme-profile xinyun14   # 切韵书判定（默认 xinyun18）
    py scripts/check_poem.py --poem "…" --json                     # JSON 输出（结构化）

override 优先级（V1.1 PHASE 8）：位置 override > 字 override > 字典默认
（dictionary_order，非词频排序）。

输出：字数 / 逐字拼音·声调·平仄 / 韵脚(第2、4句)押韵状态 / 联内相对 / 联间相粘 /
      异常位置 / 总评(PASS|WARN|FAIL)。确定性判定，无 LLM 成分。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prosody_core as core  # noqa: E402
import syllable_parser as sp  # noqa: E402


def parse_readings(items):
    """解析 --reading 列表 → (char_overrides, pos_overrides)。

    支持两种键：
      "长=chang2"       → 全诗按字
      "4:5=chang2"      → 第4句第5字（1-based，句间按标点切分后的句序）
    """
    char_ov, pos_ov = {}, {}
    for item in items:
        k, _, v = item.partition("=")
        k, v = k.strip(), v.strip()
        m = re.fullmatch(r"(\d+):(\d+)", k)
        if m:
            pos_ov[(int(m.group(1)), int(m.group(2)))] = v
        else:
            char_ov[k] = v
    return char_ov, pos_ov


def format_report(report) -> str:
    lines = []
    form = report.get("form_actual") or "?"
    exp = report.get("form_expected") or ""
    lines.append(f"输入：{report['input']}")
    lines.append(f"体式：{form}{('（期望 ' + exp + '）') if exp else ''}")
    lines.append(f"判定韵书：{core.RHYME_PROFILE_NAME.get(report.get('rhyme_profile', 'xinyun18'), '?')}"
                 f"（--rhyme-profile 可切换）")

    for i, ln in enumerate(report["lines"]):
        cells = []
        poly_hints = []
        for c in ln["chars"]:
            if c["uncertain"]:
                cells.append(f"{c['char']}[?]")
            else:
                cells.append(f"{c['char']}({sp.display_py(c['py'])},{c['pz']})")
                if c.get("alts"):
                    poly_hints.append(
                        f"{c['char']}: 默认{sp.display_py(c['py'])}"
                        f"（DEFAULT_SOURCE=dictionary_order），候选 {'/'.join(sp.display_py(a) for a in c['alts'])}")
        lines.append(f"  第{i+1}句 {ln['text']} ｜ 平仄串：{''.join(c.get('pz', '?') for c in ln['chars'])}")
        lines.append(f"        {('  '.join(cells))}")
        if poly_hints:
            lines.append(f"        多音提示：{'；'.join(poly_hints)}"
                         f"（按语义用 --reading 字=拼音 或 行:列=拼音 锁定）")

    rh = report.get("rhyme")
    if rh:
        rc = rh.get("rhyme_chars", {})
        for label in ("第2句", "第4句"):
            info = rc.get(label)
            if info:
                lines.append(f"  韵脚{label}：{info['char']}({sp.display_py(info['py'])}) {info['pz']} "
                             f"十八韵[{info['b18'] or '?'}] 十四韵[{info['b14'] or '?'}] "
                             f"十三辙[{info['z13'] or '?'}]")

    if report.get("dui_nian") and report["dui_nian"].get("template_hint"):
        lines.append(f"  {report['dui_nian']['template_hint']}")

    lines.append("检查明细：")
    seen = set()
    for entry in report["issues"]:
        key = (entry.get("level"), entry.get("item"), entry.get("detail"))
        if key in seen:
            continue
        seen.add(key)
        code = entry.get("code")
        tag = f" {code}" if code else ""
        lines.append(f"  [{entry.get('level')}{tag}] {entry.get('item')}：{entry.get('detail')}")
    if report["verdict"] == "PASS":
        lines.append("总评：PASS（确定性规则全部通过）")
    elif report["verdict"] == "WARN":
        lines.append("总评：WARN（无硬性违规，有提示项，见上）")
    else:
        lines.append("总评：FAIL（存在硬性违规，见上）")
    return "\n".join(lines)


def main(argv):
    ap = argparse.ArgumentParser(prog="check_poem")
    ap.add_argument("--poem", required=True)
    ap.add_argument("--form", choices=["jueju5", "jueju7", ""], default="")
    ap.add_argument("--reading", action="append", default=[], metavar="字=拼音 | 行:列=拼音")
    ap.add_argument("--rhyme-profile", choices=list(core.RHYME_PROFILES), default="xinyun18")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    char_ov, pos_ov = parse_readings(args.reading)
    report = core.check_poem(args.poem, readings_overrides=char_ov,
                             positional_overrides=pos_ov,
                             expect_form=args.form, rhyme_profile=args.rhyme_profile)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(format_report(report))
    return 0 if report["verdict"] == "PASS" else (1 if report["verdict"] == "WARN" else 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
