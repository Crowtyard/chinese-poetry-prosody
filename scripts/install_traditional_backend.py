"""Install a pinned optional GPL tool outside this checkout, retaining source.

Requires Git and Rust/Cargo (tested with Rust 1.90.0). Does not install Rust or
change profiles, PATH, repository source, dictionaries, or lockfiles.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from traditional_prosody import TESTED_REVISION, UPSTREAM, tools_dir


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, **kwargs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", type=Path, default=tools_dir())
    ap.add_argument("--jobs", type=int, default=2)
    args = ap.parse_args(argv)
    if args.jobs < 1:
        ap.error("--jobs 必须至少为 1")
    prefix = args.prefix.expanduser().resolve()
    checkout = prefix / "rhyme-checker"
    own_root = Path(__file__).resolve().parents[1]
    if prefix == own_root or own_root in prefix.parents:
        ap.error("请安装在本仓库之外，保持第三方源码与许可证独立。")
    if not shutil.which("git"):
        ap.error("需要 Git。")
    local_cargo = prefix / "cargo/bin/cargo"
    cargo = shutil.which("cargo") or (str(local_cargo) if local_cargo.is_file() else None)
    if not cargo:
        ap.error("需要 Rust/Cargo；已验证 Rust 1.90.0。请从 https://rustup.rs 安装，或将 cargo 加入 PATH。")
    prefix.mkdir(parents=True, exist_ok=True)
    if not checkout.exists():
        run(["git", "clone", "--no-checkout", UPSTREAM + ".git", str(checkout)])
        run(["git", "-C", str(checkout), "checkout", "--detach", TESTED_REVISION])
    # Never reset someone else's checkout, untracked files or local commits.
    origin = run(["git", "-C", str(checkout), "remote", "get-url", "origin"], capture_output=True).stdout.strip()
    head = run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True).stdout.strip()
    dirty = run(["git", "-C", str(checkout), "status", "--porcelain"], capture_output=True).stdout.strip()
    if origin.rstrip("/").removesuffix(".git") != UPSTREAM or head != TESTED_REVISION or dirty:
        ap.error("安装位置已有不同来源、版本或工作区改动；未覆盖。请改用新的 --prefix。")
    build_env = os.environ.copy()
    build_env["CARGO_TARGET_DIR"] = str(checkout / "target")
    if (prefix / "cargo").is_dir():
        build_env["CARGO_HOME"] = str(prefix / "cargo")
    if (prefix / "rustup").is_dir():
        build_env["RUSTUP_HOME"] = str(prefix / "rustup")
    run([cargo, "build", "--release", "--locked", "--jobs", str(args.jobs)],
        cwd=checkout, env=build_env)
    executable = checkout / "target/release/rhyme-checker"
    result = run([str(executable), "--no-color", "--dict-type", "pingshui", "query-char-rhyme", "白"],
                 capture_output=True)
    if "仄" not in result.stdout:
        raise RuntimeError("传统字音功能检查失败；请检查上游输出。")
    print(f"已安装独立后端：{executable}")
    print(f"固定版本：{TESTED_REVISION}；保留源码和 LICENSE：{checkout}")
    print("查字已验证。词谱匹配仍须人工复核，不等于传统整诗合律认证。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"安装失败：{exc}", file=sys.stderr)
        sys.exit(1)
