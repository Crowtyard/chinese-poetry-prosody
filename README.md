# Chinese Poetry Prosody

中文诗律 Skill —— 面向 AI Agent / LLM 中文诗歌创作工作流的**确定性现代诗律检查器**。

> **核心原则：「LLM 负责创作，程序负责验律。」**
> 诗人人设负责诗意、意象、诗脉与语言；本工具负责拼音、声调、平仄、韵部、押韵、相对、相粘与整诗扫描。
> 所有底层判定由数据 + 程序确定性计算，LLM 只解释结果并修改诗句。

## 功能

- 现代普通话拼音（带调号显示）
- 声调（1–4 声 + 轻声）
- 简化平仄（1/2 声 = 平，3/4 声 = 仄；轻声不归平仄 → UNCERTAIN）
- 中华新韵·十八韵（STRICT_XINYUN 默认）
- 中华新韵·十四韵
- 十三辙（MODERN_EAR 听感线）
- MODERN_EAR 近韵白名单（en/eng、in/ing、uen/ueng）
- 五言绝句 / 七言绝句 整诗扫描
- 联内相对（关键位第 2、4〔6〕字）
- 联间相粘（第 2/3 句关键位同类）
- 韵脚检查（第 2、4 句必查，首句入韵判定与正文同一判定入口）
- 多音字 override（`--reading 字=拼音`）
- 位置级 override（`--reading 行:列=拼音`，同字不同位置不同读音）
- 轻声关键位 → UNCERTAIN / WARN（不硬塞平仄、不误判 FAIL）
- 韵脚轻声 → 不直接判 PERFECT_RHYME
- 完整诗歌扫描报告（PASS / WARN / FAIL，结构化 status/relation）

## 安装

仅需要 **Python 3.10+**（标准库，无第三方运行期依赖）。数据文件已随仓库提供：

```bash
git clone <repo-url>
cd chinese-poetry-prosody
# 无需 pip install；直接运行 scripts/ 下的 CLI
```

> `data/chars.json` 由 `scripts/build_char_table.py` 依据 pypinyin（MIT）生成，
> 已在仓库内提供确定性产物（含全库一致性审计统计），运行时零外部依赖。

## 使用方法

所有命令在 Skill 根目录执行（Windows 用 `py` 代替 `python3`）：

```bash
# 1) 单字音韵查询（候选读音全部列出；默认读音标注 DEFAULT_SOURCE=dictionary_order）
python3 scripts/check_char.py 城
python3 scripts/check_char.py 长

# 2) 韵脚比较（可切韵书）
python3 scripts/check_rhyme.py 声 城
python3 scripts/check_rhyme.py 风 东 --profile xinyun14

# 3) 整诗扫描（五绝/七绝）
python3 scripts/check_poem.py --poem "客舍秋灯暗，风来透纸窗。开门霜满地，路向晓山长。" --reading 长=chang2
python3 scripts/check_poem.py --poem "……" --rhyme-profile xinyun14
python3 scripts/check_poem.py --poem "……" --reading 4:5=chang2   # 位置级 override
```

CLI 退出码：`0=PASS，1=WARN/UNCERTAIN，2=FAIL`。

## Rhyme Profiles

`--rhyme-profile` 可切换判定韵书（默认 **xinyun18**，与历史版本行为一致）：

| profile | 含义 | 备注 |
|---|---|---|
| `xinyun18` | 中华新韵·十八韵（1941 公布，分部与《诗韵新编》一致） | 默认；严格判定（不同部 = FAIL） |
| `xinyun14` | 中华新韵·十四韵（中华诗词学会 2005 试行简表） | eng/ing/ong/iong 合并为十一庚等；现代白话创作可选 |
| `shisan13` | 十三辙（北方曲艺通押辙口） | 同辙 = PERFECT |
| `modern-ear` | MODERN_EAR 听感模式 | PERFECT→PASS、NEAR→WARN、NO→FAIL |

**严格语义**：`xinyun18/xinyun14/shisan13` 的主判定完全由所选韵书决定；
十三辙/MODERN_EAR 只作为辅助提示显示，不改变判定。
所有押韵判定（第 2/4 句、首句入韵）共用同一入口，全诗规则一致。

> ⚠️ **本项目使用现代普通话简化诗律体系，不是传统近体诗学的完整替代。**
> 不含入声体系、不按《平水韵》分部；分析古体/古人作品时请勿套用本工具规则。

## 数据与确定性

- `data/chars.json`：36,808 条读音（26,704 汉字），每条含
  `py/tone/final/pz/b18/b14/z13`；全库一致性审计
  `tone_mismatch=0、final_mismatch=0`（`python3 scripts/build_char_table.py --check` → GATE: PASS）。
- 构建方式：单一拼音来源（pypinyin TONE3）+ 自足解析层
  `scripts/syllable_parser.py`，不存在跨 Style 列表配对（历史数据错位缺陷已修复）。
- 可重复构建：连续两次构建内容 hash 一致。
- 无法可靠判定（轻声、无数据、特殊音节）→ 一律 `UNCERTAIN`，禁止猜测。

## Known Limitations

- 生僻字（超出内置读音表）→ UNCERTAIN；`--reading` 只能在已有候选读音中选择，
  不能为完全未知字符新增读音。
- 约 32 条无法映射到现有韵部的特殊音节（纯辅音叹词 n/ng/m/hm、yo、ê 系等）→ UNCERTAIN，不强行归韵。
- 多音字默认取底层字典第一候选（dictionary_order，非词频/语境最优），
  语境读音不同时仍需 `--reading`（字级或位置级）。
- 暂不支持：平水韵、词林正韵、五律/七律、拗救、词牌、古今音切换。
- 轻声在现代简化平仄中无法稳定二分：关键位 → UNCERTAIN/WARN（如实报告而非假装确定）。

## Credits / Sources

- 汉字读音数据：**pypinyin**（MIT License, https://github.com/mozillazg/python-pinyin）——
  仅用于构建期生成离线数据，运行时无依赖。
- 架构参考：**wb14123/rhyme-checker**（GPL-3.0, https://github.com/wb14123/rhyme-checker）——
  为避免在分发与衍生实现中引入 GPL-3.0 许可义务，本项目**未复制其代码或数据**，
  仅参考其"确定性 CLI + Skill 薄包装"架构与设计思想。
- 设计对照：**Wscats/poetry-skills**（MIT, https://github.com/Wscats/poetry-skills）——
  Prompt-based 诗词技能参考；本项目明确不采用"LLM 充当格律检测器"的模式。
- 韵书/辙口为公共事实数据：中华新韵·十八韵（1941）、中华新韵·十四韵
  （中华诗词学会 2005 试行简表）、十三辙（北方曲艺通押辙口）。
- 详细来源与许可记录见 `references/sources.md`。

## License

本仓库暂未选择开源许可证（No License）。第三方依赖及其来源许可如上所述；
是否开源及采用何种许可证由作者后续决定。
