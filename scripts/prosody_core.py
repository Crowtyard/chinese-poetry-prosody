# -*- coding: utf-8 -*-
"""
prosody_core.py —— chinese-poetry-prosody 确定性规则引擎（共享核心）

设计原则（见 SKILL.md）：
  1. 底层规则全部由数据+程序确定性计算，LLM 只负责解释结果与创作修改。
  2. 拼音/声调数据来自 data/chars.json（由 scripts/build_char_table.py 依据
     pypinyin(MIT) 单字读音表构建，含异读；默认读音 = 字典首位（dictionary_order，非词频排序））。
  3. 韵部映射表见下方 F18/F14/Z13；映射键中 'i_apical' 表示 z/c/s/zh/ch/sh/r
     后的舌尖元音 -i（pypinyin 对 zhī/zī 返回韵母 'i'，需按声母区分支/齐）。
  4. 平仄：1/2 声=平，3/4 声=仄，轻声(5)=轻（默认按“平”参与判断并在关键位置
     WARN；可用 --reading 覆盖为实读）。这是本项目现代简化规则，不是近体诗学
     的完整规则（传统规则含入声字体系，见 references/）。
  5. 无法可靠判断 → 返回 UNCERTAIN / null，禁止猜测。
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CHARS_JSON = os.path.join(DATA_DIR, "chars.json")

# --------------------------------------------------------------------------
# 韵部映射（final 键 → 韵部名）
# final 键：a ia ua o uo e ie üe i u ü er ei uei ai uai ou iou ao iao an ian
#           uan üan en in uen ün ang iang uang eng ing ueng ong iong i_apical
# 来源与说明见 references/modern_rhyme.md 与 references/sources.md。
# --------------------------------------------------------------------------

F18 = {  # 中华新韵·十八韵（1941 公布；分部与《诗韵新编》一致）
    "一麻": ["a", "ia", "ua"],
    "二波": ["o", "uo"],
    "三歌": ["e"],
    "四皆": ["ie", "üe"],
    "五支": ["i_apical"],
    "六儿": ["er"],
    "七齐": ["i"],
    "八微": ["ei", "uei"],
    "九开": ["ai", "uai"],
    "十姑": ["u"],
    "十一鱼": ["ü"],
    "十二侯": ["ou", "iou"],
    "十三豪": ["ao", "iao"],
    "十四寒": ["an", "ian", "uan", "üan"],
    "十五痕": ["en", "in", "uen", "ün"],
    "十六唐": ["ang", "iang", "uang"],
    "十七庚": ["eng", "ing", "ueng"],
    "十八东": ["ong", "iong"],
}

F14 = {  # 中华新韵·十四韵（中华诗词学会 2005 试行简表：波/歌合并、齐/儿/鱼合并、庚/东合并）
    "一麻": ["a", "ia", "ua"],
    "二波": ["o", "e", "uo"],
    "三皆": ["ie", "üe"],
    "四开": ["ai", "uai"],
    "五微": ["ei", "uei"],
    "六豪": ["ao", "iao"],
    "七尤": ["ou", "iou"],
    "八寒": ["an", "ian", "uan", "üan"],
    "九文": ["en", "in", "uen", "ün"],
    "十唐": ["ang", "iang", "uang"],
    "十一庚": ["eng", "ing", "ong", "iong", "ueng"],
    "十二齐": ["i", "er", "ü"],
    "十三支": ["i_apical"],
    "十四姑": ["u"],
}

Z13 = {  # 十三辙（北方曲艺/戏曲唱词通押辙口，现代听感押韵的通行参考）
    "发花": ["a", "ia", "ua"],
    "梭波": ["o", "e", "uo"],
    "乜斜": ["ie", "üe"],
    "一七": ["i", "i_apical", "ü", "er"],
    "姑苏": ["u"],
    "怀来": ["ai", "uai"],
    "灰堆": ["ei", "uei"],
    "遥条": ["ao", "iao"],
    "由求": ["ou", "iou"],
    "言前": ["an", "ian", "uan", "üan"],
    "人辰": ["en", "in", "uen", "ün"],
    "江阳": ["ang", "iang", "uang"],
    "中东": ["eng", "ing", "ong", "iong", "ueng"],
}

FINAL2KEY18 = {f: k for k, vs in F18.items() for f in vs}
FINAL2KEY14 = {f: k for k, vs in F14.items() for f in vs}
FINAL2KEY13 = {f: k for k, vs in Z13.items() for f in vs}
# 常用别名：final 键 -> 韵部名
YUN18, YUN14, YUN13 = FINAL2KEY18, FINAL2KEY14, FINAL2KEY13

APICAL_INITIALS = ("zh", "ch", "sh", "z", "c", "s", "r")

# MODERN_EAR 的 NEAR_RHYME 显式白名单（V1.1：不再做“大组对大组”笛卡尔积）。
# 仅以下三对“同主元音、仅前/后鼻音韵尾对立”的跨辙组合判 NEAR：
#   en/eng、in/ing、uen/ueng
# 论证：en:eng、in:ing、uen:ueng 在普通话中只差韵尾 -n/-ng，主元音相同，
# 听感接近（宽式创作常见）；而 en:ong、in:ong、ün:ong、an:ang 等主元音或
# 圆唇/介音差异显著，一律 NO_RHYME（宁可从严，不给“听感模式”注水）。
# i/ü 系（i:ü、ie:üe、ian:üan、in:ün）在十三辙同归一七辙，听感模式先判
# PERFECT；无需出现在 NEAR 白名单中。
NEAR_RHYME_PAIRS = frozenset({("en", "eng"), ("in", "ing"), ("uen", "ueng")})


def final_key(final: str, initial: str = "") -> str:
    """把归一化韵母(final, 无调号, ü 已转写)映射为查表键。"""
    if final == "i" and initial in APICAL_INITIALS:
        return "i_apical"
    return final


def initial_of(py: str) -> str:
    """由拼音（无调号或带数字均可）取声母；零声母返回 ''."""
    p = re.sub(r"[0-9]", "", py)
    for ini in ("zh", "ch", "sh"):
        if p.startswith(ini) and len(p) > 2:
            return ini
    if p and p[0] in "bpmfdtnlgkhjqxrzcsyw":
        return p[0]
    return ""


def tone_of(py: str) -> int:
    """拼音尾部数字 1-4；无数字按轻声 5。"""
    if py and py[-1].isdigit():
        return int(py[-1])
    return 5


def pingze_of(tone: int) -> str:
    return {1: "平", 2: "平", 3: "仄", 4: "仄", 5: "轻"}.get(tone, "?")


def yunbu_of(final_key_: str, tone: int, profile: dict) -> str:
    """韵部查询；轻声/未知键返回 ''(表 UNCERTAIN)。"""
    if tone == 5:
        return ""
    return profile.get(final_key_, "")


def normalize_final(raw_final: str) -> str:
    """'ve4'→'üe'、'van2'→'üan'、'vn1'→'ün'、'v3'→'ü'；去调号。"""
    f = raw_final
    if f and f[-1].isdigit():
        f = f[:-1]
    return f.replace("v", "ü")


# --------------------------------------------------------------------------
# 字符数据
# --------------------------------------------------------------------------

_CHARS_CACHE = None


def load_chars() -> dict:
    global _CHARS_CACHE
    if _CHARS_CACHE is None:
        with open(CHARS_JSON, encoding="utf-8") as fh:
            _CHARS_CACHE = json.load(fh)["chars"]
    return _CHARS_CACHE


def lookup(char: str):
    """返回该字读音列表（list of dict）或 None（无数据）。"""
    return load_chars().get(char)


def reading_to_dict(py_tone3: str, final_raw: str) -> dict:
    """把 pypinyin 读音转成标准化条目。"""
    tone = tone_of(py_tone3)
    final = normalize_final(final_raw)
    ini = initial_of(py_tone3)
    fk = final_key(final, ini)
    pz = pingze_of(tone)
    return {
        "py": py_tone3,
        "tone": tone,
        "final": final,
        "pz": pz,
        "b18": yunbu_of(fk, tone, FINAL2KEY18),
        "b14": yunbu_of(fk, tone, FINAL2KEY14),
        "z13": yunbu_of(fk, tone, FINAL2KEY13),
    }


def resolve_reading(char: str, override_py: str = ""):
    """默认读音 = 底层字典返回的第一读音（dictionary_order，非词频排序）；
    可指定 override_py（如 'chang2'）锁定。返回 (reading, all_readings)。
    override 不合法时返回 (None, all)。"""
    all_r = lookup(char)
    if not all_r:
        return None, []
    if not override_py:
        return all_r[0], all_r
    for r in all_r:
        if r["py"] == override_py:
            return r, all_r
    return None, all_r


# --------------------------------------------------------------------------
# 押韵比较
# --------------------------------------------------------------------------

RHYME_LEVELS = ("PERFECT_RHYME", "NEAR_RHYME", "NO_RHYME", "UNCERTAIN")


def rhyme_compare_strict(r1: dict, r2: dict, profile_key: str = "b18") -> tuple:
    """严格韵书比较：同部 PERFECT；任一侧轻声/无部数据 UNCERTAIN；否则 NO。"""
    g1, g2 = r1.get(profile_key, ""), r2.get(profile_key, "")
    if not g1 or not g2:
        return "UNCERTAIN", "轻声或无韵部数据", f"{g1 or '?'} vs {g2 or '?'}"
    if g1 == g2:
        return "PERFECT_RHYME", "同属" + g1, g1
    return "NO_RHYME", f"分属 {g1} / {g2}", f"{g1} vs {g2}"


def rhyme_compare_ear(r1: dict, r2: dict) -> tuple:
    """听感辅助（MODERN_EAR）：以十三辙为 PERFECT 线，NEAR 只来自显式白名单。

    V1.1 修复：移除“大组对大组”笛卡尔积（旧实现会把 云/东、心/空、门/东
    都判成 NEAR）；现在 NEAR 仅当 (f1,f2) 命中 NEAR_RHYME_PAIRS。
    """
    g1, g2 = r1.get("z13", ""), r2.get("z13", "")
    f1, f2 = r1.get("final", ""), r2.get("final", "")
    if not g1 or not g2:
        return "UNCERTAIN", "轻声或无辙数据", f"{g1 or '?'} vs {g2 or '?'}"
    if g1 == g2:
        return "PERFECT_RHYME", "同辙" + g1, g1
    if f1 and f2 and ((f1, f2) in NEAR_RHYME_PAIRS or (f2, f1) in NEAR_RHYME_PAIRS):
        return "NEAR_RHYME", (
            f"不同辙({g1}/{g2})但命中 NEAR 白名单({f1}~{f2})，"
            f"宽松创作可用，严格韵书不押"
        ), f"{g1} vs {g2}"
    return "NO_RHYME", f"分属 {g1} / {g2}", f"{g1} vs {g2}"


# --------------------------------------------------------------------------
# 平仄骨架 / 粘对模板
# --------------------------------------------------------------------------

# 可切换韵书/听感 profile（PHASE 5）：整诗硬判定跟随用户选择，默认 xinyun18。
RHYME_PROFILES = ("xinyun18", "xinyun14", "shisan13", "modern-ear")
RHYME_PROFILE_KEY = {"xinyun18": "b18", "xinyun14": "b14", "shisan13": "z13"}
RHYME_PROFILE_NAME = {
    "xinyun18": "中华新韵十八韵", "xinyun14": "中华新韵十四韵",
    "shisan13": "十三辙", "modern-ear": "MODERN_EAR 听感",
}


def judge_rhyme_pair(a: dict, b: dict, profile: str = "xinyun18") -> dict:
    """统一押韵判定入口（rc2 PHASE 1/2）。

    第2↔4句、第1↔2句（首句入韵）等所有韵脚对一律走本函数；
    禁止在别处自行选择韵书字段，禁止按文案字符串反推状态。

    strict 语义（rc2 修复）：xinyun18 / xinyun14 / shisan13 为真正 strict：
    relation 完全由所选韵书决定（同部=PERFECT_RHYME→PASS；不同部=NO_RHYME→FAIL；
    轻声/无数据=UNCERTAIN→WARN）。十三辙/听感仅作为“辅助提示”写入 message，
    不改变 status。modern-ear 按听感自规则：PERFECT→PASS；NEAR→WARN；NO→FAIL。

    返回结构化 dict：
      status:   "PASS" | "WARN" | "FAIL"
      relation: "PERFECT_RHYME" | "NEAR_RHYME" | "NO_RHYME" | "UNCERTAIN"
      message:  显示用文案（绝不反向解析 message 推导 status）
    """
    pname = RHYME_PROFILE_NAME.get(profile, profile)
    if profile == "modern-ear":
        lv, why, _ = rhyme_compare_ear(a, b)
        if lv == "PERFECT_RHYME":
            return {"status": "PASS", "relation": "PERFECT_RHYME",
                    "message": f"{pname}判定：{why}"}
        if lv == "NEAR_RHYME":
            return {"status": "WARN", "relation": "NEAR_RHYME",
                    "message": f"{pname}判定：{why}"}
        if lv == "NO_RHYME":
            return {"status": "FAIL", "relation": "NO_RHYME",
                    "message": f"{pname}判定：明显不押（NO_RHYME）——出韵"}
        return {"status": "WARN", "relation": "UNCERTAIN",
                "message": f"{pname}判定 UNCERTAIN（轻声或无辙数据）"}
    key = RHYME_PROFILE_KEY.get(profile)
    if key is None:
        return {"status": "WARN", "relation": "UNCERTAIN",
                "message": f"未知 profile：{profile}（合法值 {'/'.join(RHYME_PROFILES)}）"}
    lv, why, _ = rhyme_compare_strict(a, b, key)
    if lv == "UNCERTAIN":
        return {"status": "WARN", "relation": "UNCERTAIN",
                "message": f"{pname}判定 UNCERTAIN（轻声或无韵部数据）"}
    if lv == "PERFECT_RHYME":
        return {"status": "PASS", "relation": "PERFECT_RHYME",
                "message": f"{pname}判定：{why}"}
    # NO_RHYME：strict profile 下直接 FAIL；听感差异只进辅助文案
    ear_lv, ear_why, _ = rhyme_compare_ear(a, b)
    if ear_lv == "PERFECT_RHYME":
        hint = "（辅助：十三辙同辙，现代听感较近——strict 判定不受影响）"
    elif ear_lv == "NEAR_RHYME":
        hint = f"（辅助：{ear_why}——strict 判定不受影响）"
    else:
        hint = "（辅助：十三辙/听感亦不同辙）"
    return {"status": "FAIL", "relation": "NO_RHYME",
            "message": f"{pname}不同部（{why}）——出韵 {hint}"}


JUELU_PATTERNS = {
    # 五绝：key = (句首平仄, 是否首句入韵)
    ("ze", False): ["仄仄平平仄", "平平仄仄平", "平平平仄仄", "仄仄仄平平"],
    ("ze", True): ["仄仄仄平平", "平平仄仄平", "平平平仄仄", "仄仄仄平平"],
    ("ping", False): ["平平平仄仄", "仄仄仄平平", "仄仄平平仄", "平平仄仄平"],
    ("ping", True): ["平平仄仄平", "仄仄仄平平", "仄仄平平仄", "平平仄仄平"],
}


def septet_pattern(quintet: list) -> list:
    """七绝骨架 = 五绝骨架前加相反两字（平→仄仄，仄→平平）。"""
    out = []
    for line in quintet:
        head = "仄仄" if line[0] == "平" else "平平"
        out.append(head + line)
    return out


def pattern_name(first_pz: str, head_rhyme: bool, length: int) -> str:
    start = "平起" if first_pz == "平" else "仄起"
    rhyme = "首句入韵" if head_rhyme else "首句不入韵"
    form = "五绝" if length == 5 else "七绝"
    return f"{form}·{start}{rhyme}式"


# --------------------------------------------------------------------------
# 诗歌检查
# --------------------------------------------------------------------------

def split_poem(text: str):
    """按标点/换行切句并去空。"""
    lines = re.split(r"[，。、；：！？,\n\r;:!?]+", text.strip())
    return [ln.strip() for ln in lines if ln.strip()]


def check_poem(text: str, readings_overrides: dict = None,
               positional_overrides: dict = None,
               expect_form: str = "", rhyme_profile: str = "xinyun18"):
    """整诗检查。返回结构化报告 dict。

    readings_overrides:   {char: "pinyin_tone3"}，如 {"长": "chang2"}（按字全局）。
    positional_overrides: {(行1based, 列1based): "pinyin_tone3"}，如 {(4,5): "chang2"}。
                          V1.1 PHASE 8：同一字在不同位置可给不同读音。
    优先级：位置 override > 字 override > 字典默认（dictionary_order）。
    expect_form:  "jueju5" / "jueju7" / ""(自动)。
    rhyme_profile: "xinyun18"(默认) / "xinyun14" / "shisan13" / "modern-ear"。
    """
    overrides = readings_overrides or {}
    pos_overrides = positional_overrides or {}
    lines = split_poem(text)
    report = {
        "input": text,
        "lines": [],
        "issues": [],
        "verdict": "FAIL",
        "form_expected": expect_form,
        "form_actual": "",
        "rhyme_profile": rhyme_profile,
    }

    # 行数与字数
    counts = [len(ln) for ln in lines]
    if len(lines) != 4:
        report["issues"].append({
            "level": "FAIL", "item": "行数",
            "detail": f"绝句应为 4 句，实得 {len(lines)} 句",
        })
    if expect_form == "jueju5":
        report["form_expected"] = "五绝(5字×4句)"
    elif expect_form == "jueju7":
        report["form_expected"] = "七绝(7字×4句)"

    if counts and len(set(counts)) == 1:
        n = counts[0]
        if len(lines) == 4 and n in (5, 7):
            report["form_actual"] = "五绝" if n == 5 else "七绝"
            if expect_form and ((expect_form == "jueju5" and n != 5) or (expect_form == "jueju7" and n != 7)):
                report["issues"].append({
                    "level": "FAIL", "item": "字数",
                    "detail": f"要求{report['form_expected']}，实为每句{n}字",
                })
        else:
            report["issues"].append({
                "level": "FAIL", "item": "字数",
                "detail": f"每句 {n} 字、共 {len(lines)} 句，不是五/七言绝句",
            })
    else:
        report["issues"].append({
            "level": "FAIL", "item": "字数",
            "detail": f"各句字数不齐：{counts}",
        })

    # 逐句逐字标注（V1.1：位置级 override > 字级 override > 字典默认）
    # rc2 PHASE 4：位置 override 越界必须显式诊断，不允许静默忽略
    for (pr, pc), pv in sorted(pos_overrides.items()):
        if pr < 1 or pc < 1 or pr > len(lines) or pc > (len(lines[pr - 1]) if 1 <= pr <= len(lines) else 0):
            report["issues"].append({
                "level": "WARN", "code": "POSITION_OVERRIDE_OUT_OF_RANGE",
                "item": "override",
                "detail": (f"位置 override 第{pr}句第{pc}字={pv} 越界"
                           f"（实际 {len(lines)} 句，"
                           f"第{pr}句 {len(lines[pr-1]) if 1 <= pr <= len(lines) else '-'} 字），已跳过"),
            })
    key_positions = []
    char_grid = []
    for ln_idx, ln in enumerate(lines):
        per_line = []
        for col_idx, ch in enumerate(ln):
            pos_key = (ln_idx + 1, col_idx + 1)
            has_pos_ov = pos_key in pos_overrides
            has_char_ov = (not has_pos_ov) and (ch in overrides)
            ov = (pos_overrides[pos_key] if has_pos_ov
                  else (overrides[ch] if has_char_ov else ""))
            ov_specified = has_pos_ov or has_char_ov
            if ov_specified and ov == "":
                # rc2 PHASE 5：显式空 override（如 长=）同样非法 → UNCERTAIN
                r, all_r = None, lookup(ch) or []
            else:
                r, all_r = resolve_reading(ch, ov)
            if r is None:
                if ov_specified:
                    # rc2 PHASE 5：非法 override 不假装成功、不静默 fallback——
                    # 该字标记 UNCERTAIN 并显式报告 INVALID_READING_OVERRIDE
                    where = f"位置第{ln_idx+1}句第{col_idx+1}字" if has_pos_ov else "字级"
                    cand = "、".join(a["py"] for a in all_r) if all_r else "（无候选数据）"
                    report["issues"].append({
                        "level": "WARN", "code": "INVALID_READING_OVERRIDE",
                        "item": "override",
                        "detail": (f"{where}「{ch}」指定读音 {ov} 无效"
                                   f"（候选：{cand}）；该位置无法确定读音，已标记为 UNCERTAIN"),
                    })
                per_line.append({
                    "char": ch, "py": "?", "tone": 0, "pz": "?",
                    "neutral": False, "uncertain": True,
                    "alts": [a["py"] for a in all_r],
                })
            else:
                per_line.append({
                    "char": ch, "py": r["py"], "tone": r["tone"], "pz": r["pz"],
                    "final": r["final"],
                    "b18": r["b18"], "b14": r["b14"], "z13": r["z13"],
                    "neutral": r["tone"] == 5,
                    "uncertain": False,
                    "alts": [a["py"] for a in all_r if a["py"] != r["py"]],
                })
        char_grid.append(per_line)

    # 关键位置：五言 2/4，七言 2/4/6（1-based）
    if counts and len(set(counts)) == 1 and counts[0] in (5, 7):
        key_positions = [1, 3] if counts[0] == 5 else [1, 3, 5]  # 0-based: 第2、4(、6)字

    # 韵脚与押韵（判定 profile 可切换）
    rhyme_report = _check_rhymes(lines, char_grid, profile=rhyme_profile)
    report["rhyme"] = rhyme_report

    # 粘对
    if len(lines) == 4 and key_positions:
        report["dui_nian"] = _check_dui_nian(lines, char_grid, key_positions)

    # 汇总级别
    for sec in ("rhyme", "dui_nian"):
        if sec in report:
            for entry in report[sec]["checks"]:
                if entry.get("level") in ("FAIL", "WARN"):
                    report["issues"].append(entry)
    if not any(i["level"] == "FAIL" for i in report["issues"]):
        report["verdict"] = "WARN" if any(i["level"] == "WARN" for i in report["issues"]) else "PASS"

    # 行内数据回填（供展示）
    report["lines"] = [
        {"text": ln, "chars": char_grid[i]} for i, ln in enumerate(lines)
    ]
    return report


def _pz_at(grid, line_i, pos0):
    """返回 (平仄, 是否不确定)。pos0 为 0-based。

    V1.1 轻声规则（PHASE 4）：轻声不强制归入平/仄。位于关键位时按
    “无法确定”处理（RELATION=UNCERTAIN → WARN），不直接 FAIL。
    """
    cell = grid[line_i][pos0]
    if cell.get("uncertain") or cell.get("pz") == "轻":
        return "?", True
    return cell["pz"], False


def _check_rhymes(lines, grid, profile: str = "xinyun18") -> dict:
    n_lines = len(lines)
    out = {"checks": [], "rhyme_chars": {}, "profile": profile}
    tail_pz = []
    for li in range(n_lines):
        if not grid[li]:
            continue
        tail = grid[li][-1]
        tail_pz.append((li, tail["char"], tail["pz"], tail.get("py", "?"),
                        tail.get("b18", ""), tail.get("b14", ""), tail.get("z13", ""),
                        tail.get("uncertain", False), tail.get("neutral", False)))
    # 韵脚表
    rhyme_chars = {"第2句": None, "第4句": None}
    if len(tail_pz) >= 2:
        for li, ch, pz, py, b18, b14, z13, unc, neu in tail_pz:
            if li in (1, 3):
                label = "第2句" if li == 1 else "第4句"
                rhyme_chars[label] = {
                    "char": ch, "py": py, "pz": pz, "b18": b18, "b14": b14,
                    "z13": z13, "uncertain": unc or neu,
                }

    # 必查：第2、4句韵脚一致（判定跟随 profile，V1.1 PHASE 5）
    if n_lines >= 4:
        t2, t4 = tail_pz[1], tail_pz[3]
        r2 = {"b18": t2[4], "b14": t2[5], "z13": t2[6], "final": None}
        r4 = {"b18": t4[4], "b14": t4[5], "z13": t4[6], "final": None}
        f2 = grid[1][-1].get("final", "") if len(grid) > 1 and grid[1] else ""
        f4 = grid[3][-1].get("final", "") if len(grid) > 3 and grid[3] else ""
        r2["final"], r4["final"] = f2, f4
        # 多线对照（供输出信息）：十八韵 / 十四韵 / 十三辙 / 听感
        info18 = rhyme_compare_strict(r2, r4, "b18")[0].split("_")[0]
        info14 = rhyme_compare_strict(r2, r4, "b14")[0].split("_")[0]
        info13 = rhyme_compare_strict(r2, r4, "z13")[0].split("_")[0]
        ear_lv = rhyme_compare_ear(r2, r4)[0].split("_")[0]
        if t2[7] or t4[7] or t2[8] or t4[8]:
            # 无数据或轻声韵脚：判 UNCERTAIN(WARN)，绝不直接 PERFECT
            relation = "UNCERTAIN"
            level = "WARN"
            detail = (
                f"第2句韵脚 {t2[1]}({t2[3]}) / 第4句韵脚 {t4[1]}({t4[3]}) 含轻声或无数据字，"
                f"押韵无法可靠判定（UNCERTAIN）；对照 十八韵[{info18}] 十四韵[{info14}] "
                f"十三辙[{info13}] 听感[{ear_lv}]"
            )
        else:
            j = judge_rhyme_pair(r2, r4, profile)
            level = j["status"]
            relation = j["relation"]
            detail = (f"{j['message']} ｜ 对照：十八韵[{info18}] 十四韵[{info14}] "
                      f"十三辙[{info13}] 听感[{ear_lv}]")
        out["checks"].append({
            "level": level, "item": "押韵(第2/4句韵脚)", "detail": detail,
            "relation": relation,
        })
    else:
        out["checks"].append({
            "level": "FAIL", "item": "押韵", "detail": "句数不足 4，无法检查韵脚",
        })

    # 首句是否入韵（rc2 PHASE 2/3：与 2/4 句共用 judge_rhyme_pair 统一入口；
    # 状态由结构化字段决定，绝不从文案字符串反推）
    if n_lines >= 2 and tail_pz:
        t1 = tail_pz[0]
        head = {
            "item": "首句收尾",
            "first_line_rhymes": False,
            "relation": "NA",
            "detail": "",
        }
        if t1[7] or t1[8]:
            head["level"] = "WARN"
            head["relation"] = "UNCERTAIN"
            head["first_line_rhymes"] = None
            head["detail"] = f"第1句「{t1[1]}」{t1[2]}收（轻声/无数据，入韵状态未知）"
        elif t1[2] != "平":
            head["level"] = "PASS"
            head["relation"] = "NA"
            head["first_line_rhymes"] = False
            head["detail"] = f"第1句「{t1[1]}」仄收（首句不入韵）"
        else:
            # 平收：用与正文完全相同的统一判定入口比较第1句与第2句韵脚
            r1 = {"b18": t1[4], "b14": t1[5], "z13": t1[6],
                  "final": grid[0][-1].get("final", "") if grid[0] else ""}
            r2 = {"b18": tail_pz[1][4], "b14": tail_pz[1][5], "z13": tail_pz[1][6],
                  "final": grid[1][-1].get("final", "") if len(grid) > 1 and grid[1] else ""}
            j = judge_rhyme_pair(r1, r2, profile)
            head["level"] = j["status"]
            head["relation"] = j["relation"]
            if j["status"] == "PASS":
                head["first_line_rhymes"] = True
                head["detail"] = f"第1句「{t1[1]}」平收且与第2句同韵（首句入韵）—— {j['message']}"
            elif j["status"] == "FAIL":
                head["first_line_rhymes"] = False
                head["detail"] = (f"第1句「{t1[1]}」平收但未入韵"
                                   f"（第2句韵脚不同部，判定 {j['relation']}）—— {j['message']}")
            else:  # WARN（近韵/UNCERTAIN 等）
                head["first_line_rhymes"] = None
                head["detail"] = f"第1句「{t1[1]}」平收，入韵状态待定（{j['relation']}）—— {j['message']}"
        out["checks"].append(head)

    # 韵脚平仄提示（轻声韵脚单列说明）
    pz_label = {"平": "平声", "仄": "仄声", "轻": "轻声"}
    for li, ch, pz, py, b18, b14, z13, unc, neu in tail_pz:
        if li in (1, 3) and not unc:
            if pz == "轻":
                out["checks"].append({
                    "level": "WARN", "item": "韵脚声调",
                    "detail": f"第{li+1}句韵脚「{ch}」为轻声；轻声不参与韵部与押韵判定，"
                              f"建议人工确认或改用实读字",
                })
            elif pz != "平":
                out["checks"].append({
                    "level": "WARN", "item": "韵脚声调",
                    "detail": f"第{li+1}句韵脚「{ch}」为{pz_label.get(pz, pz)}；近体诗韵脚通常押平声，"
                              f"仄韵属古风/变格（本项目允许，仅提示）",
                })
    out["rhyme_chars"] = rhyme_chars
    return out


def _check_dui_nian(lines, grid, key_positions) -> dict:
    """联内相对(1-2, 3-4) + 联间相粘(2-3)。key_positions 为 0-based 关键位。"""
    out = {"checks": [], "template_hint": ""}
    lc = [[_pz_at(grid, i, p) for p in range(len(grid[i]))] for i in range(4)]

    def same(a, b):
        return a[0] == b[0] and not a[1] and not b[1]

    def opp(a, b):
        if a[1] or b[1]:
            return None  # uncertain
        return (a[0] == "平" and b[0] == "仄") or (a[0] == "仄" and b[0] == "平")

    def pos_label(p):
        return f"第{p+1}字"

    def unc_reason(i, p):
        c = grid[i][p]
        if c.get("pz") == "轻":
            return f"{pos_label(p)}为轻声"
        return f"{pos_label(p)}无读音数据"

    for pair_name, i1, i2 in (("相对", 0, 1), ("相对", 2, 3)):
        results = []
        ok_all, has_unc = True, False
        first_ok = None  # 结构化：首个关键位（第2字）是否合规；None=UNCERTAIN
        for idx, p in enumerate(key_positions):
            o = opp(lc[i1][p], lc[i2][p])
            if o is None:
                has_unc = True
                results.append(
                    f"{pos_label(p)}: {unc_reason(i1, p)}或{unc_reason(i2, p)}，"
                    f"RELATION=UNCERTAIN（需人工确认或 --reading 指定读法）")
            elif o:
                results.append(f"{pos_label(p)}: {lc[i1][p][0]}↔{lc[i2][p][0]} 相反✓")
            else:
                ok_all = False
                results.append(f"{pos_label(p)}: {lc[i1][p][0]}↔{lc[i2][p][0]} 相同✗")
            if idx == 0:
                first_ok = None if o is None else o
        if first_ok is False:
            level = "FAIL"
            detail = f"第{i1+1}句与第{i2+1}句失对（{pos_label(key_positions[0])}未相反）；" + "；".join(results)
        elif first_ok is None and not ok_all:
            level = "FAIL" if has_unc else "WARN"
            detail = f"第{i1+1}句与第{i2+1}句：首个关键位无法判定且存在明确失对位；" + "；".join(results)
        elif ok_all:
            level = "WARN" if has_unc else "PASS"
            detail = "；".join(results) + ("（含无法判定位）" if has_unc else "")
        else:
            level = "WARN"
            detail = f"第{i1+1}句与第{i2+1}句关键位未全相反；" + "；".join(results)
        out["checks"].append({
            "level": level, "item": f"{pair_name}(第{i1+1}/{i2+1}句)", "detail": detail,
        })

    # 相粘：第2句与第3句
    results = []
    ok_all, has_unc = True, False
    first_ok = None  # 结构化：首个关键位（第2字）是否同类；None=UNCERTAIN
    for idx, p in enumerate(key_positions):
        if same(lc[1][p], lc[2][p]):
            results.append(f"{pos_label(p)}: {lc[1][p][0]}↔{lc[2][p][0]} 同类✓")
        elif lc[1][p][1] or lc[2][p][1]:
            has_unc = True
            results.append(
                f"{pos_label(p)}: {unc_reason(1, p)}或{unc_reason(2, p)}，"
                f"RELATION=UNCERTAIN（需人工确认或 --reading 指定读法）")
        else:
            ok_all = False
            results.append(f"{pos_label(p)}: {lc[1][p][0]}↔{lc[2][p][0]} 异类✗")
        if idx == 0:
            same_ok = (lc[1][p][0] == lc[2][p][0]) and not (lc[1][p][1] or lc[2][p][1])
            first_ok = same_ok if not (lc[1][p][1] or lc[2][p][1]) else None
    if first_ok is False:
        level = "FAIL"
        detail = f"第2句与第3句失粘（{pos_label(key_positions[0])}未同类）；" + "；".join(results)
    elif first_ok is None and not ok_all:
        level = "FAIL" if has_unc else "WARN"
        detail = f"第2句与第3句：首个关键位无法判定且存在明确失粘位；" + "；".join(results)
    elif ok_all:
        level = "WARN" if has_unc else "PASS"
        detail = "；".join(results) + ("（含无法判定位）" if has_unc else "")
    else:
        level = "WARN"
        detail = f"第2句与第3句关键位未全同类；" + "；".join(results)
    out["checks"].append({
        "level": level, "item": "相粘(第2/3句)", "detail": detail,
    })

    # 模板提示（仅当四句齐整且无未知平仄时）
    if len(lines) == 4 and all(not x[1] for row in lc for x in row):
        seq = ["".join(grid[i][p][0] if False else _full_pz_line(grid[i])) for i in range(4)]
        # 简化：只比较关键位+句尾
        guess = _match_template(grid)
        if guess:
            out["template_hint"] = guess
            out["checks"].append({
                "level": "PASS", "item": "平仄骨架",
                "detail": guess,
            })
    return out


def _full_pz_line(cells):
    return "".join(c.get("pz", "?") for c in cells)


def _match_template(grid):
    """按 2/4(6) 关键位 + 句尾平仄匹配标准绝句骨架；逐字一致才报告。"""
    lens = [len(row) for row in grid]
    if len(grid) != 4 or len(set(lens)) != 1 or lens[0] not in (5, 7):
        return ""
    n = lens[0]
    base = JUELU_PATTERNS
    candidates = []
    for (start, head_rhyme), pat in base.items():
        if n == 7:
            pat = septet_pattern(pat)
        candidates.append((start, head_rhyme, pat))
    actual = [_full_pz_line(row) for row in grid]
    for start, head_rhyme, pat in candidates:
        if actual == pat:
            return (f"全诗平仄与标准「{template_label(pat, n)}」逐字一致 "
                    f"（{ '/'.join(pat) }）")
    # 关键位匹配（2、4(、6) 与句尾）
    for start, head_rhyme, pat in candidates:
        ok = True
        for i in range(4):
            for p in (1, 3) if n == 5 else (1, 3, 5):
                if actual[i][p] != pat[i][p]:
                    ok = False
                    break
            if actual[i][-1] != pat[i][-1]:
                ok = False
                break
            if not ok:
                break
        if ok:
            return (f"关键位(第2、4{('、6' if n == 7 else '')}字及句尾)与标准"
                    f"「{template_label(pat, n)}」一致")
    return ""


def template_label(pat: list, n: int) -> str:
    """由模板内容推导式名（首字定起式、首句尾定入韵），避免七绝化时 key 与内容错位。"""
    form = "五绝" if n == 5 else "七绝"
    start = "平起" if pat[0][0] == "平" else "仄起"
    rhyme = "首句入韵" if pat[0][-1] == "平" else "首句不入韵"
    return f"{form}·{start}{rhyme}式"
