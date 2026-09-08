# 现代韵：STRICT_XINYUN 与 MODERN_EAR

## 本项目押韵判定的两级模式

| 模式 | 含义 | V1.1 判定线 |
|---|---|---|
| STRICT_XINYUN | 按正式现代韵书判断（默认中华新韵·十八韵） | 同属十八韵一部 = PERFECT_RHYME；不同部 = NO_RHYME |
| MODERN_EAR | 面向现代普通话创作的听感辅助 | 同十三辙 = PERFECT_RHYME；**NEAR 仅来自显式白名单**（en/eng、in/ing、uen/ueng）；否则 NO_RHYME |
| 边界情况 | 轻声、无韵部数据的字 | 一律 **UNCERTAIN**（禁止猜测） |

## 韵书版本差异（重要）

同一对韵脚在不同韵书下可能结果不同，这是**韵书版本问题，不是诗的错误**：

- **窗 chuāng / 长 cháng**：十八韵、十四韵、十三辙均同部（十六唐/十唐/江阳）；但《平水韵》中窗属上平三江、长属下平七阳，**分属两部**。
- **eng / ong**（如 风/东）：十八韵分属十七庚、十八东（NO）；十四韵同属十一庚（PERFECT）；十三辙同属中东（PERFECT）。
- **e / o / uo**（如 歌/波）：十八韵分属三歌、二波（NO）；十四韵同属二波（PERFECT）；十三辙同属梭波（PERFECT）。

输出押韵结论时必须注明所依据的韵书/模式，避免跨版本混用造成误判。

## 韵书 profile 选择（V1.1）

`check_poem.py --rhyme-profile xinyun18|xinyun14|shisan13|modern-ear`（默认 **xinyun18**，保持与 V1 行为一致）。
- 现代白话创作若希望与听感/歌词通押习惯更贴近，可选用 **xinyun14**（eng/ing/ong/iong 合并为十一庚；e/o/uo 合并为二波）或 **shisan13 / modern-ear**（同辙即 PERFECT）。
- 硬判定完全跟随所选 profile；输出同时给出四线对照（十八韵/十四韵/十三辙/听感），方便跨版本核对。
- 争议性边界一律 WARN/UNCERTAIN，不假装确定。

## MODERN_EAR 的 NEAR_RHYME 显式白名单（V1.1 收紧，可审计）

NEAR_RHYME **只**来自以下三对"同主元音、仅前/后鼻音韵尾对立"的跨辙组合：

| 对 | 例 | 说明 |
|---|---|---|
| en / eng | 深 shēn / 生 shēng | 只差 -n/-ng，主元音相同 |
| in / ing | 心 xīn / 星 xīng | 同上 |
| uen / ueng | 春 chūn / 翁 wēng | 同上 |

V1.1 移除旧的"大组对大组"笛卡尔积（旧实现把 云/东、心/空、门/东 也判 NEAR，过宽）：
- 云(yún=ün)/东(dōng=ong) → **NO_RHYME**
- 心(xīn=in)/空(kōng=ong) → **NO_RHYME**
- 门(mén=en)/东(dōng=ong) → **NO_RHYME**
- an/ang、ian/iang、uan/uang、ün/iong 等跨辙组合 → 一律 **NO_RHYME**（主元音或介音差异显著；宁严勿松，不给"听感模式"注水）

i/ü 系（i:ü、ie:üe、ian:üan、in:ün）在十三辙同归一七辙，听感模式直接判 PERFECT，无需也不应出现在 NEAR 白名单。

NEAR_RHYME 用于"宽松创作可接受但需提醒"；严格韵书判定同时输出，二者不互相覆盖。

## 轻声与押韵

轻声字（如 的、了、么）无稳定韵母调值，不参与韵部归属：
- 数据表中轻声读法的 b18/b14/z13 一律为空；
- 韵脚若为轻声 → 判定 UNCERTAIN + WARN（建议改用实读或换字）。

## 韵母键约定

数据/代码统一使用"完整韵母（含韵头）"拼写键：
`a ia ua | o uo | e | ie üe | i u ü | er | ei uei | ai uai | ou iou | ao iao | an ian uan üan | en in uen ün | ang iang uang | eng ing ueng | ong iong | i_apical`

- `i_apical` = 舌尖元音 -i（zh/ch/sh/r/z/c/s 后的 i），pypinyin 对 知/字 的韵母都返回 `i`，须按声母区分（见 pingze.md）。
- `ü` 在 pypinyin 数据中写作 `v`（lv4），本项目内部与展示均转写为 `ü`（lǜ）。
- `uei/iou/uen` 为实际读音完整形（对应拼写 ui/iu/un）。
