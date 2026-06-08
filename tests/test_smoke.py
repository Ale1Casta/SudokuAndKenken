from puzzler.sudoku import *
from puzzler.kenken import *
from puzzler.diagonal import *
from puzzler.hyper import *
from puzzler.nonconsecutive import *


# ── Sudoku ────────────────────────────────────────────────────────────────────

def test_can_build_sudoku_model():
    s, X = build_sudoku_model(4)
    assert len(X) == 4 and len(X[0]) == 4


def test_can_solve_trivial_empty_4x4():
    # Sudoku 4x4 vuoto deve avere almeno una soluzione
    sol = solve_sudoku(None, n=4)
    assert sol is not None
    assert len(sol) == 4 and len(sol[0]) == 4

def test_generate_puzzle_unique():
    puzzle, solution = generate_puzzle(4, seed=42, difficulty="medium")
    
    # Deve risolversi correttamente
    solved = solve_sudoku(puzzle, n=4)
    assert solved == solution
    
    # Deve essere unica
    assert is_puzzle_unique(solution, puzzle, 4)


# ── KenKen ────────────────────────────────────────────────────────────────────

def test_kenken_solution_varies_with_seed():
    """Seed diversi devono produrre griglie diverse"""
    sol_a = generate_full_kenken_solution(4, seed=1)
    sol_b = generate_full_kenken_solution(4, seed=2)
    assert sol_a != sol_b, "Seed diversi devono generare soluzioni diverse"


def test_kenken_solution_reproducible():
    """Lo stesso seed deve produrre sempre la stessa griglia."""
    sol_a = generate_full_kenken_solution(4, seed=42)
    sol_b = generate_full_kenken_solution(4, seed=42)
    assert sol_a == sol_b


def test_kenken_solution_is_valid_latin_square():
    """Verifica che la soluzione sia un latin square valido."""
    n = 4
    sol = generate_full_kenken_solution(n, seed=7)
    for r in range(n):
        assert sorted(sol[r]) == list(range(1, n + 1)), f"Riga {r} non valida"
    for c in range(n):
        col = [sol[r][c] for r in range(n)]
        assert sorted(col) == list(range(1, n + 1)), f"Colonna {c} non valida"


def test_kenken_cages_cover_all_cells():
    """Ogni cella deve apparire esattamente una volta nelle gabbie."""
    n = 4
    _, cages = generate_kenken_puzzle(n, seed=42)
    all_cells = [cell for cage in cages for cell in cage["cells"]]
    assert len(all_cells) == n * n
    assert len(set(all_cells)) == n * n, "Celle duplicate nelle gabbie"


def test_kenken_cages_are_connected():
    """Ogni gabbia deve essere un polinomio connesso."""
    from collections import deque

    n = 5
    _, cages = generate_kenken_puzzle(n, seed=99)

    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    for cage in cages:
        cells = set(cage["cells"])
        if len(cells) <= 1:
            continue
        # BFS da una cella qualsiasi
        start = next(iter(cells))
        visited = {start}
        queue = deque([start])
        while queue:
            r, c = queue.popleft()
            for dr, dc in directions:
                nb = (r + dr, c + dc)
                if nb in cells and nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
        assert visited == cells, f"Gabbia non connessa: {cage}"


def test_kenken_puzzle_has_unique_solution():
    """Il puzzle generato deve avere soluzione unica."""
    n = 4
    solution, cages = generate_kenken_puzzle(n, seed=42)
    check = solve_kenken(n, cages)
    assert check == solution, "Il solver non ritrova la soluzione corretta"


def test_kenken_different_seeds_produce_different_puzzles():
    """Seed diversi devono produrre puzzle diversi end-to-end."""
    _, cages_a = generate_kenken_puzzle(4, seed=10)
    _, cages_b = generate_kenken_puzzle(4, seed=20)
    targets_a = sorted(c["target"] for c in cages_a)
    targets_b = sorted(c["target"] for c in cages_b)
    assert targets_a != targets_b, "Puzzle identici con seed diversi"


# ── Diagonal Sudoku ───────────────────────────────────────────────────────────

def test_diagonal_model_builds():
    s, X = build_diagonal_model(4)
    assert len(X) == 4 and len(X[0]) == 4


def test_diagonal_solver_finds_solution():
    sol = solve_diagonal(n=4)
    assert sol is not None
    n = 4
    # Verifica diagonale principale distinta
    main_diag = [sol[i][i] for i in range(n)]
    assert len(set(main_diag)) == n, "Diagonale principale con ripetizioni"
    # Verifica diagonale secondaria distinta
    anti_diag = [sol[i][n-1-i] for i in range(n)]
    assert len(set(anti_diag)) == n, "Diagonale secondaria con ripetizioni"


def test_diagonal_puzzle_unique():
    from puzzler.diagonal.model import _check_unique_diag
    puzzle, solution = generate_diagonal_puzzle(n=4, seed=42, difficulty="medium")
    solved = solve_diagonal(puzzle, n=4)
    assert solved == solution, "Il solver non ritrova la soluzione corretta"
    assert _check_unique_diag(puzzle, 4), "Il puzzle non ha soluzione unica"


# ── Hyper Sudoku ──────────────────────────────────────────────────────────────

def test_hyper_model_builds():
    s, X = build_hyper_model(9)
    assert len(X) == 9 and len(X[0]) == 9


def test_hyper_solver_finds_solution():
    sol = solve_hyper(n=9)
    assert sol is not None
    # Verifica che le 4 finestre hyper abbiano valori distinti
    for window in get_windows():
        vals = [sol[r][c] for r, c in window]
        assert len(set(vals)) == 9, f"Finestra hyper con ripetizioni: {window}"


def test_hyper_puzzle_unique():
    from puzzler.hyper.model import _check_unique_hyper
    puzzle, solution = generate_hyper_puzzle(n=9, seed=42, difficulty="medium")
    solved = solve_hyper(puzzle, n=9)
    assert solved == solution, "Il solver non ritrova la soluzione corretta"
    assert _check_unique_hyper(puzzle), "Il puzzle non ha soluzione unica"


# ── Nonconsecutive Sudoku ─────────────────────────────────────────────────────

def test_nonconsecutive_model_builds():
    s, X = build_nonconsecutive_model(9)
    assert len(X) == 9 and len(X[0]) == 9


def test_nonconsecutive_solver_finds_solution():
    sol = solve_nonconsecutive(n=9)
    assert sol is not None
    n = 9
    # Verifica che nessuna coppia adiacente abbia valori consecutivi
    for r in range(n):
        for c in range(n):
            for dr, dc in [(0, 1), (1, 0)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n:
                    assert abs(sol[r][c] - sol[nr][nc]) != 1, (
                        f"Coppia consecutiva in ({r},{c})-({nr},{nc}): "
                        f"{sol[r][c]} e {sol[nr][nc]}"
                    )


def test_nonconsecutive_puzzle_unique():
    from puzzler.nonconsecutive.model import _check_unique_nc
    puzzle, solution = generate_nonconsecutive_puzzle(n=9, seed=42, difficulty="medium")
    solved = solve_nonconsecutive(puzzle, n=9)
    assert solved == solution, "Il solver non ritrova la soluzione corretta"
    assert _check_unique_nc(puzzle, 9), "Il puzzle non ha soluzione unica"
