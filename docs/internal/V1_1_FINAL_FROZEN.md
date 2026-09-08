# chinese-poetry-prosody v1.1.0 Final —— 冻结记录

> **V1_1_FINAL_FROZEN = TRUE**（冻结时间 2026-09-08）
> 前置冻结均未回写：BASELINE_FROZEN=TRUE、RC1_FROZEN=TRUE、RC2_FROZEN=TRUE
> 归档：`<SKILL_DIR>/chinese-poetry-prosody-v1.1-final/`（与最终工作副本逐字节一致，仅多本文件）

## 1. 版本

- SKILL.md front matter `version: 1.1.0`（Final；rc2 为 1.1.0-rc2，仅版本号/标题变更）
- 本轮为 **Final Polish**：未修改任何核心算法/数据（详见第 4 节）

## 2. 归档独立验证（在归档目录内执行）

- `py -m unittest discover -s tests -p "test_*.py"` → **Ran 121 tests … OK（121/121）**
  - test_prosody.py 21 ＋ test_v1_1_suite.py 56 ＋ test_rc2_suite.py 33 ＋ test_final_polish_suite.py 11
- `py scripts/build_char_table.py --check` → **GATE: PASS**
  （tone_mismatch=0、final_mismatch=0、invalid_tone=0、unmapped_final=32 全部 UNCERTAIN，readings_total=36808）

## 3. 核心数据指纹（与 rc1/rc2 对照）

| 文件 | sha256 | 相对 rc2 |
|---|---|---|
| data/chars.json | 745cda31b9c98be86fe31b6e98b2126561f25d067b4f61020e45a31cdf4f6161 | **未变** |
| data/shisan13.json | 8ccb099e934df348414d38bbadfa29c5198cd8e46218d18cce5356bf0fa4b9b5 | 未变 |
| data/xinyun14.json | c25cc41100ab1e39ad327faa920380d46dfb50f2ee09d3edd4a40b4aded14d02 | 未变 |
| data/xinyun18.json | 20f541fa0468efa7b434d56afa09392cde6ea4655315b4d1f77e45f14770de24 | 仅 examples 修正（河→三歌、夜→四皆；finals/F18 未动） |
| scripts/prosody_core.py | 738599dcb1f4732ae0870bd8982f0ea1358f26c1612df870dcd355eebcc6c6a5 | **未变（核心算法零改动）** |

chars.json 内容级：chars_sha256=e69ae471…、meta_sha256=de054921…（与 rc1/rc2 一致）

## 4. Final Polish 修改清单（仅限本轮允许范围）

1. check_char：未知字/UNCERTAIN → CLI exit 1（contract：0=PASS、1=WARN/UNCERTAIN、2=FAIL）
2. check_char：unknown char 提示改为“不能通过 --reading 为完全未知字符新增读音”（不再给出不真实的提示）
3. xinyun18.json examples：河(二波)→三歌；夜(三歌)→四皆（仅展示数据；finals 与核心映射未动）
4. 文档卫生：轻声旧表述、dictionary_order 表述（pingze.md 一处）、GPL 措辞（sources.md 两处）、unmapped 描述复查——全部收敛为正式表述
5. SKILL.md：version 1.1.0-rc2 → 1.1.0（Final），标题同步
6. 新增 tests/test_final_polish_suite.py（11 个用例：CLI exit code、xinyun18 examples 归属与自洽、文档卫生静态扫描、发布路径卫生）

## 5. 受控文件 sha256（21 个）

（见本文件末尾清单；第三方验收时对 `<SKILL_DIR>/chinese-poetry-prosody-v1.1-final/` 逐文件 sha256sum 核对）

## 6. 第三方验收口径

1. 逐文件 sha256 对照第 5 节清单；
2. 归档内独立运行第 2 节两条命令；
3. CLI contract 抽查：`check_char 城`→exit 0；`check_char 𠮷`→UNCERTAIN+exit 1；
4. 核心回归 9 项（基线诗 PASS；风/东 18→FAIL 14→PASS 13→PASS ear→PASS；失粘/失对/出韵 FAIL；轻声关键位 WARN；INVALID_READING_OVERRIDE；POSITION_OVERRIDE_OUT_OF_RANGE）；
5. 修复报告：`reports/poetry_skill_v1_1_final_release_report.md`；README：GitHub repo 根。

## 7. 文件清单

```
745cda31b9c98be86fe31b6e98b2126561f25d067b4f61020e45a31cdf4f6161 data/chars.json
8ccb099e934df348414d38bbadfa29c5198cd8e46218d18cce5356bf0fa4b9b5 data/shisan13.json
c25cc41100ab1e39ad327faa920380d46dfb50f2ee09d3edd4a40b4aded14d02 data/xinyun14.json
20f541fa0468efa7b434d56afa09392cde6ea4655315b4d1f77e45f14770de24 data/xinyun18.json
243929b17c0514000dd09be7ce77c83eaa0af42accccef02e17829d94f0ec93b references/dui_and_nian.md
50ad6a24220aee2622e8c5ffe6b7fc9dae4129693206dbc89916930d7a20dad9 references/jueju_patterns.md
50d1cff3b70569ec880db2d50f46f6d123629290b7f338b3e0aba4417e0921cc references/modern_rhyme.md
d6ac0cacf23b92f282ce6b1b1b058b7f7040e86bce62d8f0d538dc230812487b references/pingze.md
9462461b7e10e8f51419a7c92322b8d6e3dc410f82bec3fe79f493d6153c498b references/sources.md
a86bdae699454dc267c19565d38a7458464cf685c5a844bfddf5b64d8a4cfe59 references/terminology.md
eefd8a71cd140779b5698704ceed8e1b4fd97e672784d0a0e5c35c611c255f99 scripts/build_char_table.py
2298427a566ea5544dbb11f43e5110ffcd906c44dfa3cc04551d5ded6a349a16 scripts/check_char.py
34365846f7275c96f417da6939e6fda6bf801330c2c92aaa4a10b7838b98e979 scripts/check_poem.py
f82b03a5fbda41aa0b2c8b618c900de313f56cb02e3cc72a0b3834dd066ad7fc scripts/check_rhyme.py
738599dcb1f4732ae0870bd8982f0ea1358f26c1612df870dcd355eebcc6c6a5 scripts/prosody_core.py
2acf90213ad929f9bb1f627279bcd80d1139d855ce3253a28676db4d18c4685b scripts/syllable_parser.py
b7a5348607632027e0431f42b06547eb5490a4b0bb8d1b431862e1cd424c2497 SKILL.md
73d42c1943aa838ad085eb719a5ff6a1a15f041d222fb5b4e43eb85e2a1adbdb tests/test_final_polish_suite.py
fc799645d1348044f6e4f6f73a9244014badff6c0d0b2ddba9794af674de8f45 tests/test_prosody.py
84991c978169fae09ba58fb0a9822b2f8d16a6a4e8a86491ce06350577cf932a tests/test_rc2_suite.py
c9f2a618d238945fff7431327efd71c5cb6135936b481b85586b1dfa1600b83e tests/test_v1_1_suite.py
```

---
**V1_1_FINAL_FROZEN = TRUE —— Final 冻结完成，等待第三方最终验收。**
