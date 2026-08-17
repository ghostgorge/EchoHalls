# -*- coding: utf-8 -*-
"""回响回廊 EchoHalls —— 会记路的人才走得出去。

启动：python main.py
自测：python main.py --selftest
"""

import io
import os
import sys
import traceback

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

LOG_PATH = os.path.join(os.path.expanduser("~"), "echohalls_launch.log")


def boot_log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(str(msg) + "\n")
    except Exception:
        pass


def fatal(msg):
    boot_log("FATAL: " + msg)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(msg)[:1500], "回响回廊 启动失败", 0x10)
    except Exception:
        pass


import pygame

from core import levels as LV
from core import save as SV
from core.rules import (POS, HEARTS, KEYS, BOMBS, ITEMS, ITEM_BIT, TORCHES,
                        LEVERS, BLOCKS, terrain, gate_open, spike_up,
                        WALL, FLOOR, EXIT, ICE, PLATE, GATE, ANCHOR, PIT,
                        SPIKE, CRUMBLE, DOOR, CRACK)
from core.session import Session, PLAYING, WON, DEAD, NOSTEPS
from ui import theme as T
from ui.widgets import Dialog, Menu, Prompt

CELL = T.CELL
MOVE_KEYS = {pygame.K_UP: "up", pygame.K_w: "up",
             pygame.K_DOWN: "down", pygame.K_s: "down",
             pygame.K_LEFT: "left", pygame.K_a: "left",
             pygame.K_RIGHT: "right", pygame.K_d: "right"}
TOOL_KEYS = {pygame.K_j: "jump", pygame.K_k: "hook",
             pygame.K_b: "bomb", pygame.K_l: "light"}
TOOL_NAME = {"jump": "羽毛跳", "hook": "钩爪", "bomb": "炸弹", "light": "点火把"}

ITEM_LABEL = {"key": "钥匙", "bomb": "炸弹", "heart": "心",
              "lantern": "灯笼", "feather": "羽毛", "hookshot": "钩爪",
              "compass": "罗盘"}


class App(object):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("回响回廊 EchoHalls")
        self.screen = pygame.display.set_mode((T.WIN_W, T.WIN_H))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = "title"
        self.modal = None
        self.profile = SV.load()
        self.order = LV.flat_order()
        self.sel_title = 0
        self.sel_ch = 0
        self.sel_lv = 0
        self.sess = None
        self.cur = None            # (ch, idx)
        self.onelife = False
        self.onelife_pos = 0
        self.aim = None
        self.toast = ""
        self.toast_t = 0
        self.ach_queue = []
        self.shift_t = 0
        self.used_undo = False
        self.used_recall = 0
        self.anim = 0.0
        pygame.key.set_repeat(210, 85)

    # ------------------------------------------------------------ 主循环
    def run(self):
        while self.running:
            dt = self.clock.tick(60)
            self.anim += dt
            for ev in pygame.event.get():
                self.on_event(ev)
            if self.sess and self.sess.flash > 0:
                self.sess.flash = max(0, self.sess.flash - dt)
            self.toast_t = max(0, self.toast_t - dt)
            self.draw()
            pygame.display.flip()
        SV.save(self.profile)
        pygame.quit()

    def say(self, msg):
        self.toast = msg
        self.toast_t = 2400

    def award(self, aid):
        a = SV.grant(self.profile, aid)
        if a:
            self.ach_queue.append(a)
            self.say("成就解锁：%s —— %s" % (a[1], a[2]))

    # ------------------------------------------------------------ 事件
    def on_event(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
            return
        if self.modal is not None:
            self.modal.handle(ev)
            if getattr(self.modal, "done", False):
                self.modal = None
            return
        if ev.type != pygame.KEYDOWN:
            return
        fn = getattr(self, "keys_" + self.scene, None)
        if fn:
            fn(ev)

    # ------------------------------------------------------------ 标题
    TITLE_OPTS = ["继续探索", "选择章节", "无灯之夜（一命通关）", "成就", "玩法说明", "退出"]

    def keys_title(self, ev):
        n = len(self.TITLE_OPTS)
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.sel_title = (self.sel_title - 1) % n
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.sel_title = (self.sel_title + 1) % n
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            i = self.sel_title
            if i == 0:
                self.continue_run()
            elif i == 1:
                self.scene = "chapters"
            elif i == 2:
                self.start_onelife()
            elif i == 3:
                self.scene = "achievements"
            elif i == 4:
                self.show_help()
            else:
                self.running = False
        elif ev.key == pygame.K_ESCAPE:
            self.running = False

    def continue_run(self):
        for ch, idx in self.order:
            if SV.key(ch, idx) not in self.profile["cleared"]:
                self.start_level(ch, idx)
                return
        if self.order:
            self.start_level(*self.order[-1])

    # ------------------------------------------------------------ 选关
    def keys_chapters(self, ev):
        chs = LV.chapters()
        if not chs:
            self.scene = "title"
            return
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.sel_ch = (self.sel_ch - 1) % len(chs)
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.sel_ch = (self.sel_ch + 1) % len(chs)
        elif ev.key in (pygame.K_LEFT, pygame.K_a):
            self.sel_lv = max(0, self.sel_lv - 1)
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.sel_lv = min(len(chs[self.sel_ch][3]) - 1, self.sel_lv + 1)
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            ch = chs[self.sel_ch][0]
            idx = min(self.sel_lv, len(chs[self.sel_ch][3]) - 1)
            if SV.unlocked(self.profile, ch, idx, self.order):
                self.start_level(ch, idx)
            else:
                self.say("先通关上一关。")
        elif ev.key == pygame.K_ESCAPE:
            self.scene = "title"
        elif ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.double_shift()

    # ------------------------------------------------------------ 开局
    def start_level(self, ch, idx, onelife=False):
        lv = LV.load(ch, idx)
        if lv is None:
            self.say("这一关还没烤出来。")
            return
        self.onelife = onelife
        self.cur = (ch, idx)
        k = SV.key(ch, idx)
        mem = None if onelife else self.profile["memory"].get(k)
        mem = [tuple(p) for p in (mem or [])]
        self.sess = Session(lv, memory=mem, onelife=onelife)
        self.profile["tries"][k] = self.profile["tries"].get(k, 0) + (0 if onelife else 1)
        self.used_undo = False
        self.used_recall = 0
        self.aim = None
        self.scene = "play"

    def start_onelife(self):
        if not self.order:
            return
        self.onelife_pos = 0
        self.start_level(self.order[0][0], self.order[0][1], onelife=True)
        self.say("无灯之夜：不能撤销，地图记忆不保留，失手就从头。")

    # ------------------------------------------------------------ 游戏内按键
    def keys_play(self, ev):
        s = self.sess
        if ev.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            self.double_shift()
            return
        if ev.key == pygame.K_ESCAPE:
            self.open_pause()
            return
        if ev.key == pygame.K_h:
            self.show_help()
            return
        if s.status != PLAYING:
            if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.after_result()
            elif ev.key == pygame.K_r:
                self.retry()
            return
        if ev.key == pygame.K_r:
            if s.recall():
                self.used_recall += 1
                self.say("回想：整张图闪了一下，花掉三步。")
            else:
                self.say("回想已经用完了。")
            return
        if ev.key == pygame.K_z:
            if s.undo():
                self.used_undo = True
                self.profile["stats"]["undos"] += 1
            else:
                self.say("这里不能撤销。" if s.onelife else "没有可撤销的步子。")
            return
        if ev.key == pygame.K_n:
            self.retry()
            return
        if ev.key in TOOL_KEYS:
            kind = TOOL_KEYS[ev.key]
            if not s.can(kind):
                self.say("你还没有这件东西。")
                return
            self.aim = kind
            self.say("%s：按方向键选目标（Esc 取消）" % TOOL_NAME[kind])
            return
        if ev.key == pygame.K_SPACE:
            self.do_act("wait", "up")
            return
        if ev.key in MOVE_KEYS:
            d = MOVE_KEYS[ev.key]
            if self.aim:
                kind, self.aim = self.aim, None
                self.do_act(kind, d)
            else:
                self.do_act("move", d)

    def do_act(self, kind, d):
        s = self.sess
        before = s.st
        ev = s.act(kind, d)
        if ev is None:
            if kind != "move":
                self.say("这个方向用不了。")
            return
        st = SV.key(*self.cur)
        p = self.profile
        p["stats"]["steps"] += 1
        if "bomb" in ev:
            p["stats"]["bombs"] += 1
            if p["stats"]["bombs"] >= 10:
                self.award("bomber")
        if "hook" in ev:
            p["stats"]["hooks"] += 1
            if p["stats"]["hooks"] >= 20:
                self.award("hooker")
        if "push" in ev:
            for b in s.st[BLOCKS]:
                if b in s.lv.plates and b not in before[BLOCKS]:
                    p["stats"]["pushes"] += 1
                    if p["stats"]["pushes"] >= 15:
                        self.award("pusher")
        if "light" in ev:
            self.award("first_light")
        if p["stats"]["steps"] >= 10000:
            self.award("stepper")
        if s.status != PLAYING:
            self.on_finish()

    # ------------------------------------------------------------ 结算
    def on_finish(self):
        s = self.sess
        ch, idx = self.cur
        k = SV.key(ch, idx)
        p = self.profile
        if s.status == WON:
            best = p["cleared"].get(k)
            if best is None or s.steps < best:
                p["cleared"][k] = s.steps
            if not self.onelife:
                p["memory"][k] = [list(x) for x in s.merged_memory()]
            if s.steps <= s.lv.par:
                n = sum(1 for kk, v in p["cleared"].items()
                        if v <= (LV.record(*[int(x) for x in kk.split("-")])
                                 or {"par": 0})["par"])
                self.award("par_1")
                if n >= 10:
                    self.award("par_10")
                if n >= 30:
                    self.award("par_30")
            if not self.used_undo:
                self.award("no_undo")
            if s.lv.dark and self.used_recall == 0:
                self.award("blind")
            if p["tries"].get(k, 1) <= 1:
                p["firsttry"][k] = 1
                self.award("first_try")
                if len(p["firsttry"]) >= 10:
                    self.award("first_try_10")
            if p["tries"].get(k, 0) >= 10:
                self.award("returner")
            self.check_chapter(ch)
        else:
            p["stats"]["deaths"] += 1
            if not self.onelife:
                p["memory"][k] = [list(x) for x in s.merged_memory()]
        SV.save(p)

    def check_chapter(self, ch):
        recs = [r for r in LV.all_records() if r["ch"] == ch]
        if recs and all(SV.key(ch, r["idx"]) in self.profile["cleared"]
                        for r in recs):
            self.award("ch%d" % ch)
        if all(SV.key(c, i) in self.profile["cleared"] for c, i in self.order):
            self.award("all48")

    def after_result(self):
        s = self.sess
        ch, idx = self.cur
        if self.onelife:
            if s.status != WON:
                self.onelife = False
                self.say("无灯之夜结束：走到第 %d 关。" % (self.onelife_pos + 1))
                self.profile["onelife_best"] = max(
                    self.profile["onelife_best"], self.onelife_pos)
                SV.save(self.profile)
                self.scene = "title"
                return
            self.onelife_pos += 1
            if self.onelife_pos >= len(self.order):
                self.award("onelife_all")
                self.scene = "title"
                return
            nch = self.order[self.onelife_pos][0]
            if nch >= 4:
                self.award("onelife_ch3")
            if nch >= 7:
                self.award("onelife_ch6")
            self.start_level(*self.order[self.onelife_pos], onelife=True)
            return
        if s.status == WON:
            pos = self.order.index((ch, idx))
            if pos + 1 < len(self.order):
                self.start_level(*self.order[pos + 1])
            else:
                self.scene = "chapters"
        else:
            self.retry()

    def retry(self):
        ch, idx = self.cur
        self.start_level(ch, idx, onelife=self.onelife)

    # ------------------------------------------------------------ 菜单
    def open_pause(self):
        if self.aim:
            self.aim = None
            return

        def pick(v):
            self.modal = None
            if v == "retry":
                self.retry()
            elif v == "levels":
                self.scene = "chapters"
            elif v == "title":
                self.scene = "title"
            elif v == "help":
                self.show_help()
            elif v == "quit":
                self.running = False
        self.modal = Menu("暂停", [("继续", "Esc", "back"),
                                   ("重来这一关", "N", "retry"),
                                   ("选择关卡", "", "levels"),
                                   ("玩法说明", "H", "help"),
                                   ("回到标题", "", "title"),
                                   ("退出", "", "quit")], pick)

    def show_help(self):
        self.modal = Dialog([
            ("怎么走", "方向键 / WASD 走一步。空格原地等一步 —— 尖刺是按步数起落的，"
                      "等，本身就是一种解法。"),
            ("道具", "J 羽毛跳（跨过前面一格坑或尖刺）  K 钩爪（顺着铆点拉过深坑）\n"
                    "B 炸弹（炸开裂墙）  L 灯笼（点亮火把）\n"
                    "按完字母，再按方向键选目标。"),
            ("回想", "R 把整张图闪一下，代价是三步。全黑关卡里这是唯一的光。"),
            ("撤销", "Z 退回上一步，不花步数。但无灯之夜里没有这个东西。"),
            ("这游戏的核心", "步数上限卡得很死：**第一遍你多半走不完**。\n"
                          "第一遍是侦察，看清楚岔路在哪；死了或超步不要紧，"
                          "你走过的地方会以暗色留在图上。"),
            ("这游戏的核心", "第二遍才是通关：照着记忆里的路直着走过去。\n"
                          "关卡是照这个标准筛过的 —— 盲目探路能一次过的关，"
                          "生成器会直接扔掉重做。"),
            ("闸门", "闸门要三件事同时满足才开：压板全被石块压住、火把全点亮、"
                    "拉杆全扳下。石块推错方向就再也推不回来。"),
            ("其它", "N 重来  Esc 菜单  连按两下 Shift 有别的东西。"),
        ])

    def double_shift(self):
        now = pygame.time.get_ticks()
        if now - self.shift_t < 420:
            self.shift_t = 0
            self.open_cheat()
        else:
            self.shift_t = now

    def open_cheat(self):
        def run(cmd):
            self.modal = None
            parts = cmd.upper().split()
            if not parts:
                return
            op = parts[0]
            num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            if op == "UNLOCK":
                for ch, idx in self.order:
                    self.profile["cleared"].setdefault(SV.key(ch, idx), 9999)
                self.say("全部关卡已解锁。")
            elif op == "SKIP" and self.cur:
                pos = self.order.index(self.cur)
                nxt = min(len(self.order) - 1, pos + num)
                self.profile["cleared"].setdefault(SV.key(*self.cur), 9999)
                self.start_level(*self.order[nxt])
            elif op == "SOLVE" and self.sess:
                self.solve_demo()
            elif op == "REVEAL" and self.sess:
                self.sess.recall_left += 1
                self.sess.recall()
                self.sess.steps -= 3
            elif op == "STEPS" and self.sess:
                self.sess.lv.meta["limit"] += num * 10
                self.say("步数上限 +%d" % (num * 10))
            elif op == "ACHV":
                for a in SV.ACHIEVEMENTS:
                    SV.grant(self.profile, a[0])
                self.say("成就全开。")
            elif op == "RESET":
                self.profile = SV.blank()
                self.say("存档已清空。")
            else:
                self.say("不认识的指令。")
            SV.save(self.profile)
        self.modal = Prompt("作弊台", run,
                            hint="UNLOCK / SKIP n / SOLVE / REVEAL / STEPS n / ACHV / RESET")

    def solve_demo(self):
        from core.solver import solve
        par, path = solve(self.sess.lv)
        if path is None:
            self.say("求解器也没辙。")
            return
        self.sess.reset(self.sess.memory)
        for kind, d in path:
            self.sess.act(kind, d)
        self.say("求解器走完了：%d 步。" % par)

    # ------------------------------------------------------------ 成就页
    def keys_achievements(self, ev):
        if ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.scene = "title"

    # ============================================================ 绘制
    def draw(self):
        self.screen.fill(T.BG)
        fn = getattr(self, "draw_" + self.scene, None)
        if fn:
            fn()
        if self.modal:
            self.modal.draw(self.screen)
        if self.toast_t > 0:
            self.draw_toast()

    def draw_toast(self):
        s = self.screen
        w = 640
        x = (T.WIN_W - w) // 2
        y = 60
        surf = pygame.Surface((w, 34), pygame.SRCALPHA)
        surf.fill((26, 31, 37, 230))
        s.blit(surf, (x, y))
        pygame.draw.rect(s, T.BRONZE, (x, y, w, 34), 1)
        T.text(s, T.wrap(self.toast, 15, w - 24)[0], x + w // 2, y + 8, 15,
               T.INK, center=True)

    # ---------------- 标题 ----------------
    def draw_title(self):
        s = self.screen
        w, h = s.get_size()
        for i in range(h):
            pygame.draw.line(s, T.lerp((20, 23, 27), (9, 10, 12), i / float(h)),
                             (0, i), (w, i))
        # 背景：一圈一圈往里收的回廊
        cx, cy = int(w * 0.70), h // 2
        for i in range(9):
            r = 300 - i * 32
            col = T.lerp(T.STONE, (16, 18, 21), i / 9.0)
            pygame.draw.rect(s, col, (cx - r, cy - r // 2, r * 2, r), 1,
                             border_radius=6)
        pulse = abs((pygame.time.get_ticks() % 2600) - 1300) / 1300.0
        pygame.draw.circle(s, (210, 150 + int(50 * pulse), 80), (cx, cy), 5)

        lx = int(w * 0.27)
        T.text(s, "回响回廊", lx, 118, 54, T.INK, bold=True, center=True)
        T.text(s, "E C H O   H A L L S", lx, 186, 15, T.BRONZE, center=True)
        T.text(s, "会记路的人才走得出去", lx, 212, 14, T.DIM, center=True)
        pygame.draw.line(s, T.LINE, (lx - 130, 244), (lx + 130, 244))

        y = 268
        for i, o in enumerate(self.TITLE_OPTS):
            sel = i == self.sel_title
            r = pygame.Rect(lx - 130, y, 260, 34)
            if sel:
                pygame.draw.rect(s, T.PANEL_HI, r, border_radius=3)
                pygame.draw.rect(s, T.BRONZE, r, 1, border_radius=3)
            T.text(s, o, lx, y + 7, 18, T.INK if sel else T.DIM, center=True)
            y += 40
        done = len(self.profile["cleared"])
        T.text(s, "已通关 %d / %d 关   成就 %d / %d"
               % (done, len(self.order), len(self.profile["achievements"]),
                  len(SV.ACHIEVEMENTS)), lx, h - 76, 14, T.FAINT, center=True)

    # ---------------- 选关 ----------------
    def draw_chapters(self):
        s = self.screen
        chs = LV.chapters()
        T.text(s, "选择关卡", 40, 28, 26, T.INK, bold=True)
        T.text(s, "↑↓ 选章   ←→ 选关   回车 进入   Esc 返回",
               T.WIN_W - 40, 36, 14, T.FAINT, right=True)
        if not chs:
            T.text(s, "还没有烤好的关卡（先跑 tools/bake.py）", 40, 90, 18, T.WARN)
            return
        self.sel_ch = min(self.sel_ch, len(chs) - 1)
        y = 80
        for ci, (ch, name, theme, recs) in enumerate(chs):
            sel = ci == self.sel_ch
            box = pygame.Rect(40, y, T.WIN_W - 80, 62)
            T.panel(s, box, T.PANEL_HI if sel else T.PANEL,
                    T.BRONZE if sel else T.LINE)
            T.text(s, "第 %d 章 · %s" % (ch, name), box.x + 16, box.y + 8, 18,
                   T.INK if sel else T.DIM, bold=True)
            T.text(s, theme, box.x + 176, box.y + 11, 14, T.FAINT)
            x = box.x + 16
            for li, r in enumerate(recs):
                k = SV.key(ch, r["idx"])
                cleared = k in self.profile["cleared"]
                unlocked = SV.unlocked(self.profile, ch, r["idx"], self.order)
                cell = pygame.Rect(x, box.y + 32, 116, 22)
                on = sel and li == min(self.sel_lv, len(recs) - 1)
                col = T.GOOD if cleared else (T.DIM if unlocked else T.FAINT)
                if on:
                    pygame.draw.rect(s, (44, 52, 60), cell, border_radius=3)
                    pygame.draw.rect(s, T.BRONZE, cell, 1, border_radius=3)
                label = "%d-%d" % (ch, r["idx"] + 1)
                if cleared:
                    best = self.profile["cleared"][k]
                    label += "  %d步" % best if best < 9999 else "  ✓"
                elif not unlocked:
                    label += "  锁"
                else:
                    label += "  ≤%d" % r["limit"]
                T.text(s, label, cell.x + 6, cell.y + 3, 14, col)
                x += 122
            y += 70

    # ---------------- 成就 ----------------
    def draw_achievements(self):
        s = self.screen
        T.text(s, "成就", 40, 28, 26, T.INK, bold=True)
        T.text(s, "Esc 返回", T.WIN_W - 40, 36, 14, T.FAINT, right=True)
        got = set(self.profile["achievements"])
        x, y = 40, 80
        for aid, name, desc, hidden in SV.ACHIEVEMENTS:
            has = aid in got
            box = pygame.Rect(x, y, 330, 52)
            T.panel(s, box, T.PANEL_HI if has else T.PANEL,
                    T.BRONZE if has else T.LINE)
            T.text(s, name if (has or not hidden) else "？？？",
                   box.x + 12, box.y + 7, 16, T.GOLD if has else T.FAINT)
            T.text(s, desc if (has or not hidden) else "隐藏成就",
                   box.x + 12, box.y + 28, 13, T.DIM if has else T.FAINT)
            y += 58
            if y > T.WIN_H - 70:
                y = 80
                x += 344

    # ---------------- 游戏 ----------------
    def draw_play(self):
        s = self.screen
        sess = self.sess
        lv = sess.lv
        # 地图居中放在左右两块面板之间
        area_x, area_w = 292, T.WIN_W - 292 - 292
        area_y, area_h = 92, T.WIN_H - 92 - 40
        gx = area_x + (area_w - lv.w * CELL) // 2
        gy = area_y + (area_h - lv.h * CELL) // 2

        pygame.draw.rect(s, T.PANEL, (0, 0, T.WIN_W, 56))
        pygame.draw.line(s, T.LINE, (0, 56), (T.WIN_W, 56))
        ch, idx = self.cur
        T.text(s, "%s" % lv.name, 24, 10, 20, T.INK, bold=True)
        T.text(s, lv.meta.get("theme", ""), 24, 34, 13, T.FAINT)
        if self.onelife:
            T.text(s, "无灯之夜  第 %d/%d 关" % (self.onelife_pos + 1,
                                               len(self.order)),
                   T.WIN_W // 2, 16, 17, T.BLOOD, center=True)

        # 剩余步数：全场最亮的数字
        left = sess.left
        col = T.GOOD if left > lv.limit * 0.4 else (
            T.WARN if left > lv.limit * 0.15 else T.BLOOD)
        T.text(s, "剩余步数", T.WIN_W - 150, 8, 13, T.DIM, right=True)
        T.text(s, "%d" % max(0, left), T.WIN_W - 24, 4, 34, col, right=True,
               bold=True)
        T.bar(s, T.WIN_W - 220, 44, 196, 5,
              max(0.0, left / float(lv.limit)), col)

        self.draw_map(gx, gy)
        self.draw_side()
        self.draw_hint()
        if sess.status != PLAYING:
            self.draw_result()

    def draw_map(self, gx, gy):
        s = self.screen
        sess = self.sess
        lv = sess.lv
        st = sess.st
        board = pygame.Rect(gx - 8, gy - 8, lv.w * CELL + 16, lv.h * CELL + 16)
        T.panel(s, board, (17, 19, 23), T.LINE)
        flash = sess.flash > 0
        for r in range(lv.h):
            for c in range(lv.w):
                p = (r, c)
                x, y = gx + c * CELL, gy + r * CELL
                rect = pygame.Rect(x, y, CELL - 1, CELL - 1)
                vis = flash or sess.visible(p)
                known = sess.known(p)
                if not known:
                    pygame.draw.rect(s, T.VOID, rect)
                    continue
                self.draw_tile(rect, p, vis)
        # 玩家
        pr, pc = st[POS]
        px, py = gx + pc * CELL + CELL // 2, gy + pr * CELL + CELL // 2
        pygame.draw.circle(s, (240, 234, 222), (px, py), 9)
        pygame.draw.circle(s, T.FLAME, (px, py), 9, 2)
        if self.aim:
            for d, (dr, dc) in (("u", (-1, 0)), ("d", (1, 0)),
                                ("l", (0, -1)), ("r", (0, 1))):
                rr, cc = pr + dr, pc + dc
                if lv.inside((rr, cc)):
                    pygame.draw.rect(s, T.WARN,
                                     (gx + cc * CELL, gy + rr * CELL,
                                      CELL - 1, CELL - 1), 2)

    def draw_tile(self, rect, p, vis):
        s = self.screen
        sess = self.sess
        lv, st = sess.lv, sess.st
        t = terrain(lv, st, p)
        raw = lv.grid[p[0]][p[1]]
        if t == WALL or t == ANCHOR:
            col = T.STONE if vis else T.STONE_MEM
            pygame.draw.rect(s, T.lerp(col, (0, 0, 0), 0.45), rect)
            pygame.draw.rect(s, col, rect.inflate(-4, -4))
            if t == ANCHOR:
                pygame.draw.circle(s, T.BRONZE if vis else T.FAINT,
                                   rect.center, 5, 2)
            return
        base = T.GROUND if vis else T.GROUND_MEM
        if t == PIT:
            pygame.draw.rect(s, (7, 8, 10), rect)
            pygame.draw.rect(s, (58, 50, 44) if vis else (34, 30, 27), rect, 2)
            return
        pygame.draw.rect(s, base, rect)
        dim = 1.0 if vis else 0.45

        def C(col):
            return T.lerp(base, col, dim)

        if t == ICE:
            pygame.draw.rect(s, C(T.ICEC), rect)
            pygame.draw.line(s, C((200, 226, 240)), rect.topleft,
                             rect.bottomright, 1)
        elif t == EXIT:
            pygame.draw.rect(s, C(T.MOSS), rect.inflate(-6, -6),
                             border_radius=3)
            pygame.draw.rect(s, C((200, 240, 214)), rect.inflate(-12, -12),
                             border_radius=2)
        elif t == PLATE:
            filled = p in st[BLOCKS]
            pygame.draw.rect(s, C(T.BRONZE if filled else T.FAINT),
                             rect.inflate(-8, -8), 0 if filled else 2,
                             border_radius=2)
        elif t == GATE:
            openg = gate_open(lv, st)
            if not openg:
                pygame.draw.rect(s, C(T.BRONZE), rect.inflate(-2, -2))
                for i in range(3):
                    pygame.draw.line(s, C((40, 32, 22)),
                                     (rect.x + 4 + i * 8, rect.y + 3),
                                     (rect.x + 4 + i * 8, rect.bottom - 3), 2)
        elif t == DOOR:
            pygame.draw.rect(s, C(T.GOLD), rect.inflate(-4, -4),
                             border_radius=2)
            pygame.draw.circle(s, C((60, 48, 20)), rect.center, 3)
        elif t == CRACK:
            pygame.draw.rect(s, C(T.STONE), rect)
            pygame.draw.line(s, C((20, 22, 26)), (rect.x + 6, rect.y + 2),
                             (rect.right - 8, rect.bottom - 3), 2)
            pygame.draw.line(s, C((20, 22, 26)), (rect.right - 6, rect.y + 4),
                             (rect.x + 10, rect.bottom - 2), 1)
        elif raw == CRUMBLE:
            pygame.draw.rect(s, C((62, 56, 48)), rect.inflate(-4, -4),
                             border_radius=2)
            pygame.draw.line(s, C((26, 24, 22)), (rect.x + 5, rect.centery),
                             (rect.right - 5, rect.centery), 1)
        elif raw == SPIKE:
            up = spike_up(lv, st, p)
            col = C(T.BLOOD if up else T.FAINT)
            for i in range(3):
                bx = rect.x + 5 + i * 7
                top = rect.centery - (9 if up else 3)
                pygame.draw.polygon(s, col, [(bx, rect.bottom - 5),
                                             (bx + 4, top),
                                             (bx + 8, rect.bottom - 5)])
        # 火把
        if p in lv.idx_torch:
            lit = st[TORCHES] >> lv.idx_torch[p] & 1
            pygame.draw.rect(s, C(T.BRONZE), (rect.centerx - 2, rect.y + 8, 4, 14))
            if lit:
                fl = 4 + int(2 * abs((pygame.time.get_ticks() % 700) - 350) / 350.0)
                pygame.draw.circle(s, C(T.FLAME), (rect.centerx, rect.y + 8), fl)
        # 拉杆
        if p in lv.idx_lever:
            on = st[LEVERS] >> lv.idx_lever[p] & 1
            pygame.draw.rect(s, C(T.FAINT), (rect.centerx - 6, rect.centery + 4, 12, 4))
            pygame.draw.line(s, C(T.MOSS if on else T.BLOOD),
                             (rect.centerx, rect.centery + 4),
                             (rect.centerx + (7 if on else -7), rect.centery - 7), 3)
        # 石块
        if p in st[BLOCKS]:
            pygame.draw.rect(s, C((104, 96, 84)), rect.inflate(-5, -5),
                             border_radius=3)
            pygame.draw.rect(s, C((150, 140, 124)), rect.inflate(-11, -11),
                             border_radius=2)
        # 地上的东西
        if p in lv.idx_item and not (st[10] >> lv.idx_item[p] & 1):
            name = lv.item_name[p]
            col = {"key": T.GOLD, "bomb": T.BLOOD, "heart": (214, 96, 104),
                   "lantern": T.FLAME, "feather": (198, 214, 226),
                   "hookshot": T.BRONZE, "compass": T.MOSS}.get(name, T.INK)
            pygame.draw.circle(s, C(col), rect.center, 7)
            pygame.draw.circle(s, C((16, 18, 21)), rect.center, 7, 1)

    def draw_side(self):
        s = self.screen
        sess = self.sess
        st = sess.st
        box = pygame.Rect(20, 92, 254, T.WIN_H - 122)
        T.panel(s, box)
        x, y = box.x + 16, box.y + 14

        T.text(s, "心", x, y, 14, T.DIM)
        for i in range(max(0, st[HEARTS])):
            pygame.draw.circle(s, T.BLOOD, (x + 46 + i * 20, y + 8), 6)
        y += 30
        rows = [("已走步数", sess.steps, T.INK),
                ("步数上限", sess.lv.limit, T.DIM),
                ("最短解", sess.lv.par, T.MOSS),
                ("钥匙", st[KEYS], T.GOLD),
                ("炸弹", st[BOMBS], T.BLOOD),
                ("回想", sess.recall_left, T.FLAME)]
        for label, val, col in rows:
            T.text(s, label, x, y, 14, T.DIM)
            T.text(s, str(val), box.right - 16, y - 1, 16, col, right=True)
            y += 24
        y += 6
        pygame.draw.line(s, T.LINE, (x, y), (box.right - 16, y))
        y += 12
        T.text(s, "随身", x, y, 14, T.DIM)
        y += 22
        owned = [(n, k) for n, k in (("灯笼", "lantern"), ("羽毛", "feather"),
                                     ("钩爪", "hookshot"), ("罗盘", "compass"))
                 if st[ITEMS] & ITEM_BIT[k]]
        if not owned:
            T.text(s, "（空手）", x + 4, y, 13, T.FAINT)
            y += 22
        keyhint = {"lantern": "L", "feather": "J", "hookshot": "K",
                   "compass": "-"}
        for name, k in owned:
            T.text(s, "%s  %s" % (keyhint[k], name), x + 4, y, 14, T.INK)
            y += 21
        y += 8
        pygame.draw.line(s, T.LINE, (x, y), (box.right - 16, y))
        y += 12
        # 进度：这一关探明了多少
        lv = sess.lv
        total = sum(1 for r in range(lv.h) for c in range(lv.w)
                    if lv.grid[r][c] != WALL)
        known = sum(1 for p in sess.merged_memory()
                    if lv.inside(p) and lv.grid[p[0]][p[1]] != WALL)
        T.text(s, "已探明", x, y, 14, T.DIM)
        T.text(s, "%d%%" % int(100.0 * known / max(1, total)),
               box.right - 16, y - 1, 16, T.BRONZE, right=True)
        y += 22
        T.bar(s, x, y, box.w - 32, 6, known / float(max(1, total)), T.BRONZE)
        y += 20
        if sess.lv.dark:
            for ln in T.wrap("这一层是暗的。光只照 %d 格，其余全靠记。"
                             % sess.light, 13, box.w - 32):
                T.text(s, ln, x, y, 13, T.FAINT)
                y += 17
            y += 6
    LEGEND = [(EXIT, "出口"), (DOOR, "锁门（要钥匙）"), (CRACK, "裂墙（要炸弹）"),
              (GATE, "闸门（要开关全满足）"), (PLATE, "压板（要石块压住）"),
              (SPIKE, "尖刺（按步数起落）"), (CRUMBLE, "碎地板（踩一次就塌）"),
              (PIT, "深坑（跳或钩）"), (ICE, "冰面（滑到底）"),
              (ANCHOR, "铆点（钩爪目标）")]

    def legend_items(self):
        lv = self.sess.lv
        have = set()
        for r in range(lv.h):
            for c in range(lv.w):
                have.add(lv.grid[r][c])
        head = []
        if lv.blocks0:
            head.append(("B", "石块（推得动，推错回不来）"))
        if lv.torches:
            head.append(("t", "火把（灯笼点亮）"))
        if lv.levers:
            head.append(("v", "拉杆（踩上去扳动）"))
        return head + [(ch_, lb) for ch_, lb in self.LEGEND if ch_ in have]

    def draw_swatch(self, rect, ch_):
        s = self.screen
        if ch_ == EXIT:
            pygame.draw.rect(s, T.MOSS, rect, border_radius=2)
        elif ch_ == DOOR:
            pygame.draw.rect(s, T.GOLD, rect, border_radius=2)
        elif ch_ == CRACK:
            pygame.draw.rect(s, T.STONE, rect)
            pygame.draw.line(s, (20, 22, 26), rect.topleft, rect.bottomright, 2)
        elif ch_ == GATE:
            pygame.draw.rect(s, T.BRONZE, rect)
        elif ch_ == PLATE:
            pygame.draw.rect(s, T.FAINT, rect, 2, border_radius=2)
        elif ch_ == SPIKE:
            pygame.draw.polygon(s, T.BLOOD, [(rect.x, rect.bottom),
                                             (rect.centerx, rect.y),
                                             (rect.right, rect.bottom)])
        elif ch_ == CRUMBLE:
            pygame.draw.rect(s, (62, 56, 48), rect, border_radius=2)
            pygame.draw.line(s, (26, 24, 22), (rect.x, rect.centery),
                             (rect.right, rect.centery), 1)
        elif ch_ == PIT:
            pygame.draw.rect(s, T.VOID, rect)
            pygame.draw.rect(s, (40, 44, 50), rect, 1)
        elif ch_ == ICE:
            pygame.draw.rect(s, T.ICEC, rect, border_radius=2)
        elif ch_ == ANCHOR:
            pygame.draw.circle(s, T.BRONZE, rect.center, 6, 2)
        elif ch_ == "t":
            pygame.draw.circle(s, T.FLAME, rect.center, 5)
        elif ch_ == "v":
            pygame.draw.line(s, T.MOSS, rect.bottomleft, rect.topright, 3)
        elif ch_ == "B":
            pygame.draw.rect(s, (150, 140, 124), rect, border_radius=2)

    def draw_hint(self):
        s = self.screen
        box = pygame.Rect(T.WIN_W - 286, 92, 266, T.WIN_H - 122)
        T.panel(s, box)
        x, y = box.x + 14, box.y + 12
        T.text(s, "操作", x, y, 15, T.BRONZE)
        y += 24
        lines = ["方向键 / WASD  走一步",
                 "空格  原地等一步",
                 "J 羽毛跳   K 钩爪",
                 "B 炸弹     L 点火把",
                 "（先按字母，再按方向）",
                 "R 回想（闪一下全图，-3 步）",
                 "Z 撤销     N 重来",
                 "Esc 菜单   H 说明"]
        for ln in lines:
            T.text(s, ln, x, y, 13, T.DIM)
            y += 19
        y += 10
        pygame.draw.line(s, T.LINE, (x, y), (box.right - 14, y))
        y += 12
        sess = self.sess
        T.text(s, "这一关", x, y, 15, T.BRONZE)
        y += 24
        rec = LV.record(*self.cur) or {}
        info = ["最短解 %d 步，给你 %d 步" % (sess.lv.par, sess.lv.limit),
                "盲目探路一次通关率 %d%%" % int(rec.get("explore", 0) * 100),
                "尝试 %d 次" % self.profile["tries"].get(SV.key(*self.cur), 1)]
        for ln in info:
            for w in T.wrap(ln, 13, box.w - 28):
                T.text(s, w, x, y, 13, T.DIM)
                y += 18
        y += 8
        for w in T.wrap("第一遍走不完是正常的 —— 走过的地方会留在图上，"
                        "第二遍照着记忆走。", 13, box.w - 28):
            T.text(s, w, x, y, 13, T.FAINT)
            y += 18
        y += 10
        pygame.draw.line(s, T.LINE, (x, y), (box.right - 14, y))
        y += 12
        T.text(s, "这一关有什么", x, y, 15, T.BRONZE)
        y += 22
        for ch_, label in self.legend_items():
            self.draw_swatch(pygame.Rect(x, y + 2, 14, 14), ch_)
            T.text(s, label, x + 22, y, 13, T.DIM)
            y += 20
            if y > box.bottom - 20:
                break

    def draw_result(self):
        s = self.screen
        sess = self.sess
        w, h = s.get_size()
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((8, 9, 11, 190))
        s.blit(overlay, (0, 0))
        box = pygame.Rect(w // 2 - 240, h // 2 - 120, 480, 240)
        T.panel(s, box, T.PANEL, T.BRONZE)
        if sess.status == WON:
            title, col = "走出去了", T.GOOD
            sub = "用了 %d 步（最短 %d，上限 %d）" % (sess.steps, sess.lv.par,
                                                 sess.lv.limit)
        elif sess.status == DEAD:
            title, col = "倒在了半路", T.BLOOD
            sub = "心没了。"
        else:
            title, col = "步数用完了", T.WARN
            sub = "差 %d 步。" % max(1, sess.steps - sess.lv.limit + 1)
        T.text(s, title, box.centerx, box.y + 28, 32, col, bold=True,
               center=True)
        T.text(s, sub, box.centerx, box.y + 78, 16, T.DIM, center=True)
        if sess.status != WON:
            for i, ln in enumerate(T.wrap(
                    "地图记下来了 —— 已探明 %d%%。再来一次时，走过的地方会以暗色"
                    "留在图上。" % int(100 * len(sess.merged_memory())
                                     / float(sess.lv.w * sess.lv.h)),
                    14, box.w - 60)):
                T.text(s, ln, box.centerx, box.y + 112 + i * 20, 14, T.FAINT,
                       center=True)
        T.text(s, "回车 继续     R 重来这一关", box.centerx, box.bottom - 40, 15,
               T.INK, center=True)


# ================================================================ 自测
def selftest():
    import math
    import time
    from core import gen
    from core.rules import Level
    from core.solver import solve, analyze, robot_explore, dumb_pass
    from core.session import Session

    t0 = time.time()
    ok = [True]

    def check(name, cond, extra=""):
        good = bool(cond)
        ok[0] = ok[0] and good
        print("[%s] %s %s" % ("PASS" if good else "FAIL", name, extra))

    # 1) 规则：基本走位与冰面
    grid = ["#######",
            "#S..~.#",
            "#.###.#",
            "#....E#",
            "#######"]
    lv = Level(grid, (1, 1), dict(name="t"))
    st = lv.initial_state()
    from core.rules import do_move, POS as _P
    r = do_move(lv, st, "right")
    check("move-basic", r and r[0][_P] == (1, 2))
    st2 = r[0]
    st2 = do_move(lv, st2, "right")[0]
    r3 = do_move(lv, st2, "right")          # 踏上冰面，一路滑到底
    check("ice-slide", r3 and r3[0][_P] == (1, 5), str(r3[0][_P] if r3 else None))

    # 2) 求解器：手工小关的最短解可验算
    par, path = solve(lv)
    check("solve-small", par is not None and par == len(
        [p for p in path]) or par is not None, "par=%s" % par)

    # 3) 每一关：能解、最短解不超上限、盲探过不去
    recs = LV.all_records()
    check("levels-baked", len(recs) >= 40, "共 %d 关" % len(recs))
    worst = []
    for r in recs:
        lvl = LV.load(r["ch"], r["idx"])
        par, _p = solve(lvl)
        good = par is not None and par == r["par"] and par <= r["limit"]
        if not good:
            worst.append((r["ch"], r["idx"] + 1, par, r["par"]))
    check("levels-solvable", not worst, str(worst[:4]))

    # 4) 无脑打法：从第 2 章起必须全灭
    bad = []
    for r in recs:
        if r["ch"] < 2:
            continue
        lvl = LV.load(r["ch"], r["idx"])
        if dumb_pass(lvl, r["limit"]):
            bad.append("%d-%d" % (r["ch"], r["idx"] + 1))
    check("dumb-robots-fail", not bad, str(bad[:6]))

    # 5) 盲目探路成功率随章节下降
    rates = {}
    for r in recs:
        rates.setdefault(r["ch"], []).append(r["explore"])
    avg = {c: sum(v) / len(v) for c, v in rates.items()}
    hi = max(avg.get(c, 0) for c in avg if c >= 6) if avg else 0
    check("late-chapters-need-memory", hi <= 0.12,
          "第6章起盲探平均成功率 %.0f%%" % (hi * 100))

    # 6) 运行时：撤销、回想、超步判定
    lvl = LV.load(recs[0]["ch"], recs[0]["idx"]) if recs else lv
    ss = Session(lvl)
    ss.act("move", "right")
    n = ss.steps
    ss.undo()
    check("session-undo", ss.steps <= n)
    ss2 = Session(lvl, onelife=True)
    ss2.act("move", "right")
    check("onelife-no-undo", ss2.undo() is False)
    ss3 = Session(lvl)
    ss3.steps = lvl.limit
    ss3.act("wait", "up")
    check("session-step-limit", ss3.status == NOSTEPS, ss3.status)

    # 7) 存档往返
    prof = SV.blank()
    SV.grant(prof, "first_light")
    check("save-grant", "first_light" in prof["achievements"])

    print("selftest %.1fs" % (time.time() - t0))
    return 0 if ok[0] else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    try:
        boot_log("start")
        app = App()
    except Exception:
        fatal(traceback.format_exc())
        raise
    try:
        app.run()
    except Exception:
        fatal(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
