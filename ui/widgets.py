# -*- coding: utf-8 -*-
"""回响回廊 - UI 控件：剧情框、选择菜单、文字输入框。"""

import pygame
from . import theme as T


class Dialog(object):
    """剧情对话框，逐字显示。lines: [(说话人, 文本), ...]"""

    def __init__(self, lines, on_done=None, title=None):
        self.lines = list(lines)
        self.idx = 0
        self.chars = 0
        self.on_done = on_done
        self.title = title
        self.done = False

    @property
    def cur(self):
        return self.lines[self.idx] if self.idx < len(self.lines) else ("", "")

    def advance(self):
        who, txt = self.cur
        if self.chars < len(txt):
            self.chars = len(txt)
            return
        self.idx += 1
        self.chars = 0
        if self.idx >= len(self.lines):
            self.done = True
            if self.on_done:
                self.on_done()

    def update(self, dt):
        who, txt = self.cur
        if self.chars < len(txt):
            self.chars = min(len(txt), self.chars + dt * 0.045)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (
                pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.advance()
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.advance()
            return True
        return False

    def draw(self, surf):
        if self.done:
            return
        w, h = surf.get_size()
        box = pygame.Rect(60, h - 210, w - 120, 170)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 8, 7, 175))
        surf.blit(overlay, (0, 0))
        T.panel(surf, box, T.PANEL, T.LINE)
        who, txt = self.cur
        y = box.y + 16
        if who:
            T.text(surf, who, box.x + 20, y, 19, T.GOLD, bold=True)
            y += 30
        shown = txt[:int(self.chars)]
        for line in T.wrap(shown, 19, box.w - 44):
            T.text(surf, line, box.x + 20, y, 19, T.INK)
            y += 27
        T.text(surf, "空格继续  (%d/%d)" % (self.idx + 1, len(self.lines)),
               box.right - 18, box.bottom - 28, 14, T.FAINT, right=True)


class Menu(object):
    """通用竖排选择菜单。items: [(标签, 副标签, 值), ...]"""

    def __init__(self, title, items, on_pick, on_cancel=None, note=None):
        self.title = title
        self.items = items
        self.sel = 0
        self.on_pick = on_pick
        self.on_cancel = on_cancel
        self.note = note
        self.done = False

    def handle(self, ev):
        if ev.type != pygame.KEYDOWN:
            return False
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % max(1, len(self.items))
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % max(1, len(self.items))
        elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            if self.items:
                self.on_pick(self.items[self.sel][2])
        elif ev.key == pygame.K_ESCAPE:
            self.done = True
            if self.on_cancel:
                self.on_cancel()
        elif pygame.K_1 <= ev.key <= pygame.K_9:
            i = ev.key - pygame.K_1
            if i < len(self.items):
                self.sel = i
                self.on_pick(self.items[i][2])
        return True

    def draw(self, surf):
        if self.done:
            return
        w, h = surf.get_size()
        rows = max(1, len(self.items))
        bh = 120 + rows * 40 + (44 if self.note else 0)
        box = pygame.Rect(w // 2 - 250, h // 2 - bh // 2, 500, bh)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 8, 7, 180))
        surf.blit(overlay, (0, 0))
        T.panel(surf, box, T.PANEL, T.LINE)
        T.text(surf, self.title, box.centerx, box.y + 16, 21, T.GOLD, bold=True,
               center=True)
        y = box.y + 58
        if self.note:
            for line in T.wrap(self.note, 15, box.w - 40)[:2]:
                T.text(surf, line, box.x + 20, y, 15, T.DIM)
                y += 21
            y += 6
        for i, (label, sub, _v) in enumerate(self.items):
            r = pygame.Rect(box.x + 14, y, box.w - 28, 34)
            if i == self.sel:
                pygame.draw.rect(surf, T.PANEL_HI, r, border_radius=3)
                pygame.draw.rect(surf, T.BRONZE, r, 1, border_radius=3)
            T.text(surf, label, r.x + 12, r.y + 8, 17,
                   T.INK if i == self.sel else T.DIM)
            if sub:
                T.text(surf, sub, r.right - 12, r.y + 9, 15,
                       T.GOLD if i == self.sel else T.FAINT, right=True)
            y += 40
        T.text(surf, "↑↓ 选择   回车 确定   Esc 取消",
               box.centerx, box.bottom - 30, 14, T.FAINT, center=True)


class Prompt(object):
    """全屏模态文字输入（自己吃原始事件，因为 Menu 的按键路由拿不到 unicode）。"""

    def __init__(self, title, on_ok, on_cancel=None, hint=""):
        self.title = title
        self.buf = ""
        self.on_ok = on_ok
        self.on_cancel = on_cancel
        self.hint = hint
        self.done = False

    def handle(self, ev):
        if ev.type == pygame.TEXTINPUT:
            self.buf += ev.text
            return True
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_BACKSPACE:
                self.buf = self.buf[:-1]
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.done = True
                self.on_ok(self.buf.strip())
            elif ev.key == pygame.K_ESCAPE:
                self.done = True
                if self.on_cancel:
                    self.on_cancel()
            elif ev.unicode and ev.unicode.isprintable() and \
                    pygame.version.vernum[0] < 2:
                # pygame2 会同时发 TEXTINPUT，再吃一次 unicode 就重复了
                self.buf += ev.unicode
            return True
        return False

    def draw(self, surf):
        if self.done:
            return
        w, h = surf.get_size()
        box = pygame.Rect(w // 2 - 230, h // 2 - 80, 460, 160)
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((10, 8, 7, 185))
        surf.blit(overlay, (0, 0))
        T.panel(surf, box, T.PANEL, T.LINE)
        T.text(surf, self.title, box.centerx, box.y + 16, 20, T.GOLD, bold=True,
               center=True)
        field = pygame.Rect(box.x + 24, box.y + 62, box.w - 48, 38)
        T.panel(surf, field, (16, 14, 12), T.LINE, 3)
        T.text(surf, self.buf + "_", field.x + 10, field.y + 9, 19, T.INK)
        if self.hint:
            T.text(surf, self.hint, box.centerx, box.bottom - 32, 14, T.FAINT,
                   center=True)
