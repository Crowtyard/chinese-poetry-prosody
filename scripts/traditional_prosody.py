"""Optional, separate-process bridge to wb14123/rhyme-checker.

No upstream implementation or dictionary is included in this repository.
Lookups are external dictionary evidence, not a certificate of classical meter.
Upstream matching has a human-readable report and returns zero for mismatches;
therefore check-ci always requires review and never emits our native PASS.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


UPSTREAM = "https://github.com/wb14123/rhyme-checker"
TESTED_REVISION = "388e6a6c1e6783a787a65338ef1584473884c59f"
DICTIONARIES = ("pingshui", "cilin", "xinyun")


class BackendError(Exception):
    pass


def tools_dir():
    default = (Path("/workspace/shared/poetry-tools") if Path("/workspace").is_dir()
               else Path.home() / ".local/share/poetry-tools")
    return Path(os.environ.get("POETRY_TOOLS_DIR", default)).expanduser()


def find_backend(explicit=None):
    requested = explicit or os.environ.get("RHYME_CHECKER_BIN")
    if requested:
        found = shutil.which(str(Path(requested).expanduser()))
        if not found:
            raise BackendError("指定的 rhyme-checker 不存在或不可执行；请检查 --backend / RHYME_CHECKER_BIN。")
        return found
    found = shutil.which("rhyme-checker")
    if found:
        return found
    candidate = tools_dir() / "rhyme-checker/target/release/rhyme-checker"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    raise BackendError("未安装可选传统验律器；运行 scripts/install_traditional_backend.py，或设置 RHYME_CHECKER_BIN。")


class Backend:
    def __init__(self, executable, dictionary):
        self.executable = executable
        self.dictionary = dictionary
        self._cache = {}

    def run(self, *args):
        # An argv list keeps poem text out of the shell. --no-color is part of
        # the text interface contract, rather than a cosmetic preference.
        try:
            proc = subprocess.run(
                [self.executable, "--no-color", "--dict-type", self.dictionary, *args],
                capture_output=True, text=True, encoding="utf-8", timeout=30,
            )
        except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
            raise BackendError(f"外部命令无法完成：{exc}") from exc
        if proc.returncode:
            raise BackendError(f"外部命令失败（exit {proc.returncode}）：{proc.stderr.strip()}")
        if not proc.stdout.strip():
            raise BackendError("外部命令未返回报告，不能据此作出判断。")
        return proc.stdout.strip()

    def char(self, char):
        if char in self._cache:
            return self._cache[char]
        output = self.run("query-char-rhyme", char)
        memberships = []
        if output == f"未找到韵律信息: {char}":
            result = {"char": char, "memberships": [], "raw_output": output}
            self._cache[char] = result
            return result
        for line in output.splitlines():
            match = re.fullmatch(r"韵部: (.+), (平|仄)(?:, (.+))?", line.strip())
            if not match:
                raise BackendError("无法识别外部查字报告格式；请核对后端版本，不能猜测韵部。")
            name, tone, group = match.groups()
            item = {"name": name, "tone": tone, "group": group}
            if item not in memberships:
                memberships.append(item)
        result = {"char": char, "memberships": memberships, "raw_output": output}
        self._cache[char] = result
        return result


def parse_cipai(output):
    """Read only the published plain-text query protocol, fail on drift."""
    variants = []
    for block in re.split(r"\n={10,}\n", output):
        name = re.search(r"^词牌名：(.+)$", block, re.M)
        if not name:
            continue
        alias = re.search(r"^别名：(.+)$", block, re.M)
        variant = re.search(r"^变体：(.+)$", block, re.M)
        pattern = re.findall(r"^--- ?(.*)$", block, re.M)
        if not variant or not pattern:
            raise BackendError("外部词谱缺少变体或格律，不能作为检查依据。")
        for line in pattern:
            if not re.fullmatch(r"(?:[平仄中](?:（韵\d+）)?)*", line):
                raise BackendError("无法识别外部词谱符号；请核对后端版本。")
        variants.append({
            "name": name.group(1),
            "aliases": alias.group(1).split("、") if alias else [],
            "variant": variant.group(1),
            "pattern": pattern,
        })
    if not variants and "未找到词牌:" not in output:
        raise BackendError("无法识别外部词牌报告格式。")
    return variants


def query_cipai(backend, name, variant=None):
    # Fetch the title before filtering variants: upstream mislabels an unknown
    # variant as a missing title. Keep its full evidence and diagnose locally.
    output = backend.run("query-ci-pai", "--ci-pai", name)
    # Upstream uses substring matching. Do not silently select another title.
    matches = [v for v in parse_cipai(output)
               if name in [v["name"], *v["aliases"]]
               and (variant is None or variant == v["variant"])]
    return matches, output


def pattern_diagnostic(name, variant, matches, output):
    available = [v for v in parse_cipai(output) if name in [v["name"], *v["aliases"]]]
    result = {"requested_name": name, "requested_variant": variant,
              "available_variants": list(dict.fromkeys(v["variant"] for v in available))}
    if not available:
        result.update(code="CIPAI_NOT_FOUND", note=f"未找到确切词牌：{name}；未使用近似名称代替。")
    elif not matches:
        result.update(code="VARIANT_NOT_FOUND", note=f"词牌 {name} 存在，但未找到请求的变体：{variant}；未自动替换。")
    elif variant is not None and len(matches) != 1:
        result.update(code="VARIANT_AMBIGUOUS", note="未找到唯一的确切变体；未执行匹配。")
    return result


def make_report(args, backend):
    report = {
        "schema_version": 1, "action": args.command,
        "backend": "wb14123/rhyme-checker", "backend_path": backend.executable,
        "source": UPSTREAM, "tested_upstream_revision": TESTED_REVISION,
        "dictionary": args.dict, "status": "OK", "scope": "external_lookup_only",
    }
    if args.command == "char":
        report.update(backend.char(args.char))
        if not report["memberships"]:
            report["status"] = "UNCERTAIN"
    elif args.command == "rhyme":
        results = [backend.char(c) for c in args.chars]
        report["characters"] = results
        sets = [{(r["name"], r["tone"]) for r in x["memberships"]} for x in results]
        report["shared_memberships"] = [
            {"name": name, "tone": tone} for name, tone in sorted(sets[0] & sets[1])
        ]
        report["relation"] = ("UNCERTAIN" if not all(sets) else
                              "SHARED_MEMBERSHIP" if report["shared_memberships"] else
                              "NO_SHARED_MEMBERSHIP")
        report["note"] = "只比较外部字表中的同名同声韵部；多音多义须核对语境，不代表整诗合律或词谱允许通押。"
        if not all(sets):
            report["status"] = "UNCERTAIN"
    elif args.command == "cipai":
        matches, output = query_cipai(backend, args.name, args.variant)
        report.update(variants=matches, raw_output=output)
        report.update(pattern_diagnostic(args.name, args.variant, matches, output))
        if not matches:
            report["status"] = "UNCERTAIN"
    elif args.command == "check-ci":
        matches, output = query_cipai(backend, args.ci_pai, args.variant)
        report.update(scope="external_ci_review", status="UNCERTAIN", verdict="WARN",
                      relation="EXTERNAL_REVIEW_REQUIRED", pattern_output=output)
        report.update(pattern_diagnostic(args.ci_pai, args.variant, matches, output))
        if len(matches) != 1:
            return report
        report["selected_pattern"] = matches[0]
        # Missing entries must not be mistaken for wrong historical tones.
        chars = sorted(set(re.findall(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U000323af]", args.poem)))
        entries = [backend.char(char) for char in chars]
        report["missing_characters"] = [x["char"] for x in entries if not x["memberships"]]
        report["multiple_memberships"] = [x for x in entries if len(x["memberships"]) > 1]
        report["raw_output"] = backend.run(
            "match-ci-pai", "--ci-pai", args.ci_pai, "--variant", args.variant, "--", args.poem,
        )
        report["note"] = (
            "外部报告仅供复核：匹配分数、无错误标记或 exit 0 均不自动等于合律。"
            "先核对缺字、多音语义、词谱变体与典籍；不得因上游提示直接修改古人作品。"
            "本接口不作传统整诗 PASS 认证，也不检查审美、对仗或拗救。"
        )
    return report


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", help="独立安装的 rhyme-checker 可执行文件")
    ap.add_argument("--dict", choices=DICTIONARIES, default="cilin")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("char", help="查单字传统韵部").add_argument("char")
    sub.add_parser("rhyme", help="比较两个字的韵部候选交集").add_argument("chars", nargs=2)
    cp = sub.add_parser("cipai", help="查询确切词牌及其变体")
    cp.add_argument("name")
    cp.add_argument("--variant")
    check = sub.add_parser("check-ci", help="调用外部词谱匹配；结果必须复核，exit 1")
    check.add_argument("--ci-pai", required=True)
    check.add_argument("--variant", required=True)
    check.add_argument("--poem", required=True)
    return ap


def main(argv=None):
    ap = parser()
    args = ap.parse_args(argv)
    chars = [args.char] if args.command == "char" else args.chars if args.command == "rhyme" else []
    if any(len(c) != 1 for c in chars):
        ap.error("查字和韵部比较必须输入单字。")
    if args.command == "check-ci" and (not args.poem.strip() or len(args.poem) > 1000):
        ap.error("请输入不含标题的词正文（1–1000 字符）。")
    try:
        report = make_report(args, Backend(find_backend(args.backend), args.dict))
    except BackendError as exc:
        report = {"status": "UNCERTAIN", "code": "BACKEND_UNAVAILABLE_OR_INCOMPATIBLE",
                  "message": str(exc), "action": args.command}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"外部传统韵律接口｜{args.dict}｜{report['status']}")
        if "pattern_output" in report:
            print(report["pattern_output"])
        if "raw_output" in report:
            print(report["raw_output"])
        if args.command == "rhyme" and "characters" in report:
            for entry in report["characters"]:
                print(f"{entry['char']}：{entry['raw_output']}")
            print(f"候选关系：{report['relation']}；同部候选：{report['shared_memberships']}")
        if report.get("missing_characters"):
            print("外部字表缺字：" + "、".join(report["missing_characters"]))
        if report.get("multiple_memberships"):
            print("需按语境核对多候选：" + "、".join(x["char"] for x in report["multiple_memberships"]))
        print(report.get("note") or report.get("message") or "查询完成；这不是整诗合律结论。")
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
