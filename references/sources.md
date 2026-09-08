# 来源与许可证记录（可审计）

本 Skill 的代码与数据均**未复制任何不兼容许可证项目的代码**。逐项记录如下：

## 数据

| 组件 | 来源 | 许可证 | 使用方式 |
|---|---|---|---|
| 汉字读音表 data/chars.json | 由 pypinyin 0.55.0 生成（mozillazg/python-pinyin） | **MIT** | 生成离线 JSON（scripts/build_char_table.py 一次性构建，构建时间记录在 chars.json meta 中）；运行时不再依赖 pypinyin |
| 韵部/辙口划分表 | 中华新韵·十八韵（1941 教育部公布，分部与《诗韵新编》一致）、中华新韵·十四韵（中华诗词学会 2005 试行简表）、十三辙（北方曲艺通押辙口） | 公共韵书/通行规则（事实性数据） | 自行整理为 data/*.json 与 prosody_core.py 中 F18/F14/Z13 表 |

## 参考项目（仅借鉴思想，未复制代码/数据）

| 项目 | 许可证 | 借鉴内容 | 未采用的原因 |
|---|---|---|---|
| wb14123/rhyme-checker（Rust CLI + Claude Skill，支持平水韵/词林正韵/中华新韵/词牌格律） | **GPL-3.0** | ① "SKILL.md 薄包装 + 外部确定性 CLI"的分工模式（LLM 不当检测器）；② 韵部↔字双索引的数据组织思想；③ 多韵书参数切换设计 | rhyme-checker 采用 GPL-3.0。为避免在本项目的分发与衍生实现中引入 GPL-3.0 所附带的许可义务，本项目未复制其代码或数据，仅参考其架构与设计思想（其韵部数据 README 注明源自 charlesix59/chinese_word_rhyme，未核验许可，亦未采用） |
| Wscats/poetry-skills（Prompt-based 诗词生成/查询 Skill，MIT，数据为 chinese-poetry 语料约 291MB + strains 平仄标注） | **MIT** | ① SKILL.md front matter 的 activation trigger 写法（但其为 Claude 规范，本项目遵循本机 Kun Skill 规范：id/name/description）；② 认识到"strains 语料 + LLM 参考"模式 | 其格律判断最终仍由 LLM 完成（与"LLM 不当检测器"原则冲突）；291MB 语料对"规则验证"不是必需品；V1 不需要语料检索能力 |

## 决策：为什么 V1 采用"自有 Python 引擎 + 离线数据"

1. **确定性**：押韵/平仄/粘对是可计算规则 → 用数据+程序验证，杜绝 LLM 判断漂移（用户任务第十二节的工程原则）。
2. **许可处理**：核心数据来自 pypinyin（MIT）；韵书为公共事实数据；GPL-3.0 项目仅作思想参考并记录来源，未复制其代码或数据，以避免在本项目分发与衍生实现中引入 GPL-3.0 许可义务。
3. **离线自洽**：chars.json 一次构建后，运行时零依赖（不需要 python 包/网络/外部 CLI），SKILL 使用成本低。
4. **职责分离**：诗人人设负责审美创作，Skill 负责规则验证；LLM 只解释报告并据报告修改诗句。

## 语音学边界声明

- 本数据基于现代普通话读音；pypinyin 字典内读音顺序为 dictionary_order（底层字典返回顺序），**不声称与《现代汉语词典》词频或注音次序一致**；个别字（生僻/异读）可能有差异。凡数据缺失、轻声或无法映射的韵母一律报 UNCERTAIN，不猜测。
- 斜、骑等字**不采用古读**（xiá/jì），严格按现代普通话（xié/qí）——这是本项目"现代普通话创作系统"的既定基准。
