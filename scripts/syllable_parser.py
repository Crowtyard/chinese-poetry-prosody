# -*- coding: utf-8 -*-
"""
syllable_parser.py —— V1.1 新增：单个拼音音节的自足解析层

背景（V1 BLOCKER）：旧 build 分别调用 pinyin(Style.TONE3) 与
pinyin(Style.FINALS_TONE3)，再按下标配对两组 heteronym 列表；不同 Style 的
列表顺序/去重/长度可能不一致，导致出现 佛 bo2→tone4/final=i 一类错位数据。

V1.1 原则：**以完整拼音读音（如 "chang2"）为唯一主键**，一切字段
（tone / initial / final / pingze / 韵部）都由本层从该读音独立推导，
不依赖任何第二组 API 输出。

推导规则（确定性，全部基于汉语拼音拼写规范）：
1. 调号/声调：音节尾部数字 1-4；无数字 = 轻声 5。
2. 声母切分：zh/ch/sh 优先，其次单辅音 b p m f d t n l g k h j q x r z c s；
   y/w 不是声母（隔音字母），一律按零声母处理走还原表。
3. 韵母还原（拼写 → 音系完整韵母，含韵头）：
   - j/q/x 后的 u/uan/ue → ü/üan/üe（ju/qu/xu/juan/quan/xuan/jue/que/xue）；
     注意 j/q/x 后 iu/iong 不转（qiu→iou、jiong→iong）。
   - n/l 后的 v → ü（lv4→lü、nv3→nü）。
   - 有声母时的省写还原：ui→uei、un→uen、iu→iou（dui/chun/liu…）。
   - 零声母 y 系显式表：yi→i、yin→in、ying→ing、ya→ia、ye→ie、yao→iao、
     you→iou、yan→ian、yang→iang、yong→iong、yu→ü、yue→üe、yuan→üan、
     yun→ün。
   - 零声母 w 系显式表：wu→u、wo→uo、wa→ua、wai→uai、wei→uei、wan→uan、
     wen→uen、wang→uang、weng→ueng。
   - 纯辅音叹词音节（n/ng/m/hm/hng 等）无元音韵母 → final 记为空（UNCERTAIN）；
     yo（哟）、ê 系等不在标准韵母表的拼写同样无法映射 → 空（UNCERTAIN），
     不强行归入任何韵部。
   - 其余零声母 a/o/e/ai/ei/ao/ou/an/en/ang/eng/er 等直接就是韵母。
4. 舌尖元音：声母 zh/ch/sh/r/z/c/s 后韵母 i → i_apical（韵书“支”类），
   其余 i 为普通 i（“齐”类）。
5. 平仄：1/2=平、3/4=仄、5(轻声)=轻 —— 本项目现代简化规则。
6. 调号显示：按汉语拼音标调规则（a>o>e 优先；i/u 并列标在后：ui 标 i、
   iu 标 u；无 a/o/e 时标最后 i/u/ü）。
"""
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 2 字符声母（必须优先匹配）
INITIALS_DOUBLE = ("zh", "ch", "sh")
# 1 字符声母
INITIALS_SINGLE = "bpmfdtnlgkhjqxrzcs"
# 舌尖元音声母（z/c/s/zh/ch/sh/r 后的 i 是 -i）
APICAL_INITIALS = ("zh", "ch", "sh", "z", "c", "s", "r")
# 零声母 y 系还原表：拼写 -> 音系完整韵母
Y_FINAL_MAP = {
    "yi": "i", "yin": "in", "ying": "ing",
    "ya": "ia", "ye": "ie", "yao": "iao", "you": "iou",
    "yan": "ian", "yang": "iang", "yong": "iong",
    "yu": "ü", "yue": "üe", "yuan": "üan", "yun": "ün",
}
# 零声母 w 系还原表
W_FINAL_MAP = {
    "wu": "u", "wo": "uo", "wa": "ua", "wai": "uai",
    "wei": "uei", "wan": "uan", "wen": "uen",
    "wang": "uang", "weng": "ueng",
}
# 纯辅音（无元音）叹词音节
CONSONANTAL_SYLLABLES = {"n", "ng", "m", "hm", "hng", "m", "ń", "ň", "ǹ", "ḿ", "m̀"}

_TONE_DIGIT_RE = re.compile(r"[0-9]")

# 预组合带调字符（V1.1 PHASE 6：避免组合附加符在部分终端/编码下显示异常）
_TONE_MARKED = {
    1: {"a": "ā", "o": "ō", "e": "ē", "i": "ī", "u": "ū", "ü": "ǖ"},
    2: {"a": "á", "o": "ó", "e": "é", "i": "í", "u": "ú", "ü": "ǘ"},
    3: {"a": "ǎ", "o": "ǒ", "e": "ě", "i": "ǐ", "u": "ǔ", "ü": "ǚ"},
    4: {"a": "à", "o": "ò", "e": "è", "i": "ì", "u": "ù", "ü": "ǜ"},
}


def parse_tone_number(py: str) -> int:
    """音节尾部数字即声调（1-4）；无数字 = 轻声 5。"""
    if py and py[-1].isdigit():
        return int(py[-1])
    return 5


def strip_tone_number(py: str) -> str:
    """去掉尾部声调数字，返回无声调拼写。"""
    return py[:-1] if py and py[-1].isdigit() else py


def split_initial_final(syllable: str):
    """切分 (声母, 韵母拼写)。y/w 视作零声母（声母返回 ''）。"""
    s = syllable
    if s in CONSONANTAL_SYLLABLES:
        return "", ""
    for ini in INITIALS_DOUBLE:
        if s.startswith(ini) and len(s) > len(ini):
            return ini, s[len(ini):]
    if len(s) > 1 and s[0] in INITIALS_SINGLE:
        return s[0], s[1:]
    # 零声母（含 y/w 隔音开头）
    return "", s


def expand_final(initial: str, rest: str) -> str:
    """韵母拼写 → 音系完整韵母（含韵头）；无法还原返回 ''（=UNCERTAIN）。"""
    if not rest:
        return ""
    if initial in ("j", "q", "x"):
        # jqx 后 u 是 ü 的省写（u/uan/ue），但 iu/iong 等不转
        if rest.startswith("u") and len(rest) > 1 and rest[1] != "i":
            return expand_final(initial, "ü" + rest[1:])
        if rest == "u":
            return "ü"
    if rest.startswith("v"):
        return expand_final(initial, "ü" + rest[1:])
    if initial:
        # 省写还原（只发生在有声母时）
        if rest == "ui":
            return "uei"
        if rest == "un":
            return "uen"
        if rest == "iu":
            return "iou"
        return rest
    # 零声母：y/w 显式表
    if rest.startswith("y") and rest in Y_FINAL_MAP:
        return Y_FINAL_MAP[rest]
    if rest.startswith("w") and rest in W_FINAL_MAP:
        return W_FINAL_MAP[rest]
    if rest[0] in "aeoê":
        return rest
    return ""


def final_key(final: str, initial: str = "") -> str:
    """韵母键：舌尖元音 -i 归类为 i_apical（供韵部表查表）。"""
    if final == "i" and initial in APICAL_INITIALS:
        return "i_apical"
    return final


def classify_pingze(tone: int) -> str:
    """1/2 平、3/4 仄、5 轻（本项目现代简化规则）。"""
    return {1: "平", 2: "平", 3: "仄", 4: "仄", 5: "轻"}.get(tone, "?")


# --------------------------------------------------------------------------
# 调号显示（PHASE 6：严格实现标调规则，不再用“从右往左找第一个元音”）
# --------------------------------------------------------------------------

def apply_tone_mark(syllable_no_tone: str, tone: int) -> str:
    """给无声调音节加调号（tone 1-4；5=轻声不加）。

    规则：有 a 标 a；无 a 有 o 标 o（uo/ou 中 o 为韵腹候选顺序 a>o>e）；
    无 a/o 有 e 标 e；无 a/o/e 时 i/u/ü 并列标在后（ui 标 i、iu 标 u），
    其余标最后一个 i/u/ü。
    """
    if tone == 5 or not syllable_no_tone:
        return syllable_no_tone
    marked = _TONE_MARKED.get(tone, {})
    s = syllable_no_tone
    target = None
    if "a" in s:
        target = "a"
    elif "o" in s:
        target = "o"
    elif "e" in s:
        target = "e"
    else:
        # i/u/ü：并列取后（ui 标 i、iu 标 u）；否则取最后一个出现的
        idx = max(s.rfind("i"), s.rfind("u"), s.rfind("ü"))
        if idx >= 0:
            return s[:idx] + marked[s[idx]] + s[idx + 1:]
        return s
    idx = s.rfind(target)
    return s[:idx] + marked[target] + s[idx + 1:]


def display_py(py_tone3: str) -> str:
    """'chang2' -> 'cháng'；无数字(轻声)原样返回。"""
    if not py_tone3:
        return ""
    tone = parse_tone_number(py_tone3)
    body = strip_tone_number(py_tone3).replace("v", "ü")
    return apply_tone_mark(body, tone)


# --------------------------------------------------------------------------
# 完整单音节解析（build 与审计共用）
# --------------------------------------------------------------------------

def parse_reading(py_tone3: str, yunbu_lookup=None) -> dict:
    """从带声调数字的拼音读音推导全部字段。

    yunbu_lookup: 可选回调 final_key -> 韵部名 dict（b18/b14/z13 三个 profile 的
    合并查找器）；由调用方（prosody_core）注入韵部表，本层只做音系解析。
    返回字段：py/tone/final/final_key/pz/neutral/known(是否有元音韵母)
    """
    tone = parse_tone_number(py_tone3)
    body = strip_tone_number(py_tone3)
    initial, rest = split_initial_final(body)
    final = expand_final(initial, rest)
    fk = final_key(final, initial) if final else ""
    return {
        "py": py_tone3,
        "tone": tone,
        "initial": initial,
        "final": final,
        "final_key": fk,
        "pz": classify_pingze(tone),
        "neutral": tone == 5,
        "known_final": bool(final),
    }
