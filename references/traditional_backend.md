# 传统韵书与词谱：独立后端接入

## 先选规则，再查字或验律

| 用户目标 | 入口 | 能证明什么 |
|---|---|---|
| 现代普通话五绝/七绝 | `check_poem.py`，选择 `xinyun18` / `xinyun14` 等 | 本项目现代简化规则内的 PASS/WARN/FAIL |
| 按平水韵查字、比较韵部 | `traditional_prosody.py --dict pingshui` | 外部字表的传统声类、韵部候选 |
| 按词林正韵查字、比较韵部 | `traditional_prosody.py --dict cilin` | 外部词韵字表的声类、韵部候选 |
| 查词牌、选词谱变体 | `traditional_prosody.py cipai` | 外部收录的句式、平仄和韵脚标记 |
| 按指定词牌检查词稿 | `traditional_prosody.py check-ci` | 供复核的外部匹配报告，始终 WARN，不认证整词合律 |

平水韵常用于传统近体诗，词林正韵常用于填词；词牌是句式与声律规范，不能用韵书代替。
同一词牌可能有多个变体，先查询再选择，不能假定都叫“定格”。
外部 `xinyun` 是上游韵书标识，不能当成原生 `xinyun18` 的别名。
现代新韵已有原生入口；不为让某一稿通过而偷偷换韵书或更换词谱。

## 安装及来源

可选后端为 [wb14123/rhyme-checker](https://github.com/wb14123/rhyme-checker)，
验证版本固定为 `388e6a6c1e6783a787a65338ef1584473884c59f`。
它独立安装、独立执行，不将其实现和字表复制进本仓库，也不改变原生离线现代引擎。
上游采用 GPL-3.0，其字表与词谱还有各自的来源，见 `sources.md`。

需要 Git 与 Rust/Cargo，已验证 Rust 1.90.0。以下命令从本仓库根目录运行：

```bash
python3 scripts/install_traditional_backend.py
```

云环境默认安装到 `/workspace/shared/poetry-tools`，其他环境默认个人数据目录。
可用 `--prefix` 选择仓库之外的目录。安装器使用固定提交与 `cargo build --locked`，
保留完整上游源码、LICENSE 和锁文件；遇到已有不同版本或工作区更改时停止，不覆盖。
安装器不安装 Rust，也不更改 shell 初始化文件。Rust 请通过其官方安装方式准备。

已安装其他位置的可执行文件可使用全局参数 `--backend /path/to/rhyme-checker`，
或环境变量 `RHYME_CHECKER_BIN`。自定义安装根目录可设置 `POETRY_TOOLS_DIR`。
外部程序是本地可执行代码，应只指向可信安装。未经兼容性验证的版本不能沿用本次验证结论。

## 命令

全局参数 `--dict`、`--backend`、`--json` 放在子命令之前。

```bash
# 平水韵：传统声类不是由现代普通话声调推导
python3 scripts/traditional_prosody.py --dict pingshui char 白
python3 scripts/traditional_prosody.py --dict pingshui rhyme 斜 家

# 先查谱及全部变体，再选择一个确切变体
python3 scripts/traditional_prosody.py --dict cilin cipai 如梦令
python3 scripts/traditional_prosody.py --dict cilin cipai 浣溪沙
python3 scripts/traditional_prosody.py --dict cilin cipai 定风波 --variant 定格

# 返回复核报告，预期 exit 1；不是安装失败，也不是诗稿 FAIL
python3 scripts/traditional_prosody.py --dict cilin --json check-ci \
  --ci-pai 如梦令 --variant 定格 \
  --poem '昨夜雨疏风骤，浓睡不消残酒。试问卷帘人，却道海棠依旧。知否，知否，应是绿肥红瘦。'
```

检查输入只放正文，不混入标题、作者或说明；保留正确分句。
不自动繁简转换，不将现代拼音 `--reading` 传入传统后端。上游接口不提供语境读音锁定；
返回多候选不代表每个候选都适合本句，不能让程序从候选中挑出“能过”的读法便声称语义正确。

## 输出与复核纪律

- 查字/词谱 `status=OK`、exit 0 只代表查询完成，不表示诗词合律。
- `SHARED_MEMBERSHIP` 只表示两个字有同名、同声类韵部候选，不保证当前语义下可以通押。
- 缺字、未找到确切词牌/变体、未安装后端、超时或接口不兼容 → `UNCERTAIN`、exit 1。
- `check-ci` 始终 `verdict=WARN`、`relation=EXTERNAL_REVIEW_REQUIRED`、exit 1。
  外部运行成功或匹配分数 1，都不能转换成原生引擎的 PASS。
- 安装/参数错误不应当被解读成诗稿的审美或格律缺陷。

接口返回后端来源、测试过的提交、字表缺字、多韵部候选、选定词谱与原始报告。
外部报告中的不匹配只作为待核查线索，不直接判定古人写错；需检查词谱版本、异体字、
多音多义、通押与数据覆盖，并保留无法确认的结论。

## 已执行的对照与已知限制

本次固定版本的实际结果：

| 对照 | 观察 |
|---|---|
| 平水韵查“白” | 入声十一陌，仄；与现代普通话的阳平分类不同 |
| 平水韵查“斜、家” | 均有六麻平声候选；原生新韵下分部不同 |
| 《如梦令·昨夜雨疏风骤》，定格 | 上游匹配分数 1；接口仍返回待复核，不假冒全面合律认证 |
| 《如梦令·常记溪亭日暮》，定格 | 上游对“日”提示平仄错，并缺“沉”的数据；不能据此自动修改原作 |
| 《浣溪沙·一曲新词酒一杯》，格一 | 上游对“台、来”提示韵脚不匹配；须核对通押与所用词韵，不能直接判原作出韵 |
| 《定风波·莫听穿林打叶声》，定格 | 上游对“醒、冷”提示韵脚不匹配；多组韵脚及换韵解释须进一步核查 |

这些观察正是接入目前保持“参考、待复核”的原因。尚未认证上游所有韵部及全部词谱的准确性。
本接口未新增传统五绝/七绝/五律/七律的整诗验证，未验证对仗、孤平、拗救、叠句等完整规则。
需要严格传统验收的任务应如实标记待复核，不能退回现代新韵检查后宣布传统规则通过。

学习到的设计：韵书与词谱分别选择、按字查声韵、先查变体再填词、通过确定性外部工具提供证据。
未采用的做法：凭匹配分数或进程退出码认证合律、自动将多音候选当语境实读、把未核验的字表直接并入核心数据。
