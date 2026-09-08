---
id: chinese-poetry-prosody
name: Chinese poetry prosody checker (中文诗律)
version: 1.1.0
description: 中文格律诗（五绝/七绝）的确定性规则验证工具。负责拼音、声调、简化平仄、现代韵（中华新韵十八韵/十四韵、十三辙、听感近韵）、联内相对、联间相粘、韵脚与整诗扫描；所有底层判定由数据+程序计算并以结构化状态输出，LLM 只解释结果并修改诗句。v1.1-rc2：strict profile 真正严格（十三辙/听感仅作辅助提示不改变判定）、首句入韵与正文共用同一判定入口、无字符串反推状态、override 越界/非法显式诊断（POSITION_OVERRIDE_OUT_OF_RANGE / INVALID_READING_OVERRIDE）。诗人创作后请用它复查格律；处理诗歌声韵问题、判定是否出韵/失粘/失对、查字音韵部时使用。
---

# 中文诗律 Skill（chinese-poetry-prosody）v1.1.0 Final

## 定位与职责边界（本 Skill 最重要的一页）

把"审美创作"与"形式规则验证"拆开：

| | 诗人人设 Prompt（创作侧） | 本 Skill（验证侧） |
|---|---|---|
| 负责 | 诗意、意象、诗脉、情绪、语言、留白、风格、朗读美感 | 拼音、声调、平仄、韵部、押韵、相对、相粘、模板、整诗扫描 |
| 方法 | 创作与修改 | **确定性数据+程序计算** |

工程原则（不遵守则本 Skill 无意义）：
- **不得让 LLM 自己判断"这两字是否押韵/这字是平是仄"** —— 一律查 `data/chars.json`（由 pypinyin MIT 数据经**单一拼音来源**构建，离线、确定性、全库审计通过）。
- LLM 的角色是：运行脚本 → 阅读报告 → 依据报告修改诗句 → 复检，直到 PASS 或确认无法满足。
- 无法可靠判定时脚本返回 UNCERTAIN，LLM 不得猜测填充。

## 使用流程（每次写/改格律诗后执行）

```
1. 诗人按人设写诗（或修改稿）
2. 运行：py scripts/check_poem.py --poem "<诗>" [--form jueju5|jueju7]
         [--reading 字=拼音 | 行:列=拼音 ...] [--rhyme-profile xinyun18|xinyun14|shisan13|modern-ear]
3. 读报告：
   PASS —— 确定性规则全部通过，可交付
   WARN —— 无硬性违规但有提示（多音字默认读法、近韵提醒、韵脚仄声、
           轻声关键位 UNCERTAIN 等），视提示决定是否修改/加 --reading
   FAIL —— 存在硬性违规（失粘/失对/出韵/字数），必须修改对应句后复检
4. 修改只动违规处，保持诗意（人设负责）；记录每一版，不隐藏中间版本
5. 迭代上限建议 5 轮；若诗意与规则不可兼得，如实报告冲突，不强行凑合
```

## 命令速查

所有命令在 Skill 根目录（`~/.kun/skills/chinese-poetry-prosody/`）下执行：

```bash
# 1) 单字音韵查询（候选读音全部列出；默认读音标注 DEFAULT_SOURCE=dictionary_order）
py scripts/check_char.py 城
py scripts/check_char.py 长        # 多音字：默认 + 候选

# 2) 韵脚比较（可切韵书 profile）
py scripts/check_rhyme.py 声 城
py scripts/check_rhyme.py 窗 长 --reading 长=chang2
py scripts/check_rhyme.py 风 东 --profile xinyun14     # 十四韵下同部
py scripts/check_rhyme.py 风 东 --profile modern-ear   # 听感模式

# 3) 整诗扫描（五绝/七绝）
py scripts/check_poem.py --poem "客舍秋灯暗，风来透纸窗。开门霜满地，路向晓山长。" --reading 长=chang2
py scripts/check_poem.py --poem "……" --form jueju7
py scripts/check_poem.py --poem "……" --reading 4:5=chang2   # 位置级 override（第4句第5字）
py scripts/check_poem.py --poem "……" --rhyme-profile xinyun14
py scripts/check_poem.py --poem "……" --json

# 4) 全库一致性审计（发布门禁）
py scripts/build_char_table.py --check    # GATE: PASS 才允许发布

# 5) 测试
py tests/test_prosody.py                  # V1 保留测试（21 个）
py tests/test_v1_1_suite.py               # V1.1 四层套件（56 个，含全库审计）
```

- 诗句分隔：逗号/句号/顿号/换行均可。
- `--reading 字=拼音` 按字全局锁定；`--reading 行:列=拼音` 位置级锁定（行/列均 1-based）。
  **优先级：位置 override > 字 override > 字典默认。**
- `--rhyme-profile` 默认 **xinyun18**（与 V1 行为一致）。现代听感创作可切
  `xinyun14`（波/歌、齐/鱼、庚/东 等合部更宽）或 `modern-ear`（以十三辙为
  听感线）。
  **rc2 strict 语义**：xinyun18/xinyun14/shisan13 下主判定完全由所选韵书决定
  （不同部=NO_RHYME=FAIL）；十三辙/MODERN_EAR 只作为“辅助提示”显示，不改变
  判定。modern-ear 按其自身规则（PERFECT→PASS、NEAR→WARN、NO→FAIL）。
- 退出码：0=PASS，1=WARN，2=FAIL。

## 规则速查（详细版见 references/）

### 简化平仄（现代普通话）
- 1、2 声 = 平；3、4 声 = 仄；轻声 = "轻"。
- **轻声规则（V1.1）**：轻声**不强制归入平或仄**。位于关键位（2/4/6 字）
  时对/粘关系 = UNCERTAIN → WARN（提示"需人工确认或 --reading"），不直接
  FAIL；位于韵脚时不参与韵部判定（押韵 UNCERTAIN → WARN），绝不自动判
  PERFECT。不要默认把轻声当平声。
- 多音字：默认 = 底层字典返回的第一读音（DEFAULT_SOURCE=dictionary_order，
  **非词频排序**）；check_char/check_poem 会列出全部候选，语义明确时用
  --reading（字级或位置级）锁定。
- **本项目现代简化规则 ≠ 近体诗学完整规则**（无入声体系）；分析古体作品禁用。

### 押韵 profile 与两级听感
- profile：`xinyun18`（默认）/ `xinyun14` / `shisan13` / `modern-ear`；
  整诗硬判定跟随 profile，输出附 十八韵/十四韵/十三辙/听感 四线对照。
- MODERN_EAR 的 NEAR_RHYME 只来自**显式白名单**（V1.1 移除大组笛卡尔积）：
  `(en,eng)、(in,ing)、(uen,ueng)` 三对跨辙近韵；其余跨辙一律 NO_RHYME
  （如 云/东、心/空、门/东 不再误判 NEAR）。
- 输出押韵结论必须注明依据 profile，防跨版本误判。

### 粘与对（简化检查法）
```
第1句 →(对)→ 第2句 →(粘)→ 第3句 →(对)→ 第4句
```
- 对 = 联内两句关键位平仄**相反**；粘 = 第2、3句关键位平仄**同类**。
- 关键位：五言=第2、4字；七言=第2、4、6字。
- 第2字异类 → FAIL 失粘/失对；第2字合规但其余关键位有偏差 → WARN；
  关键位为轻声/无数据 → RELATION=UNCERTAIN（WARN，不 FAIL）。

### 韵脚
- 第2、4句必查同韵（按所选 profile）；首句可入韵（平收同部）可不入韵（仄收）。
- 韵脚通常押平声；仄韵脚提示但允许；轻声韵脚判 UNCERTAIN。

## 目录结构

```
chinese-poetry-prosody/
├── SKILL.md                # 本文件（v1.1.0）
├── references/
│   ├── modern_rhyme.md     # 现代韵：profiles、韵书版本差异、NEAR 白名单
│   ├── pingze.md           # 简化平仄 + 与传统近体规则区分 + 轻声规则 + 多音字策略
│   ├── dui_and_nian.md     # 对/粘定义与简化检查法（含轻声 UNCERTAIN）
│   ├── jueju_patterns.md   # 五绝/七绝 × 4 式模板与检查顺序
│   ├── terminology.md      # 术语表
│   └── sources.md          # 来源与许可证记录
├── data/
│   ├── chars.json          # 读音表（V1.1：单一拼音来源构建，含全库审计统计）
│   ├── xinyun18.json / xinyun14.json / shisan13.json
├── scripts/
│   ├── syllable_parser.py  # V1.1 新增：单音节自足解析层（tone/initial/final/调号）
│   ├── prosody_core.py     # 确定性引擎（共享）
│   ├── check_char.py / check_rhyme.py / check_poem.py
│   ├── build_char_table.py # V1.1：单源 TONE3 构建 + 全库审计 + 可重复 hash
│   └── （__pycache__ 忽略）
└── tests/
    ├── test_prosody.py     # V1 保留测试（21 个）
    └── test_v1_1_suite.py  # V1.1 四层套件（56 个：unit/全库/回归/fixtures+边界样本）
```

## 版本记录

- v1.0（上一版）：五绝/七绝现代简化检查；数据链存在"双 Style 列表按下标配对"
  缺陷（第三方审计：227 条 tone 错位、195 条 final 错位）；MODERN_EAR 近韵过宽
  （大组笛卡尔积）；轻声在关键位被误判 FAIL；韵书判定写死十八韵；
  调号显示算法错误（海→haǐ）；"通用度"表述无数据依据。
- v1.1-rc2（本轮规则层修复，见 reports/poetry_skill_v1_1_rc2_fix_report.md）：
  ① strict profile 真正 strict：xinyun18/xinyun14/shisan13 不同部直接
     FAIL（十三辙/听感仅作辅助提示，不再把 FAIL 降级 WARN）；
  ② 首句入韵与正文(2/4)共用 judge_rhyme_pair 统一入口（modern-ear 不再
     fallback 到 b18）；
  ③ 移除全部“按文案字符串反推状态”（同韵 in info 等）→ 结构化
     status/relation/first_line_rhymes/message；对/粘判定同样布尔化；
  ④ 位置 override 越界 → POSITION_OVERRIDE_OUT_OF_RANGE（WARN，不静默）；
  ⑤ 非法/空 override → INVALID_READING_OVERRIDE + 该字 UNCERTAIN
     （不再写“已忽略”却偷偷 fallback）；
  ⑥ unmapped readings（32 条）文档表述勘误：包括 纯辅音叹词 n/ng/m/hm、
     yo（哟）、ê 系等特殊音节，一律 UNCERTAIN 不强行归部。
- v1.1（本版）：全部修复（详见 reports/poetry_skill_v1_1_fix_report.md）：
  ① 单音节解析层（拼音读音为唯一主键，杜绝跨 Style 配对）；
  ② chars.json 全库审计门禁（tone/final mismatch = 0）+ 可重复构建 hash；
  ③ NEAR 白名单 {(en,eng),(in,ing),(uen,ueng)}；
  ④ 轻声 = UNCERTAIN（关键位 WARN 不 FAIL；韵脚不判 PERFECT）；
  ⑤ --rhyme-profile xinyun18|xinyun14|shisan13|modern-ear（默认 xinyun18）；
  ⑥ 调号按标调规则 + 预组合字符（海→hǎi、小→xiǎo）；
  ⑦ DEFAULT_SOURCE = dictionary_order 表述 + 候选读音展示；
  ⑧ 位置级 --reading（行:列=拼音），优先级 位置 > 字 > 字典默认。
- 不含（下一版候选）：平水韵、词林正韵、入声体系、五律/七律、拗救、词牌、古今音切换、同韵部选字建议。
