# Verification

中文诗律 Skill 的验证体系与历史验收状态（面向第三方独立审计）。

## 自动测试

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

| 套件 | 数量 | 内容 |
|---|---|---|
| test_prosody.py | 21 | V1 保留（单字/押韵/整诗/失粘失对出韵/模板式名） |
| test_v1_1_suite.py | 56 | V1.1：解析层单元、全库一致性审计（36,808 readings）、第三方反例回归、11 fixtures、22 边界样本 |
| test_rc2_suite.py | 33 | rc2：strict profile、首句统一入口、字符串陷阱、override 越界/非法、回归 |
| test_final_polish_suite.py | 11 | Final：CLI exit code、xinyun18 examples 归属与自洽、文档卫生静态扫描 |
| **合计** | **121** | `Ran 121 tests … OK` |

## 数据层门禁

```bash
python3 scripts/build_char_table.py --check
# GATE: PASS
```

- tone_mismatch = 0、final_mismatch = 0、invalid_tone = 0（36,808 readings）
- unmapped_final = 32：纯辅音叹词（n/ng/m/hm）、yo、ê 系等特殊音节 → 一律 UNCERTAIN
- chars.json 内容级 hash：chars=e69ae471…、meta=de054921…（可重复构建一致）

## 核心回归样本（CLI）

| 样本 | 期望 |
|---|---|
| 基线诗《秋夜驿宿》（舍=she4、长=chang2） | PASS |
| 风/东 押韵诗：xinyun18 / xinyun14 / shisan13 / modern-ear | FAIL / PASS / PASS / PASS |
| 故意失粘 / 故意失对 / 故意出韵 | FAIL（定位到句与关键位） |
| 轻声在关键位 | WARN（RELATION=UNCERTAIN） |
| `--reading 长=zhang3x` | INVALID_READING_OVERRIDE + UNCERTAIN |
| `--reading 9:9=chang2` | POSITION_OVERRIDE_OUT_OF_RANGE |
| `check_char 城` / `check_char 𠮷` | exit 0 / UNCERTAIN + exit 1 |

## 验收状态时间线

- v1 基线（无 Skill 裸跑）：BASELINE_FROZEN=TRUE（2026-09-08）
- v1.1-rc1：数据层第三方验收 DATA_LAYER_VERIFIED=TRUE；规则层问题移交 rc2
- v1.1-rc2：第二轮第三方验收（数据/规则/核心引擎通过），遗留 Final Polish 项
- v1.1.0 Final：Final Polish 完成，V1_1_FINAL_FROZEN=TRUE（本仓库）
- **VERIFIED 最终标定权在第三方独立复验**（复验口径见 docs/internal/V1_1_FINAL_FROZEN.md）

## 修复历史（摘要）

- v1.1：数据构建"双 Style 列表按下标配对"错位（227 tone / 195 final 错位）→ 单一拼音来源 + 自足解析层；MODERN_EAR 大组笛卡尔积过宽 → 三对白名单；轻声 FAIL → UNCERTAIN；调号显示、dictionary_order 表述、位置级 override。
- rc2：strict profile 被听感降级 → 真正 strict；modern-ear 首句 fallback b18 → 统一判定入口；"同韵 in message"字符串反推状态 → 结构化 status/relation；override 越界/非法静默 → 显式 code 诊断。
- Final：check_char UNCERTAIN exit code 0→1；unknown char 提示修正；xinyun18 examples 两处归属修正（河→三歌、夜→四皆）；文档卫生收敛。
