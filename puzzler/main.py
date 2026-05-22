from __future__ import annotations

import random
import time
from argparse import ArgumentParser

from puzzler.sudoku import *
from puzzler.kenken import *
from puzzler.diagonal import *
from puzzler.hyper import *
from puzzler.nonconsecutive import *

EXAMPLE_GRID_9x9 = [
    [6, 4, 0, 8, 0, 0, 2, 5, 0],
    [5, 3, 0, 6, 0, 2, 0, 0, 4],
    [8, 2, 0, 5, 4, 9, 6, 1, 0],
    [2, 1, 0, 0, 0, 0, 0, 4, 5],
    [4, 9, 0, 0, 0, 0, 8, 3, 2],
    [0, 0, 0, 2, 0, 4, 1, 0, 6],
    [3, 0, 4, 0, 2, 0, 5, 6, 0],
    [1, 0, 0, 0, 6, 0, 4, 2, 0],
    [0, 6, 2, 4, 0, 5, 3, 0, 0],
]


_KENKEN_DIFFICULTY: dict = {
    #                max_cage_size  singleton_rate
    "easy":   dict(max_cage_size_factor=0.6,  singleton_rate=0.05),
    "medium": dict(max_cage_size_factor=0.4,  singleton_rate=0.15),
    "hard":   None,   # usa generate_minimal_kenken_puzzle
}


def main() -> None:
    parser = ArgumentParser(description="Logic puzzles using Z3")
    parser.add_argument(
        "--game",
        choices=["sudoku", "kenken", "diagonal", "hyper", "nonconsecutive"],
        default="sudoku",
        help="Tipo di gioco (default: sudoku)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=9,
        help="Dimensione griglia: 4/9/16 per Sudoku, qualsiasi n≥3 per KenKen (default: 9)",
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="Difficoltà (default: medium)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed per riproducibilità (default: casuale)",
    )

    args = parser.parse_args()

    # Seed: usa quello fornito, altrimenti generane uno casuale e stampalo
    seed = args.seed if args.seed is not None else random.randint(0, 99_999)

    game_label = {
        "sudoku":         "Sudoku",
        "kenken":         "KenKen",
        "diagonal":       "Diagonal Sudoku",
        "hyper":          "Hyper Sudoku",
        "nonconsecutive": "Nonconsecutive Sudoku",
    }[args.game]

    print("=" * 54)
    print(f"  Logic Puzzles — {game_label} {args.size}x{args.size}"
          f"  [{args.difficulty}]  seed={seed}")
    print("=" * 54)


# ── Sudoku ────────────────────────────────────────────────────────────────────

    if args.game == "sudoku":        
        start = time.time()

        puzzle, solution = generate_puzzle(args.size, seed=seed, difficulty=args.difficulty)
        elapsed = time.time() - start

        num_clues = sum(1 for row in puzzle for v in row if v != 0)
        print(f"Generato in {elapsed:.1f}s con {num_clues} indizi")
    
        print("\nPuzzle:")
        for row in puzzle:
            print(" ".join(["." if v == 0 else str(v) for v in row]))
        
        print("\nSoluzione:")
        for i in solution:
            print(i)

        # Verifica
        inizio = time.time()
        check = solve_sudoku(puzzle, n=args.size)
        delta = time.time() - inizio
        print(f"Verificato in {delta:.1f}s")
        print(f"\nVerifica: {'✓' if check == solution else '✗'}")


# ── KenKen ────────────────────────────────────────────────────────────────────

    elif args.game == "kenken":
        start = time.time()

        if args.difficulty == "hard":
            max_cage_size = max(2, int(args.size * 0.4))
            solution, cages = generate_minimal_kenken_puzzle(
                args.size,
                max_cage_size=max_cage_size,
                seed=seed,
            )
        else:
            params = _KENKEN_DIFFICULTY[args.difficulty]
            max_cage_size = max(2, int(args.size * params["max_cage_size_factor"]))
            solution, cages = generate_kenken_puzzle(
                args.size,
                max_cage_size=max_cage_size,
                singleton_rate=params["singleton_rate"],
                seed=seed,
            )


        elapsed = time.time() - start
        print(f"\nGenerato in {elapsed:.1f}s  —  {len(cages)} gabbie\n")

        print_kenken_puzzle(solution, cages, show_solution=True)

        # Verifica solver
        start = time.time()
        check = solve_kenken(args.size, cages)
        elapsed = time.time() - start
        print(f"Verificato in {elapsed:.1f}s")
        print(f"\nVerifica solver: {'✓' if check == solution else '✗'}")


# ── Varianti Sudoku ───────────────────────────────────────────────────────────

    elif args.game in ("diagonal", "hyper", "nonconsecutive"):
        n = args.size

        start = time.time()
        if args.game == "diagonal":
            puzzle, solution = generate_diagonal_puzzle(n, seed=seed, difficulty=args.difficulty)
            solver_fn = lambda p: solve_diagonal(p, n)
        elif args.game == "hyper":
            puzzle, solution = generate_hyper_puzzle(n, seed=seed, difficulty=args.difficulty)
            solver_fn = lambda p: solve_hyper(p, n)
        else:
            puzzle, solution = generate_nonconsecutive_puzzle(n, seed=seed, difficulty=args.difficulty)
            solver_fn = lambda p: solve_nonconsecutive(p, n)
        elapsed = time.time() - start

        num_clues = sum(1 for row in puzzle for v in row if v != 0)
        print(f"Generato in {elapsed:.1f}s con {num_clues} indizi")

        print("\nPuzzle:")
        for row in puzzle:
            print(" ".join("." if v == 0 else str(v) for v in row))

        print("\nSoluzione:")
        for row in solution:
            print(" ".join(str(v) for v in row))

        start = time.time()
        check = solver_fn(puzzle)
        delta = time.time() - start
        print(f"\nVerificato in {delta:.1f}s")
        print(f"Verifica: {'✓' if check == solution else '✗'}")


if __name__ == "__main__":
    main()
