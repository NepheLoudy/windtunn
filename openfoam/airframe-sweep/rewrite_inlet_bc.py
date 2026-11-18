#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 patch 名精确改写来流边界值 (替换 clone_case 的 sed 字符串匹配 — 格式无关)。

背景 (2026-11-18): 热启动时场取自收敛时间目录, OpenFOAM 写盘用紧凑格式
(`uniform (-19.9239 0 -1.74311)`), 与模板 6 位小数格式不同 → 旧 sed 的
"旧值字符串替换" 失配, 静默把边界留在旧 V。本工具按 patch 定位, 不依赖数值文本。

只改 inlet/outlet/side 的 **uniform** 项:
  - inlet  : value uniform ...        (fixedValue)
  - outlet : inletValue uniform ...   (inletOutlet)  — value 可能是 nonuniform(壁函数结果), 不动
  - side   : inletValue uniform ...   同上
其它 patch (body_*/fin_* 壁面) 一律不动。

用法:
  rewrite_inlet_bc.py <field_file> U <ux> <uy> <uz>
  rewrite_inlet_bc.py <field_file> scalar <val>
退出码: 0=成功且至少改 1 处; 1=未匹配到任何可改项 (视为失败, 由调用方回退)
"""
import re
import sys

PATCHES = ("inlet", "outlet", "side")


def patch_blocks(text):
    """yield (patch_name, start, end) — 仅 4 空格缩进的顶格 patch 段。"""
    for m in re.finditer(r"(?m)^ {4}([A-Za-z_][\w]*)\s*$", text):
        name = m.group(1)
        # 找该 patch 的块体：从名字行开始，到下一个 4 空格缩进的 patch 名 或 顶格 '}' 
        nxt = re.search(r"(?m)^(?: {4}[A-Za-z_][\w]*\s*$|\})", text[m.end():])
        end = m.end() + (nxt.start() if nxt else len(text) - m.end())
        yield name, m.start(), end


def rewrite(fname, kind, new):
    text = open(fname, encoding="utf-8").read()
    n_changed = 0
    out = []
    last = 0
    if kind == "U":
        pat = re.compile(r"uniform\s*\(\s*[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s*\)")
        repl = "uniform (%s %s %s)" % tuple(new)
    else:
        # 只换 "uniform <纯数字>" (排除 uniform List<...> / 表达式)
        pat = re.compile(r"uniform\s+[-+0-9.eE]+(?![\w<])")
        repl = "uniform %s" % new[0]

    # ① 冷启动时 internalField 是 uniform 初值 → 一并换 (与旧 sed 行为一致);
    #    热启动时 internalField 是 nonuniform 收敛场 → 不匹配, 天然保留
    m = re.search(r"internalField\s+uniform", text)
    if m:
        seg_end = text.find(";", m.end())
        if seg_end > 0:
            seg = text[m.start():seg_end + 1]
            newseg, k = pat.subn(repl, seg)
            if k:
                n_changed += k
                out.append(text[:m.start()])
                out.append(newseg)
                last = seg_end + 1

    # ② inlet/outlet/side 的 uniform 项
    for name, s, e in patch_blocks(text):
        if name not in PATCHES:
            continue
        if s < last:      # 已被 ① 覆盖的区域跳过 (不会发生, internalField 在 boundaryField 之前)
            continue
        block = text[s:e]
        newblock, k = pat.subn(repl, block)
        if k:
            n_changed += k
            out.append(text[last:s])
            out.append(newblock)
            last = e
    if not n_changed:
        return 0
    out.append(text[last:])
    open(fname, "w", encoding="utf-8").write("".join(out))
    return n_changed


def verify(fname, kind, new):
    """复核: inlet 段内第一个 uniform 项必须等于新值。"""
    text = open(fname, encoding="utf-8").read()
    for name, s, e in patch_blocks(text):
        if name != "inlet":
            continue
        block = text[s:e]
        if kind == "U":
            m = re.search(r"uniform\s*\(\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)",
                          block)
            if not m:
                return False, "inlet 无 uniform 矢量"
            got = [float(x) for x in m.groups()]
            want = [float(x) for x in new]
            ok = all(abs(a - b) <= 1e-6 * max(1.0, abs(b)) for a, b in zip(got, want))
            return ok, "inlet=%s want=%s" % (got, want)
        else:
            m = re.search(r"uniform\s+([-+0-9.eE]+)(?![\w<])", block)
            if not m:
                return False, "inlet 无 uniform 标量"
            return abs(float(m.group(1)) - float(new[0])) <= 1e-6 * max(1.0, abs(float(new[0]))), \
                "inlet=%s want=%s" % (m.group(1), new[0])
    return False, "未找到 inlet patch"


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    fname, kind = sys.argv[1], sys.argv[2]
    if kind == "U":
        if len(sys.argv) != 6:
            print("U 需要 3 个分量")
            return 2
        new = sys.argv[3:6]
    elif kind == "scalar":
        new = [sys.argv[3]]
    else:
        print("kind 必须是 U 或 scalar")
        return 2
    n = rewrite(fname, kind, new)
    if n == 0:
        print("REWRITE_MISS 未匹配到可改项: %s" % fname)
        return 1
    ok, msg = verify(fname, kind, new)
    if not ok:
        print("VERIFY_FAIL %s (%s)" % (fname, msg))
        return 1
    print("rewrote %d 处 (%s)" % (n, msg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
