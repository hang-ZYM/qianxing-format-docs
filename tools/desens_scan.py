#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脱敏扫描器：按 desens_manifest.json 的禁止模式清单机械检查仓库文本。

遍历仓库（默认为脚本所在仓库根），对每个文本文件逐行匹配清单中声明的禁止
模式；任何命中即打印报告（文件 / 行号 / 模式 / 行预览）并以退出码 1 结束，
零命中退出码 0，清单或参数问题退出码 2。

设计约束：
- 模式清单与扫描器解耦——本文件不含任何具体模式，清单全部来自 manifest；
- 只扫文本：按 NUL 字节嗅探判定二进制文件并跳过（清单可再按扩展名排除）；
- 默认排除版本库内部目录、依赖与编译产物目录，以及 manifest 自身。

用法：
    python tools/desens_scan.py [根目录] [--manifest 清单路径] [--quiet]

典型接入（发布前人工执行或 CI 挂钩）：
    python tools/desens_scan.py && git commit ...
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Tuple

# 扫描器自带的目录级默认排除（与 manifest 的 exclude_dirs 取并集）
DEFAULT_EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}
DIR_SUFFIX_EXCLUDES = (".egg-info", ".egg-info/")
BINARY_SNIFF_BYTES = 8192
PREVIEW_MAX = 120

Pattern = dict  # {"id", "category", "match": Callable[[str], bool]}


def config_error(msg: str) -> "SystemExit":
    print(f"[desens] 配置错误：{msg}", file=sys.stderr)
    return SystemExit(2)


def load_manifest(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise config_error(f"无法读取清单 {path}：{exc}")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise config_error(f"清单 {path} 不是合法 UTF-8 JSON：{exc}")
    if not isinstance(data, dict) or not isinstance(data.get("patterns"), list):
        raise config_error(f"清单 {path} 缺少 patterns 数组")
    if not data["patterns"]:
        raise config_error(f"清单 {path} 的 patterns 为空——拒绝空清单运行")
    return data


def compile_patterns(entries: list) -> List[Pattern]:
    compiled: List[Pattern] = []
    for idx, ent in enumerate(entries, 1):
        if not isinstance(ent, dict):
            raise config_error(f"第 {idx} 条模式不是对象")
        pid = ent.get("id") or f"PAT-{idx:02d}"
        pat = ent.get("pattern")
        if not pat or not isinstance(pat, str):
            raise config_error(f"模式 {pid} 缺少字符串 pattern 字段")
        ci = bool(ent.get("ci", True))
        if ent.get("regex"):
            try:
                rx = re.compile(pat, re.IGNORECASE if ci else 0)
            except re.error as exc:
                raise config_error(f"模式 {pid} 正则不合法：{exc}")

            def match(line: str, _rx=rx) -> bool:
                return _rx.search(line) is not None
        elif ci:
            needle = pat.casefold()

            def match(line: str, _n=needle) -> bool:
                return _n in line.casefold()
        else:
            needle = pat

            def match(line: str, _n=needle) -> bool:
                return _n in line
        compiled.append({"id": pid, "category": ent.get("category", ""), "match": match})
    return compiled


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(BINARY_SNIFF_BYTES)
    except OSError:
        return True  # 读不了的一律当不可扫文本跳过
    return b"\x00" in chunk


def iter_candidate_files(root: Path, scan_cfg: dict, manifest_path: Path) -> Iterator[Tuple[Path, str, str]]:
    """产出 (路径, 相对 posix 路径, 类别)，类别为 text / binary / excluded。"""
    exclude_dirs = set(scan_cfg.get("exclude_dirs", [])) | DEFAULT_EXCLUDE_DIRS
    exclude_globs = [g for g in scan_cfg.get("exclude_globs", []) if isinstance(g, str)]
    exclude_files = set(scan_cfg.get("exclude_files", []))

    def dir_excluded(name: str) -> bool:
        return name in exclude_dirs or name.endswith(DIR_SUFFIX_EXCLUDES)

    def file_excluded(rel_posix: str, name: str) -> bool:
        if rel_posix in exclude_files:
            return True
        return any(fnmatch.fnmatch(rel_posix, g) or fnmatch.fnmatch(name, g) for g in exclude_globs)

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not dir_excluded(d))
        for name in sorted(filenames):
            fpath = Path(dirpath) / name
            rel = fpath.relative_to(root).as_posix()
            if fpath.resolve() == manifest_path.resolve() or file_excluded(rel, name):
                yield fpath, rel, "excluded"
                continue
            yield fpath, rel, ("binary" if is_binary(fpath) else "text")


def scan_file(fpath: Path, patterns: List[Pattern]) -> List[Tuple[str, int, str]]:
    """返回 [(模式 id, 行号, 行预览)]；读取失败返回 [("READ-ERROR", 0, 原因)]。"""
    try:
        text = fpath.read_bytes().decode("utf-8-sig", errors="replace")
    except OSError as exc:
        return [("READ-ERROR", 0, str(exc))]
    hits: List[Tuple[str, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for p in patterns:
            if p["match"](line):
                preview = line.strip()
                if len(preview) > PREVIEW_MAX:
                    preview = preview[: PREVIEW_MAX - 3] + "..."
                hits.append((p["id"], lineno, preview))
    return hits


def main(argv: Optional[List[str]] = None) -> int:
    try:  # Windows 控制台编码兜底：预览行可能含任意字符
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description="按禁止模式清单机械扫描仓库文本（脱敏双扫）")
    ap.add_argument("root", nargs="?", default=str(here.parent.parent), help="仓库根目录（默认：脚本所在仓库）")
    ap.add_argument("--manifest", default=str(here.parent / "desens_manifest.json"), help="禁止模式清单路径")
    ap.add_argument("--quiet", action="store_true", help="只输出统计与命中，不逐文件报进度")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    manifest_path = Path(args.manifest).resolve()
    if not root.is_dir():
        raise config_error(f"根目录不存在：{root}")
    manifest = load_manifest(manifest_path)
    patterns = compile_patterns(manifest["patterns"])

    n_text = n_binary = n_excluded = 0
    all_hits: List[Tuple[str, str, int, str]] = []
    for fpath, rel, kind in iter_candidate_files(root, manifest.get("scan", {}), manifest_path):
        if kind == "excluded":
            n_excluded += 1
            continue
        if kind == "binary":
            n_binary += 1
            continue
        n_text += 1
        for pid, lineno, preview in scan_file(fpath, patterns):
            all_hits.append((rel, pid, lineno, preview))

    if not args.quiet:
        print(f"[desens] 根目录：{root}")
        print(f"[desens] 清单：{manifest_path}（{len(patterns)} 条禁止模式）")
        print(f"[desens] 扫描文本文件 {n_text} 个；按清单排除/按嗅探跳过二进制 {n_excluded + n_binary} 个")

    if all_hits:
        print(f"[desens] 命中 {len(all_hits)} 处，禁止发布：")
        for rel, pid, lineno, preview in all_hits:
            print(f"  {rel}:{lineno}  [{pid}]  {preview}")
        by_id: dict = {}
        for _, pid, _, _ in all_hits:
            by_id[pid] = by_id.get(pid, 0) + 1
        print("[desens] 按模式统计：" + ", ".join(f"{k}×{v}" for k, v in sorted(by_id.items())))
        return 1

    print("[desens] 零命中——当前内容通过脱敏检查。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
