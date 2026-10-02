"""qxfmt 命令行：roundtrip / compose / verify。用法见仓库 QUICKSTART.md。"""
import argparse
import os
import sys

from .container import Container
from .pbtree import roundtrip


def cmd_roundtrip(args):
    ok = True
    for p in args.files:
        try:
            c = Container.load(p)
            good = roundtrip(c.proto)
        except AssertionError as e:
            print(f"[FAIL] {os.path.basename(p)} 容器断言: {e}")
            ok = False
            continue
        verdict = "PASS" if good else "FAIL"
        print(f"[{verdict}] {os.path.basename(p)} type={c.file_type} proto={len(c.proto)}B")
        ok = ok and good
    return 0 if ok else 1


def cmd_compose(args):
    from .compose import Composer
    from .verify import verify_bytes
    comp = Composer(args.template)
    print(f"模板: {comp.info()}")
    if args.text is not None:
        comp.set_text(args.text)
    if args.name is not None:
        comp.set_name(args.name)
    if args.guid is not None:
        comp.set_guid(args.guid)
    out = comp.build()
    n = out.save(args.output)
    verdict, msgs = verify_bytes(out.to_bytes())
    for m in msgs:
        print("  " + m)
    print(f"[{verdict}] 输出 {args.output} ({n}B)")
    return 0 if verdict != "ERROR" else 1


def cmd_verify(args):
    from .verify import verify_file
    ok = True
    for p in args.files:
        verdict, msgs = verify_file(p, args.catalog, args.universe)
        for m in msgs:
            print(("  " if verdict == "PASS" else "SICK " if not m.startswith("WARN")
                   and verdict == "SICK" else "  ") + m)
        print(f"[{verdict}] {os.path.basename(p)}")
        ok = ok and verdict == "PASS"
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="qxfmt", description="千星奇域文件格式工具链")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("roundtrip", help="容器与树往返验证（修改前的合法性前提）")
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_roundtrip)

    p = sub.add_parser("compose", help="模板手术合成图文件")
    p.add_argument("-t", "--template", required=True, help="模板 .gis 文件")
    p.add_argument("-o", "--output", required=True, help="输出 .gis 文件")
    p.add_argument("--text", help="替换打印节点的文本")
    p.add_argument("--name", help="替换图名（注意：对已有图的改名会导致导入拒收，docs/25 §3）")
    p.add_argument("--guid", type=lambda s: int(s, 0), help="替换图 guid（如 0x40000030）")
    p.set_defaults(fn=cmd_compose)

    p = sub.add_parser("verify", help="格式规则校验（kind5/泛型信封/信封完整）")
    p.add_argument("files", nargs="+")
    p.add_argument("--catalog", help="可选：引脚目录 JSON（启用泛型槽检查）")
    p.add_argument("--universe", help="可选：kernel 宇宙 JSON（启用未知 kernel WARN）")
    p.set_defaults(fn=cmd_verify)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
