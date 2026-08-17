# -*- coding: utf-8 -*-
"""《回响回廊》视觉基调：湿石头、青铜、和一点点灯火。

配色刻意压得暗——因为这个游戏一半时间你是看不见路的。
真正亮起来的只有两样东西：你脚下那一圈光，和右上角剩余步数。
"""

import os
import pygame

BG        = (14, 16, 19)
PANEL     = (23, 27, 32)
PANEL_HI  = (33, 39, 46)
LINE      = (52, 60, 70)
INK       = (222, 228, 233)
DIM       = (128, 140, 152)
FAINT     = (78, 88, 99)

STONE     = (96, 104, 116)    # 墙（看得见时）
STONE_MEM = (48, 53, 60)      # 墙（只在记忆里）
GROUND    = (28, 32, 38)
GROUND_MEM = (17, 19, 23)

FLAME     = (226, 158, 74)
BRONZE    = (176, 141, 87)
MOSS      = (98, 152, 118)
ICEC      = (132, 178, 206)
BLOOD     = (198, 84, 78)
VOID      = (10, 11, 13)
GOLD      = (222, 188, 108)
GOOD      = (124, 184, 128)
WARN      = (222, 170, 80)

CELL = 30
WIN_W, WIN_H = 1240, 706

_FC = {}
_FP = None

CJK = ["msyh", "microsoftyaheiui", "microsoftyahei", "simhei", "simsun",
       "dengxian", "pingfangsc", "stheiti", "hiraginosansgb",
       "notosanscjksc", "notosanscjk", "wenquanyimicrohei",
       "wenquanyizenhei", "arialunicodems", "dejavusans"]


def _find():
    global _FP
    if _FP is not None:
        return _FP
    for n in CJK:
        try:
            p = pygame.font.match_font(n)
        except Exception:
            p = None
        if p:
            _FP = p
            return p
    for d in (r"C:\Windows\Fonts", "/usr/share/fonts", "/Library/Fonts",
              "/System/Library/Fonts"):
        if not os.path.isdir(d):
            continue
        for root, _ds, fs in os.walk(d):
            for fn in fs:
                lo = fn.lower()
                if lo.startswith(("msyh", "simhei", "simsun", "notosanscjk",
                                  "wqy", "dejavusans")) and lo.endswith(
                        (".ttf", ".ttc", ".otf")):
                    _FP = os.path.join(root, fn)
                    return _FP
    _FP = ""
    return ""


def font(size, bold=False):
    k = (size, bold)
    if k in _FC:
        return _FC[k]
    p = _find()
    try:
        f = pygame.font.Font(p, size) if p else pygame.font.Font(None, size)
    except Exception:
        f = pygame.font.Font(None, size)
    try:
        f.set_bold(bold)
    except Exception:
        pass
    _FC[k] = f
    return f


def text(surf, s, x, y, size=17, color=INK, bold=False, center=False,
         right=False):
    img = font(size, bold).render(str(s), True, color)
    r = img.get_rect()
    if center:
        r.midtop = (x, y)
    elif right:
        r.topright = (x, y)
    else:
        r.topleft = (x, y)
    surf.blit(img, r)
    return r


def wrap(s, size, width):
    f = font(size)
    out = []
    for para in str(s).split("\n"):
        line = ""
        for ch in para:
            if f.size(line + ch)[0] > width and line:
                out.append(line)
                line = ch
            else:
                line += ch
        out.append(line)
    return out


def panel(surf, rect, fill=PANEL, border=LINE, radius=4):
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, 1, border_radius=radius)


def bar(surf, x, y, w, h, frac, color, back=(38, 43, 50)):
    pygame.draw.rect(surf, back, (x, y, w, h), border_radius=2)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        pygame.draw.rect(surf, color, (x, y, int(w * frac), h), border_radius=2)


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))
