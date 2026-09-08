# Architecture

中文诗律 Skill 的架构说明。

## 总则：创作与验证分离

```
诗人人设（创作侧）                本工具（验证侧）
  诗意 / 意象 / 诗脉               拼音 / 声调 / 平仄
  情绪 / 语言 / 留白               韵部 / 押韵 / 相对 / 相粘
  朗读美感                         模板 / 整诗扫描
        │                                │
        └──────── 诗句 ──────────►  check_poem ──► PASS/WARN/FAIL
                                  （确定性，无 LLM 成分）
```

LLM 的角色：运行脚本 → 读结构化报告 → 修改诗句 → 复检。

## 数据链（单源，可审计）

```
pypinyin (MIT, 构建期)
      │ 单次调用 Style.TONE3(heteronym=True)
      ▼
scripts/syllable_parser.py     ← 自足解析层：以完整拼音读音（如 chang2）
      │                           为唯一主键，独立推导：
      │                           tone（尾数字）/ initial / final（含
      │                           j/q/x 后 u→ü、n/l 后 v→ü、ui/un/iu 省写
      │                           还原、y/w 零声母表、舌尖元音 i_apical）
      ▼
data/chars.json                ← 36,808 readings（py/tone/final/pz/b18/b14/z13）
      │                           运行时唯一数据依赖；全库审计 0 mismatch
      ▼
scripts/prosody_core.py        ← 确定性规则引擎（查表/比较/报告）
```

要点：
- **不存在跨 Style 列表配对**（v1 数据错位缺陷的根因已消除）；
- 轻声（tone 5）不参与韵部归属 → UNCERTAIN；
- 无法映射的特殊音节（n/ng/m/hm、yo、ê 系）→ final 为空 → UNCERTAIN，禁止猜测；
- 连续两次构建内容 hash 一致（可重复构建）。

## 规则层（rc2 之后的结构化状态模型）

所有判定输出结构化字段，**禁止从人类文案字符串反推状态**：

```python
{ "status": "PASS" | "WARN" | "FAIL",
  "relation": "PERFECT_RHYME" | "NEAR_RHYME" | "NO_RHYME" | "UNCERTAIN",
  "message": "…" }        # 仅展示
```

- 统一判定入口 `judge_rhyme_pair(a, b, profile)`：第 2/4 句、首句入韵（1↔2）全走同一函数；
- strict profile（xinyun18/xinyun14/shisan13）：主判定只由所选韵书决定；
  十三辙/听感仅作辅助提示；modern-ear 按自身规则；
- 粘/对：关键位（五言 2/4、七言 2/4/6）布尔化判定（first_ok/ok_all/has_unc），
  轻声关键位 → RELATION=UNCERTAIN（WARN 不 FAIL）。

## 韵部模型

| 维度 | 内容 |
|---|---|
| b18 | 中华新韵·十八韵（默认 STRICT_XINYUN 线） |
| b14 | 中华新韵·十四韵 |
| z13 | 十三辙（MODERN_EAR 的 PERFECT 线） |
| NEAR 白名单 | {(en,eng), (in,ing), (uen,ueng)}（仅听感模式提示） |

韵母键为"完整韵母（含韵头）"：`a ia ua … i_apical`（i_apical = zh/ch/sh/r/z/c/s 后 -i）。

## override 优先级

```
位置级 --reading 行:列=拼音  >  字级 --reading 字=拼音  >  字典默认（dictionary_order）
```

- 非法/空 override → `INVALID_READING_OVERRIDE` + 该字 UNCERTAIN（不静默 fallback）；
- 越界位置 → `POSITION_OVERRIDE_OUT_OF_RANGE`（显式诊断）。

## 目录

```
├── SKILL.md            # Skill 入口（front matter: id/name/version/description）
├── data/               # chars.json + 韵部元数据（xinyun18/14、shisan13）
├── scripts/            # syllable_parser / prosody_core / check_* / build_char_table
├── references/         # 规则文档（modern_rhyme/pingze/dui_and_nian/jueju_patterns/terminology/sources）
└── tests/              # 121 个确定性测试（4 套件）
```
