"""
gui.py — Minimal puzzle game interface
Run: python gui.py
"""
from __future__ import annotations

import math
import random
import threading
import time
import tkinter as tk
from typing import Optional

# ── Palettes ──────────────────────────────────────────────────────────────────

DARK = {
    "bg":          "#12131F",
    "panel":       "#1C1D2E",
    "accent":      "#6C8EFF",
    "accent_dk":   "#4F6CF7",
    "text":        "#E2E8F0",
    "muted":       "#6B7280",
    "clue_bg":     "#252848",
    "user_bg":     "#1C1D2E",
    "error_bg":    "#3B1111",
    "solved_bg":   "#0F2E1A",
    "diag_tint":    "#2A2510",
    "hyper_tint":   "#1A1A00",
    "hyper_border": "#D97706",
    "line_thin":    "#2E3155",
    "line_thick":  "#6C8EFF",
    "sel_outline": "#6C8EFF",
    "num_clue":    "#E2E8F0",
    "num_user":    "#6C8EFF",
    "num_solved":  "#4ADE80",
    "success":     "#4ADE80",
}

LIGHT = {
    "bg":          "#F7F8FC",
    "panel":       "#FFFFFF",
    "accent":      "#4F6CF7",
    "accent_dk":   "#3451B2",
    "text":        "#1A202C",
    "muted":       "#718096",
    "clue_bg":     "#EEF2FF",
    "user_bg":     "#FFFFFF",
    "error_bg":    "#FEE2E2",
    "solved_bg":   "#D1FAE5",
    "diag_tint":    "#FFFBEB",
    "hyper_tint":   "#FEF3C7",
    "hyper_border": "#D97706",
    "line_thin":    "#CBD5E0",
    "line_thick":  "#2D3748",
    "sel_outline": "#4F6CF7",
    "num_clue":    "#1A202C",
    "num_user":    "#4F6CF7",
    "num_solved":  "#059669",
    "success":     "#059669",
}

C: dict = dict(LIGHT)  # mutable — updated in-place on theme toggle

# ── Layout helpers ────────────────────────────────────────────────────────────

PAD = 20

def cell_px(n: int) -> int:
    if n <= 4:  return 84
    if n <= 6:  return 70
    if n <= 9:  return 56
    return 38

def num_font(n: int, bold: bool = False) -> tuple:
    sz = {4: 24, 6: 19, 9: 17, 16: 12}
    size = next(v for k, v in sorted(sz.items()) if n <= k)
    return ("Segoe UI", size, "bold" if bold else "normal")

def cage_label_font(n: int) -> tuple:
    sz = {4: 11, 6: 10, 9: 9, 16: 7}
    size = next(v for k, v in sorted(sz.items()) if n <= k)
    return ("Segoe UI", size)

# ── Game catalogue ────────────────────────────────────────────────────────────

GAME_LABELS = {
    "sudoku":         "Sudoku",
    "kenken":         "KenKen",
    "diagonal":       "Diagonal Sudoku",
    "hyper":          "Hyper Sudoku",
    "nonconsecutive": "Nonconsecutive Sudoku",
}

GAME_SIZES = {
    "sudoku":         [4, 9, 16],
    "kenken":         [3, 4, 5, 6, 7, 8, 9],
    "diagonal":       [4, 9],
    "hyper":          [9],
    "nonconsecutive": [9],
}

DIFFICULTIES = ["easy", "medium", "hard"]

_KENKEN_DIFF = {
    "easy":   dict(max_cage_size_factor=0.6, singleton_rate=0.05),
    "medium": dict(max_cage_size_factor=0.4, singleton_rate=0.15),
    "hard":   None,
}

# ── Generation (runs in background thread) ────────────────────────────────────

def run_generate(game: str, n: int, difficulty: str, seed: int):
    t0 = time.time()
    if game == "sudoku":
        from puzzler.sudoku import generate_puzzle
        puzzle, solution = generate_puzzle(n, seed=seed, difficulty=difficulty)
        return puzzle, solution, None, time.time() - t0

    if game == "kenken":
        from puzzler.kenken import generate_kenken_puzzle, generate_minimal_kenken_puzzle
        if difficulty == "hard":
            max_cage = max(2, int(n * 0.4))
            solution, cages = generate_minimal_kenken_puzzle(n, max_cage_size=max_cage, seed=seed)
        else:
            p = _KENKEN_DIFF[difficulty]
            max_cage = max(2, int(n * p["max_cage_size_factor"]))
            solution, cages = generate_kenken_puzzle(
                n, max_cage_size=max_cage,
                singleton_rate=p["singleton_rate"], seed=seed,
            )
        puzzle = [[0] * n for _ in range(n)]
        return puzzle, solution, cages, time.time() - t0

    if game == "diagonal":
        from puzzler.diagonal import generate_diagonal_puzzle
        puzzle, solution = generate_diagonal_puzzle(n, seed=seed, difficulty=difficulty)
        return puzzle, solution, None, time.time() - t0

    if game == "hyper":
        from puzzler.hyper import generate_hyper_puzzle
        puzzle, solution = generate_hyper_puzzle(n, seed=seed, difficulty=difficulty)
        return puzzle, solution, None, time.time() - t0

    if game == "nonconsecutive":
        from puzzler.nonconsecutive import generate_nonconsecutive_puzzle
        puzzle, solution = generate_nonconsecutive_puzzle(n, seed=seed, difficulty=difficulty)
        return puzzle, solution, None, time.time() - t0

    raise ValueError(f"Unknown game: {game}")


# ── Shared button style helpers ───────────────────────────────────────────────

def _pill(parent, text, cmd, primary=True, **kw):
    bg = C["accent"] if primary else C["bg"]
    fg = "white" if primary else C["text"]
    bd = 0 if primary else 1
    relief = "flat" if primary else "solid"
    kw.setdefault("pady", 8)
    kw.setdefault("padx", 20)
    kw.setdefault("font", ("Segoe UI", 11))
    btn = tk.Button(
        parent, text=text, command=cmd,
        bg=bg, fg=fg,
        activebackground=C["accent_dk"] if primary else C["muted"],
        activeforeground="white" if primary else C["text"],
        bd=bd, relief=relief, cursor="hand2",
        **kw,
    )
    return btn

def _toggle_btn(parent, text, cmd):
    btn = tk.Button(
        parent, text=text, command=cmd,
        font=("Segoe UI", 10), bd=0, relief="flat", cursor="hand2",
        bg=C["bg"], fg=C["text"], pady=5, padx=12,
    )
    return btn

def _set_active(btn, active: bool):
    if active:
        btn.config(bg=C["accent"], fg="white", font=("Segoe UI", 10, "bold"))
    else:
        btn.config(bg=C["bg"], fg=C["text"], font=("Segoe UI", 10))


# ── App root ──────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Logic Puzzles")
        self.configure(bg=C["bg"])
        self.resizable(True, True)
        self._theme = "light"
        self._current = "home"
        self._saved_game: Optional[dict] = None
        self._frame: Optional[tk.Frame] = None

        # Persistent toolbar — always at top, never destroyed
        self._toolbar = tk.Frame(self, bg=C["bg"])
        self._toolbar.pack(fill="x", side="top")
        self._theme_btn = tk.Button(
            self._toolbar, text="🌙", command=self._toggle_theme,
            bg=C["bg"], fg=C["muted"], bd=0, relief="flat",
            font=("Segoe UI", 15), cursor="hand2",
            activebackground=C["bg"], activeforeground=C["text"],
        )
        self._theme_btn.pack(side="right", padx=10, pady=4)

        self.show_home()

    def _switch(self, frame: tk.Frame):
        if self._frame:
            self._frame.destroy()
        self._frame = frame
        frame.pack(fill="both", expand=True)

    def _toggle_theme(self):
        # Capture live game state before destroying the frame
        if self._current == "game" and isinstance(self._frame, GameFrame):
            gf = self._frame
            self._saved_game.update(
                user_grid=[row[:] for row in gf.user_grid],
                seconds=gf._seconds,
                solved_view=gf._solved_view,
                won=gf._won,
            )

        self._theme = "light" if self._theme == "dark" else "dark"
        C.update(LIGHT if self._theme == "light" else DARK)
        icon = "🌙" if self._theme == "light" else "☀"
        self.configure(bg=C["bg"])
        self._toolbar.configure(bg=C["bg"])
        self._theme_btn.configure(text=icon, bg=C["bg"], fg=C["muted"],
                                   activebackground=C["bg"])
        # Rebuild current screen with new colors
        if self._current == "home":
            self._switch(HomeFrame(self))
        elif self._current == "game" and self._saved_game:
            sg = self._saved_game
            self.geometry("")
            self._switch(GameFrame(
                self, sg["game"], sg["n"], sg["difficulty"], sg["seed"],
                sg["puzzle"], sg["solution"], sg["cages"], sg["elapsed"],
                user_grid=sg["user_grid"], seconds=sg["seconds"],
                solved_view=sg["solved_view"], won=sg["won"],
            ))

    def show_home(self):
        self._current = "home"
        self._saved_game = None
        self._switch(HomeFrame(self))

    def show_loading(self, game, n, difficulty, seed):
        self._current = "loading"
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        self._switch(LoadingFrame(self, game, n, difficulty, seed))
        self.geometry(f"{w}x{h}")

    def show_game(self, game, n, difficulty, seed, puzzle, solution, cages, elapsed):
        self._current = "game"
        self._saved_game = dict(
            game=game, n=n, difficulty=difficulty, seed=seed,
            puzzle=puzzle, solution=solution, cages=cages, elapsed=elapsed,
            user_grid=None, seconds=0, solved_view=False, won=False,
        )
        self.geometry("")
        self._switch(GameFrame(self, game, n, difficulty, seed,
                               puzzle, solution, cages, elapsed))


# ── Home screen ───────────────────────────────────────────────────────────────

class HomeFrame(tk.Frame):
    def __init__(self, app: App):
        super().__init__(app, bg=C["bg"])
        self.app = app

        tk.Label(self, text="Logic Puzzles", bg=C["bg"],
                 font=("Segoe UI", 30, "bold"), fg=C["text"]).pack(pady=(52, 6))
        tk.Label(self, text="Choose a puzzle and start playing",
                 bg=C["bg"], font=("Segoe UI", 12), fg=C["muted"]).pack()

        card = tk.Frame(self, bg=C["panel"],
                        highlightbackground=C["line_thin"], highlightthickness=1)
        card.pack(padx=80, pady=32, ipadx=36, ipady=28)

        def section(label):
            tk.Label(card, text=label, bg=C["panel"],
                     font=("Segoe UI", 10), fg=C["muted"],
                     anchor="w").pack(fill="x", padx=8, pady=(14, 3))

        # Game row
        section("Game")
        gf = tk.Frame(card, bg=C["panel"])
        gf.pack(fill="x", padx=8)
        self._game_var = tk.StringVar(value="sudoku")
        self._game_btns: dict = {}
        for g, lbl in GAME_LABELS.items():
            b = _toggle_btn(gf, lbl, lambda g=g: self._pick_game(g))
            b.pack(side="left", padx=2, pady=2)
            self._game_btns[g] = b

        # Size row
        section("Size")
        self._size_frame = tk.Frame(card, bg=C["panel"])
        self._size_frame.pack(fill="x", padx=8)
        self._size_var = tk.IntVar(value=9)
        self._size_btns: dict = {}

        # Difficulty row
        section("Difficulty")
        df = tk.Frame(card, bg=C["panel"])
        df.pack(fill="x", padx=8)
        self._diff_var = tk.StringVar(value="medium")
        self._diff_btns: dict = {}
        for d in DIFFICULTIES:
            b = _toggle_btn(df, d.capitalize(), lambda d=d: self._pick_diff(d))
            b.pack(side="left", padx=2, pady=2)
            self._diff_btns[d] = b

        # Generate
        _pill(card, "Generate Puzzle", self._go, pady=11, padx=28,
              font=("Segoe UI", 13, "bold")).pack(pady=(22, 4))

        # Init
        self._pick_game("sudoku")
        self._pick_diff("medium")

    def _pick_game(self, game: str):
        self._game_var.set(game)
        for g, b in self._game_btns.items():
            _set_active(b, g == game)
        self._rebuild_sizes(game)

    def _rebuild_sizes(self, game: str):
        for w in self._size_frame.winfo_children():
            w.destroy()
        self._size_btns = {}
        sizes = GAME_SIZES[game]
        default = 9 if 9 in sizes else sizes[0]
        self._size_var.set(default)
        for s in sizes:
            b = _toggle_btn(self._size_frame, f"{s}×{s}",
                            lambda s=s: self._pick_size(s))
            b.pack(side="left", padx=2, pady=2)
            self._size_btns[s] = b
        self._pick_size(default)

    def _pick_size(self, size: int):
        self._size_var.set(size)
        for s, b in self._size_btns.items():
            _set_active(b, s == size)

    def _pick_diff(self, diff: str):
        self._diff_var.set(diff)
        for d, b in self._diff_btns.items():
            _set_active(b, d == diff)

    def _go(self):
        self.app.show_loading(
            self._game_var.get(),
            self._size_var.get(),
            self._diff_var.get(),
            random.randint(0, 99_999),
        )


# ── Loading screen ────────────────────────────────────────────────────────────

def _make_dot_frames() -> list[str]:
    """3×3 grid: 3-dot comet rotating clockwise around the ring."""
    ring = [(0,0),(0,1),(0,2),(1,2),(2,2),(2,1),(2,0),(1,0)]
    frames = []
    for i in range(8):
        g = [["○","○","○"],["○","○","○"],["○","○","○"]]
        for j in (i, (i+1) % 8, (i+2) % 8):
            r, c = ring[j]
            g[r][c] = "●"
        frames.append("\n".join("  ".join(row) for row in g))
    return frames


class LoadingFrame(tk.Frame):
    _SPINNER = _make_dot_frames()

    def __init__(self, app: App, game, n, difficulty, seed):
        super().__init__(app, bg=C["bg"])
        self.app = app
        self._tick = 0
        self._done = False

        tk.Label(self, text=GAME_LABELS[game], bg=C["bg"],
                 font=("Segoe UI", 24, "bold"), fg=C["text"]).pack(pady=(70, 6))
        tk.Label(self, text=f"{n}×{n}  ·  {difficulty.capitalize()}",
                 bg=C["bg"], font=("Segoe UI", 13), fg=C["muted"]).pack()

        self._spin_lbl = tk.Label(self, text=self._SPINNER[0], bg=C["bg"],
                                   font=("Segoe UI", 22), fg=C["accent"],
                                   justify="center")
        self._spin_lbl.pack(pady=(28, 8))

        self._msg = tk.Label(self, text="Generating…", bg=C["bg"],
                              font=("Segoe UI", 13), fg=C["muted"])
        self._msg.pack()

        self._animate()
        threading.Thread(
            target=self._bg, args=(game, n, difficulty, seed), daemon=True
        ).start()

    def _animate(self):
        if self._done:
            return
        self._spin_lbl.config(text=self._SPINNER[self._tick % len(self._SPINNER)])
        self._tick += 1
        self.after(120, self._animate)

    def _bg(self, game, n, difficulty, seed):
        try:
            result = run_generate(game, n, difficulty, seed)
        except Exception as exc:
            result = exc
        self.after(0, lambda: self._finish(game, n, difficulty, seed, result))

    def _finish(self, game, n, difficulty, seed, result):
        self._done = True
        if isinstance(result, Exception):
            self._spin_lbl.config(text="✗", fg="red")
            self._msg.config(text=f"Error: {result}", fg="red")
            _pill(self, "Back", self.app.show_home, primary=False).pack(pady=16)
            return
        puzzle, solution, cages, elapsed = result
        self.app.show_game(game, n, difficulty, seed, puzzle, solution, cages, elapsed)


# ── Game screen ───────────────────────────────────────────────────────────────

class GameFrame(tk.Frame):
    def __init__(self, app: App, game, n, difficulty, seed,
                 puzzle, solution, cages, elapsed_gen,
                 user_grid=None, seconds=0, solved_view=False, won=False):
        super().__init__(app, bg=C["bg"])
        self.app = app
        self.game = game
        self.n = n
        self.difficulty = difficulty
        self.seed = seed
        self.puzzle = puzzle
        self.solution = solution
        self.cages = cages
        self.elapsed_gen = elapsed_gen

        self.cs = cell_px(n)
        self._cpx = PAD * 2 + n * self.cs

        # State — restored from saved game when rebuilding after theme switch
        if user_grid is not None:
            self.user_grid = [row[:] for row in user_grid]
        else:
            self.user_grid = [[puzzle[r][c] or None for c in range(n)] for r in range(n)]
        self.is_clue: list[list[bool]] = [
            [puzzle[r][c] != 0 for c in range(n)] for r in range(n)
        ]
        if cages:
            self.cage_of: list[list[int]] = [[-1] * n for _ in range(n)]
            for i, cage in enumerate(cages):
                for (r, c) in cage["cells"]:
                    self.cage_of[r][c] = i
        else:
            self.cage_of = None

        self.selected: Optional[tuple[int, int]] = None
        self._solved_view = solved_view
        self._won = won
        self._seconds = seconds
        self._ticking = not (won or solved_view)

        # Multi-digit buffer (for n > 9)
        self._buf = ""
        self._buf_job: Optional[str] = None

        self._build()
        self._redraw()
        self._timer_tick()

    # ── UI skeleton ───────────────────────────────────────────────────────────

    def _build(self):
        # ── top bar
        top = tk.Frame(self, bg=C["bg"])
        top.pack(fill="x", padx=24, pady=(18, 4))

        tk.Label(top, text=GAME_LABELS[self.game], bg=C["bg"],
                 font=("Segoe UI", 19, "bold"), fg=C["text"]).pack(side="left")
        tk.Label(top,
                 text=f"  {self.n}×{self.n}  ·  {self.difficulty.capitalize()}  ·  seed {self.seed}",
                 bg=C["bg"], font=("Segoe UI", 10), fg=C["muted"]).pack(side="left")

        self._timer_lbl = tk.Label(top, text="00:00", bg=C["bg"],
                                    font=("Segoe UI", 17, "bold"), fg=C["accent"])
        self._timer_lbl.pack(side="right")

        tk.Label(self, text=f"Generated in {self.elapsed_gen:.2f}s",
                 bg=C["bg"], font=("Segoe UI", 9), fg=C["muted"]).pack()

        # ── canvas
        self._cv = tk.Canvas(self, width=self._cpx, height=self._cpx,
                              bg=C["panel"], highlightthickness=0)
        self._cv.pack(pady=10)
        self._cv.bind("<Button-1>", self._click)
        self._cv.bind("<Key>",      self._key)
        self._cv.bind("<BackSpace>", self._backspace)
        self._cv.bind("<Delete>",    self._backspace)
        self._cv.bind("<Up>",    lambda e: self._nav(-1, 0))
        self._cv.bind("<Down>",  lambda e: self._nav(1, 0))
        self._cv.bind("<Left>",  lambda e: self._nav(0, -1))
        self._cv.bind("<Right>", lambda e: self._nav(0, 1))
        self._cv.focus_set()

        # ── bottom buttons
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(pady=(2, 24))
        _pill(bf, "← Menu", self.app.show_home, primary=False).pack(side="left", padx=6)
        _pill(bf, "Solve",  self._do_solve).pack(side="left", padx=6)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _redraw(self):
        cv = self._cv
        cv.delete("all")
        n, cs = self.n, self.cs

        # Cell backgrounds (tints integrated into each cell's logic)
        for r in range(n):
            for c in range(n):
                self._draw_cell_bg(r, c)

        # Grid lines
        self._draw_lines()

        # Hyper window borders drawn last so they sit on top of grid lines
        if self.game == "hyper":
            self._draw_hyper_borders()

        # Values
        for r in range(n):
            for c in range(n):
                self._draw_value(r, c)

        # KenKen cage labels
        if self.cages:
            self._draw_cage_labels()

        # Selection
        if self.selected:
            self._draw_sel(*self.selected)

    def _cell_box(self, r, c):
        x0 = PAD + c * self.cs
        y0 = PAD + r * self.cs
        return x0, y0, x0 + self.cs, y0 + self.cs

    def _fill_cell(self, r, c, color):
        x0, y0, x1, y1 = self._cell_box(r, c)
        self._cv.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    def _in_hyper_window(self, r: int, c: int) -> bool:
        for wr, wc in [(1, 1), (1, 5), (5, 1), (5, 5)]:
            if wr <= r < wr + 3 and wc <= c < wc + 3:
                return True
        return False

    def _draw_cell_bg(self, r, c):
        v = self.user_grid[r][c]
        n = self.n
        if self.is_clue[r][c]:
            color = C["clue_bg"]
        elif self._solved_view and v == self.solution[r][c]:
            color = C["solved_bg"]
        elif v is not None and v != self.solution[r][c]:
            color = C["error_bg"]
        elif self.game == "diagonal" and (r == c or r == n - 1 - c):
            color = C["diag_tint"]
        elif self.game == "hyper" and self._in_hyper_window(r, c):
            color = C["hyper_tint"]
        else:
            color = C["user_bg"]
        self._fill_cell(r, c, color)

    def _draw_hyper_borders(self):
        cv = self._cv
        cs = self.cs
        for wr, wc in [(1, 1), (1, 5), (5, 1), (5, 5)]:
            x0 = PAD + wc * cs
            y0 = PAD + wr * cs
            x1 = x0 + 3 * cs
            y1 = y0 + 3 * cs
            cv.create_rectangle(x0, y0, x1, y1,
                                 outline=C["hyper_border"], width=3)

    def _draw_lines(self):
        cv = self._cv
        n, cs = self.n, self.cs

        if self.cage_of:
            # KenKen: thin lattice + thick cage borders
            for i in range(n + 1):
                p = PAD + i * cs
                cv.create_line(p, PAD, p, PAD + n * cs, fill=C["line_thin"], width=1)
                cv.create_line(PAD, p, PAD + n * cs, p, fill=C["line_thin"], width=1)
            self._draw_cage_borders()
        else:
            # Sudoku: thin cells, thick boxes
            box = int(math.isqrt(n))
            for i in range(n + 1):
                thick = i % box == 0
                w = 3 if thick else 1
                col = C["line_thick"] if thick else C["line_thin"]
                p = PAD + i * cs
                cv.create_line(p, PAD, p, PAD + n * cs, fill=col, width=w)
                cv.create_line(PAD, p, PAD + n * cs, p, fill=col, width=w)

        cv.create_rectangle(PAD, PAD, PAD + n * cs, PAD + n * cs,
                             outline=C["line_thick"], width=3)

    def _draw_cage_borders(self):
        cv = self._cv
        n, cs = self.n, self.cs
        W = 3
        for r in range(n):
            for c in range(n):
                cid = self.cage_of[r][c]
                x0, y0, x1, y1 = self._cell_box(r, c)
                if c + 1 < n and self.cage_of[r][c + 1] != cid:
                    cv.create_line(x1, y0, x1, y1, fill=C["line_thick"], width=W)
                if r + 1 < n and self.cage_of[r + 1][c] != cid:
                    cv.create_line(x0, y1, x1, y1, fill=C["line_thick"], width=W)

    def _draw_cage_labels(self):
        cv = self._cv
        lf = cage_label_font(self.n)
        for cage in self.cages:
            cells = sorted(cage["cells"])
            tr, tc = cells[0]
            x0, y0 = PAD + tc * self.cs, PAD + tr * self.cs
            op, tgt = cage["op"], cage["target"]
            text = str(tgt) if op == "1" else f"{tgt}{op}"
            cv.create_text(x0 + 4, y0 + 4, text=text, anchor="nw",
                           font=lf, fill=C["text"])

    def _draw_value(self, r, c):
        v = self.user_grid[r][c]
        if v is None:
            return
        x0, y0, x1, y1 = self._cell_box(r, c)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if self.is_clue[r][c]:
            color, bold = C["num_clue"], True
        elif self._solved_view:
            color, bold = C["num_solved"], False
        else:
            color, bold = C["num_user"], False
        self._cv.create_text(cx, cy, text=str(v),
                             font=num_font(self.n, bold), fill=color)

    def _draw_sel(self, r, c):
        x0, y0, x1, y1 = self._cell_box(r, c)
        self._cv.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2,
                                   outline=C["sel_outline"], width=2)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _click(self, event):
        self._cv.focus_set()
        if self._won or self._solved_view:
            return
        c = (event.x - PAD) // self.cs
        r = (event.y - PAD) // self.cs
        if 0 <= r < self.n and 0 <= c < self.n and not self.is_clue[r][c]:
            self.selected = (r, c)
            self._redraw()

    def _key(self, event):
        if self._won or self._solved_view or self.selected is None:
            return
        r, c = self.selected
        if self.is_clue[r][c]:
            return
        ch = event.char
        if not ch or not ch.isdigit():
            return

        if self.n <= 9:
            d = int(ch)
            if 1 <= d <= self.n:
                self._set_cell(r, c, d)
        else:
            # Multi-digit buffer with 600ms commit timeout
            self._buf += ch
            if self._buf_job:
                self.after_cancel(self._buf_job)
            if len(self._buf) >= 2:
                self._commit_buf(r, c)
            else:
                self._buf_job = self.after(600, lambda: self._commit_buf(r, c))

    def _commit_buf(self, r, c):
        self._buf_job = None
        try:
            d = int(self._buf)
        except ValueError:
            self._buf = ""
            return
        self._buf = ""
        if 1 <= d <= self.n:
            self._set_cell(r, c, d)

    def _backspace(self, _event):
        if self._won or self._solved_view or self.selected is None:
            return
        r, c = self.selected
        if not self.is_clue[r][c]:
            self.user_grid[r][c] = None
            self._redraw()

    def _nav(self, dr, dc):
        if self.selected is None:
            self.selected = (0, 0)
        else:
            r, c = self.selected
            self.selected = ((r + dr) % self.n, (c + dc) % self.n)
        self._redraw()

    def _set_cell(self, r, c, d):
        self.user_grid[r][c] = d
        self._redraw()
        self._check_win()

    # ── Solve / Win ───────────────────────────────────────────────────────────

    def _do_solve(self):
        self._ticking = False
        self._solved_view = True
        self.selected = None
        for r in range(self.n):
            for c in range(self.n):
                self.user_grid[r][c] = self.solution[r][c]
        self._redraw()

    def _check_win(self):
        for r in range(self.n):
            for c in range(self.n):
                if self.user_grid[r][c] != self.solution[r][c]:
                    return
        self._won = True
        self._ticking = False
        self.after(120, self._show_win)

    def _show_win(self):
        m, s = divmod(self._seconds, 60)
        time_str = f"{m:02d}:{s:02d}"

        win = tk.Toplevel(self)
        win.title("Puzzle Solved!")
        win.configure(bg=C["panel"])
        win.resizable(False, False)
        win.grab_set()
        self.update_idletasks()
        px = self.winfo_rootx() + self.winfo_width() // 2 - 190
        py = self.winfo_rooty() + self.winfo_height() // 2 - 150
        win.geometry(f"380x300+{px}+{py}")

        tk.Label(win, text="✓", bg=C["panel"], fg=C["success"],
                 font=("Segoe UI", 52)).pack(pady=(28, 2))
        tk.Label(win, text="Puzzle Solved!", bg=C["panel"], fg=C["text"],
                 font=("Segoe UI", 22, "bold")).pack()
        tk.Label(win, text=f"Time  {time_str}", bg=C["panel"], fg=C["muted"],
                 font=("Segoe UI", 14)).pack(pady=(6, 2))
        tk.Label(win,
                 text=f"{GAME_LABELS[self.game]}  ·  {self.n}×{self.n}  ·  {self.difficulty.capitalize()}",
                 bg=C["panel"], fg=C["muted"], font=("Segoe UI", 10)).pack()

        bf = tk.Frame(win, bg=C["panel"])
        bf.pack(pady=26)
        _pill(bf, "New Game",
              lambda: (win.destroy(), self.app.show_home())).pack(side="left", padx=8)
        _pill(bf, "Close", win.destroy, primary=False).pack(side="left", padx=8)

    # ── Timer ─────────────────────────────────────────────────────────────────

    def _timer_tick(self):
        if not self._ticking:
            return
        m, s = divmod(self._seconds, 60)
        self._timer_lbl.config(text=f"{m:02d}:{s:02d}")
        self._seconds += 1
        self.after(1000, self._timer_tick)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().mainloop()
