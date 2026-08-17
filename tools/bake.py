# -*- coding: utf-8 -*-
"""扫种子、验收、把合格的关卡烤进 core/baked.py。

筛子按"便宜的排前面"：先求最短解（A*，毫秒级），再看步数落没落在区间里，
再跑贪心/贴墙（快），最后才跑 15 次盲探（慢）和道具必需性检查。
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import gen
from core.solver import solve, analyze


def bake(budget=260, verbose=True):
    out = []
    t0 = time.time()
    for ch in gen.CHAPTERS:
        for idx in range(ch["levels"]):
            cfg = gen.level_cfg(ch["id"], idx)
            lo, hi = cfg["par"]
            found = None
            tried = 0
            for k in range(budget):
                seed = ch["id"] * 100003 + idx * 7919 + k * 131
                tried = k + 1
                try:
                    lv = gen.build(seed, cfg)
                except Exception:
                    continue
                par, _path = solve(lv)
                if par is None or not (lo <= par <= hi):
                    continue
                limit = int(math.ceil(par * cfg["slack"]))
                lv.meta["limit"] = limit
                rep = analyze(lv, limit,
                              need_dumb_fail=cfg["need_dumb"],
                              need_items=cfg["need_items"],
                              need_depth=cfg["need_depth"],
                              max_explore=cfg["max_explore"])
                if rep["ok"]:
                    found = (seed, par, limit, rep)
                    break
            if found is None:
                print("!! %d-%d 没烤出来（试了 %d 个种子）" % (ch["id"], idx + 1, tried))
                continue
            seed, par, limit, rep = found
            out.append(dict(ch=ch["id"], idx=idx, seed=seed, par=par,
                            limit=limit, explore=rep["explore_rate"],
                            depth=rep["depth"], tight=rep["tight"],
                            nodmg=rep["par_nodamage"]))
            if verbose:
                print("%d-%d seed=%d par=%d limit=%d 盲探成功率=%.0f%% "
                      "机关动作=%d (试了%d个种子)"
                      % (ch["id"], idx + 1, seed, par, limit,
                         rep["explore_rate"] * 100, rep["depth"], tried))
    print("烤完 %d 关，用时 %.1fs" % (len(out), time.time() - t0))
    return out


def write(out, path=None):
    path = path or os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "core", "baked.py")
    lines = ["# -*- coding: utf-8 -*-",
             '"""自动生成，不要手改。tools/bake.py 烤出来的关卡种子表。',
             "",
             "每一项都通过了：有解 / 步数落在本章区间 / 贪心与贴墙法过不去 /",
             "盲目探路的一次通关率低于本章阈值 / 该用的道具确实非用不可。",
             '"""', "", "LEVELS = ["]
    for r in out:
        lines.append("    dict(ch=%d, idx=%d, seed=%d, par=%d, limit=%d,"
                     " explore=%.3f, depth=%d, tight=%.3f, nodmg=%s),"
                     % (r["ch"], r["idx"], r["seed"], r["par"], r["limit"],
                        r["explore"], r["depth"], r["tight"], r["nodmg"]))
    lines.append("]")
    lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("已写入", path)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 260
    write(bake(n))
