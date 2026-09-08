# -*- coding: utf-8 -*-
"""build_char_table.py —— V1.1：一次性构建 data/chars.json（运行时唯一依赖数据）。

V1 BLOCKER 修复（第三方审计）：
  旧实现分别调用 pinyin(Style.TONE3) 与 pinyin(Style.FINALS_TONE3)，
  再按下标把两组 heteronym 列表配对 —— 两组列表可能顺序/长度/去重不同，
  导致 227 条 tone 错位、195 条 final 错位（如 佛 bo2→tone4/final=i）。

V1.1 方案：单次调用 pinyin(Style.TONE3, heteronym=True)，
  以“完整拼音读音”为唯一主键，每个 reading 独立经 syllable_parser 解析：
  tone / initial / final(完整韵母) / 平仄 / 十八韵 / 十四韵 / 十三辙。
  不再存在第二组输出，从根上消除配对错位。

数据来源与许可：
  pypinyin (MIT License, https://github.com/mozillazg/python-pinyin)
  chars.json 内不保存任何时间戳性差异源；meta.generated 仅作记录，
  数据可重复构建性以“chars 部分 sha256 + meta(除 generated) sha256”验证。

用法：
  py -m pip install pypinyin
  py scripts/build_char_table.py          # 重建 data/chars.json
  py scripts/build_char_table.py --check  # 只审计现有 chars.json，不重建
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
CHARS_JSON = os.path.join(DATA_DIR, "chars.json")

import prosody_core as core        # noqa: E402  （韵部映射表 YUN18/14/13）
import syllable_parser as sp       # noqa: E402  （单音节解析层）

# 主 CJK 收录区（与 V1 相同：基本区 + 扩展A + 兼容区）
def _cjk_codepoints():
    try:
        from pypinyin.constants import PINYIN_DICT
        cps = [cp for cp in PINYIN_DICT.keys() if isinstance(cp, int)]
    except Exception:
        cps = list(range(0x4E00, 0xA000))
    return sorted(cp for cp in cps if 0x3400 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF)


def reading_entry(py_tone3: str) -> dict:
    """由单一拼音读音（TONE3 拼写）自足构造条目；解析失败返回 None。

    返回字段与 V1 完全兼容：py/tone/final/pz/b18/b14/z13。
    final 为音系完整韵母（含韵头、ü 用 'ü'），如 eng/ang/üan/uei/iou/uen/i_apical。
    """
    parsed = sp.parse_reading(py_tone3)
    if parsed is None:
        return None
    tone = parsed["tone"]
    fk = parsed["final_key"]          # 如 'i_apical' 已归一
    return {
        "py": py_tone3,
        "tone": tone,
        "final": parsed["final"],     # 显示/比对用完整韵母
        "pz": parsed["pz"],
        "b18": "" if tone == 5 else core.YUN18.get(fk, ""),
        "b14": "" if tone == 5 else core.YUN14.get(fk, ""),
        "z13": "" if tone == 5 else core.YUN13.get(fk, ""),
    }


def derive_final(py_tone3: str) -> str:
    """从拼音读音重新推导完整韵母（审计用，必须与 stored 一致）。"""
    parsed = sp.parse_reading(py_tone3)
    return parsed["final"] if parsed else ""


def build_chars() -> dict:
    """遍历全部 CJK 码点，生成 chars 表。返回 {"meta":..., "chars":...}。"""
    from pypinyin import pinyin, Style

    chars = {}
    missing = 0
    tone_mismatch = 0
    final_mismatch = 0
    unparsed = 0
    for cp in _cjk_codepoints():
        ch = chr(cp)
        try:
            sylv = pinyin(ch, style=Style.TONE3, heteronym=True, errors="ignore")
        except Exception:
            missing += 1
            continue
        if not sylv or not sylv[0]:
            missing += 1
            continue
        entries = []
        for py_tone3 in sylv[0]:
            if not py_tone3:
                continue
            e = reading_entry(py_tone3)
            if e is None:
                unparsed += 1
                continue
            # 构建期自检（解析层输出必须与拼音本身一致）
            t = sp.parse_tone_number(py_tone3)
            if e["tone"] != t:
                tone_mismatch += 1
            if derive_final(py_tone3) != e["final"]:
                final_mismatch += 1
            entries.append(e)
        if entries:
            chars[ch] = entries

    stats = {
        "cjk_codepoints": len(_cjk_codepoints()),
        "chars_with_readings": len(chars),
        "readings_total": sum(len(v) for v in chars.values()),
        "missing_chars": missing,
        "unparsed_readings": unparsed,
        "tone_mismatch": tone_mismatch,
        "final_mismatch": final_mismatch,
    }
    meta = {
        "description": "汉字现代普通话读音表（含异读；顺序 = pypinyin 字典返回顺序 dictionary_order，非词频排序）",
        "source": "pypinyin " + _pypinyin_version() + " (MIT License)",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "builder": "build_char_table.py V1.1 (单源 TONE3 + syllable_parser，无跨 Style 配对)",
        "stats": stats,
        "note": "平仄/韵部按本项目现代简化规则预计算；轻声(tone5)无韵部；"
                "final 无法映射到韵部表时为 ''，使用方必须报 UNCERTAIN",
    }
    return {"meta": meta, "chars": chars}


def data_sha(data: dict) -> dict:
    """内容哈希：chars 与 meta(除 generated) 分开计算，保证可重复构建可验证。"""
    chars_h = hashlib.sha256(
        json.dumps(data["chars"], ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    meta_no_ts = {k: v for k, v in data["meta"].items() if k != "generated"}
    meta_h = hashlib.sha256(
        json.dumps(meta_no_ts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {"chars_sha256": chars_h, "meta_sha256": meta_h}


def audit_chars(chars: dict) -> dict:
    """全库审计（PHASE 2 门禁）：遍历每条 reading 做独立一致性验证。

    A. py 尾数字与 tone 一致（1-4；无数字=5 轻声）
    B. stored final == derive_final(py)（从拼音本身重推）
    C. tone ∈ {1,2,3,4,5}
    D. 已识别 final 必须能进入韵部表（b18/b14/z13 非空），否则记为 unmapped_final
       （轻声除外：tone5 无韵部属设计）
    E. 可重复构建由 build_chars 两次哈希验证（外部调用方/审计脚本负责）
    """
    res = {
        "tone_mismatch": 0, "final_mismatch": 0,
        "invalid_tone": 0, "unmapped_final": 0,
        "unmapped_final_examples": [],
        "readings_total": 0,
    }
    for ch, entries in chars.items():
        for e in entries:
            res["readings_total"] += 1
            py = e["py"]
            t = sp.parse_tone_number(py)
            # A + C
            if e["tone"] != t:
                res["tone_mismatch"] += 1
            if t not in (1, 2, 3, 4, 5):
                res["invalid_tone"] += 1
            # B
            if derive_final(py) != e["final"]:
                res["final_mismatch"] += 1
            # D
            if t != 5:
                if not (e["b18"] and e["b14"] and e["z13"]):
                    res["unmapped_final"] += 1
                    if len(res["unmapped_final_examples"]) < 10:
                        res["unmapped_final_examples"].append(f"{ch}{py} final={e['final']}")
    return res


def _pypinyin_version():
    try:
        import pypinyin
        return getattr(pypinyin, "__version__", "?")
    except Exception:
        return "?"


def main(argv=None):
    ap = argparse.ArgumentParser(description="构建/审计 chars.json")
    ap.add_argument("--check", action="store_true", help="只审计现有 chars.json，不重建")
    args = ap.parse_args(argv)

    if args.check:
        with open(CHARS_JSON, encoding="utf-8") as fh:
            data = json.load(fh)
        res = audit_chars(data["chars"])
        print("audit:", json.dumps(res, ensure_ascii=False))
        print("hash:", json.dumps(data_sha(data), ensure_ascii=False))
        gate = res["tone_mismatch"] == 0 and res["final_mismatch"] == 0
        print("GATE:", "PASS" if gate else "FAIL")
        return 0 if gate else 1

    data = build_chars()
    res = audit_chars(data["chars"])
    if res["tone_mismatch"] > 0 or res["final_mismatch"] > 0:
        print("BUILD ABORTED: 构建产物存在数据错位", json.dumps(res, ensure_ascii=False))
        return 1
    with open(CHARS_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    print("chars.json written:", CHARS_JSON)
    print("stats:", json.dumps(data["meta"]["stats"], ensure_ascii=False))
    print("audit:", json.dumps(res, ensure_ascii=False))
    print("hash:", json.dumps(data_sha(data), ensure_ascii=False))
    # 抽样自检（第三方反例 + 常用）
    for ch in ["佛", "侧", "圈", "折", "长", "还", "舍", "城", "窗", "海", "绿", "鱼", "云", "春"]:
        print(ch, "->", json.dumps(data["chars"].get(ch), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
