# Logic Puzzles

Progetto Python che implementa Sudoku, KenKen e tre varianti Sudoku usando Z3 (z3-solver).

## Avvio rapido — Interfaccia grafica

```bash
python gui.py
```

Apre l'applicazione grafica con cui è possibile giocare a tutti i puzzle direttamente dalla finestra.  
Permette di scegliere gioco, dimensione e difficoltà, mostra il tempo di generazione e offre un timer di gioco, un pulsante **Solve** per rivelare la soluzione e un messaggio di completamento al termine.  
Supporta tema chiaro e scuro (toggle in alto a destra).

---

## Struttura

```
ProgettoCCL/
├── gui.py                       # interfaccia grafica (tkinter)
├── conftest.py
├── pyproject.toml               # dipendenze: z3-solver, pytest
├── puzzler/
│   ├── main.py                  # CLI entry-point
│   ├── core/
│   │   ├── __init__.py
│   │   └── solver_utils.py      # utilità Z3 condivise
│   ├── sudoku/
│   │   ├── __init__.py
│   │   └── model.py             # Sudoku classico 4×4 / 9×9 / 16×16
│   ├── kenken/
│   │   ├── __init__.py
│   │   └── model.py             # KenKen n×n
│   ├── diagonal/
│   │   ├── __init__.py
│   │   └── model.py             # Variante: Diagonal Sudoku
│   ├── hyper/
│   │   ├── __init__.py
│   │   └── model.py             # Variante: Hyper Sudoku
│   └── nonconsecutive/
│       ├── __init__.py
│       └── model.py             # Variante: Nonconsecutive Sudoku
└── tests/
    ├── __init__.py
    └── test_smoke.py
```

## Installazione

```bash
# Installa le dipendenze runtime
pip install z3-solver

# Installa in modalità editable (include dipendenze dev: pytest)
pip install -e ".[dev]"
```

---

## Regole dei giochi

### Sudoku classico

Griglia N×N (N = 4, 9 o 16) divisa in box √N×√N.  
Ogni riga, ogni colonna e ogni box devono contenere tutti i valori da 1 a N esattamente una volta.

---

### KenKen

Griglia N×N (qualsiasi N ≥ 3) senza box.  
Le celle sono raggruppate in **gabbie** (regioni connesse) ognuna con un'operazione e un target:

| Simbolo | Regola |
|---------|--------|
| `n` (singleton) | la cella vale esattamente n |
| `t+` | la somma delle celle della gabbia è t |
| `t*` | il prodotto delle celle è t |
| `t-` | la differenza (in valore assoluto) tra le due celle è t |
| `t/` | il quoziente (maggiore ÷ minore) tra le due celle è t |

Ogni riga e ogni colonna devono contenere tutti i valori da 1 a N (latin square). Le gabbie con `-` e `/` hanno sempre esattamente 2 celle.

---

### Diagonal Sudoku

Tutte le regole del Sudoku classico, più:

- La **diagonale principale** `(0,0)→(N-1,N-1)` deve contenere tutti i valori da 1 a N.
- La **diagonale secondaria** `(0,N-1)→(N-1,0)` deve contenere tutti i valori da 1 a N.

Grazie ai due vincoli extra, il puzzle ammette solitamente meno indizi rispetto al Sudoku classico. Supporta N = 4 e N = 9.

---

### Hyper Sudoku

Tutte le regole del Sudoku classico 9×9, più:

- **4 regioni 3×3 aggiuntive** (le "finestre", evidenziate in grigio nelle versioni cartacee) devono contenere tutti i valori da 1 a 9.

Le finestre sono sfalsate rispetto ai box standard:

```
· · · | · · · | · · ·
· W W W · · W W W ·
· W W W · · W W W ·
· W W W · · W W W ·
· · · | · · · | · · ·
· W W W · · W W W ·
· W W W · · W W W ·
· W W W · · W W W ·
· · · | · · · | · · ·
```

Solo N = 9 supportato.

---

### Nonconsecutive Sudoku

Tutte le regole del Sudoku classico, più:

- Nessuna coppia di celle **ortogonalmente adiacenti** (orizzontale o verticale) può avere valori consecutivi, cioè la differenza assoluta tra celle adiacenti deve essere ≥ 2.

Questo vincolo è sorprendentemente forte: riduce drasticamente il numero di soluzioni valide e permette puzzle unici con pochissimi indizi. Solo N = 9 supportato (N = 4 è impossibile con questa regola).

---

## Esecuzione

### Sudoku classico

```bash
# 9x9 medium (seed casuale)
python -m puzzler.main --game sudoku --size 9 --difficulty medium

# 9x9 hard riproducibile
python -m puzzler.main --game sudoku --size 9 --difficulty hard --seed 42

# 4x4 easy
python -m puzzler.main --game sudoku --size 4 --difficulty easy --seed 7

# 16x16 medium (~30s)
python -m puzzler.main --game sudoku --size 16 --difficulty medium --seed 1
```

### KenKen

```bash
# 4x4 easy
python -m puzzler.main --game kenken --size 4 --difficulty easy --seed 1

# 6x6 medium
python -m puzzler.main --game kenken --size 6 --difficulty medium

# 9x9 medium (~3s in media)
python -m puzzler.main --game kenken --size 9 --difficulty medium

# 9x9 hard (minimal)
python -m puzzler.main --game kenken --size 9 --difficulty hard
```

### Diagonal Sudoku

```bash
# 4x4 medium
python -m puzzler.main --game diagonal --size 4 --difficulty medium --seed 1

# 9x9 easy
python -m puzzler.main --game diagonal --size 9 --difficulty easy

# 9x9 hard (minimal, ~60s)
python -m puzzler.main --game diagonal --size 9 --difficulty hard
```

### Hyper Sudoku

```bash
# 9x9 easy (~10-30s)
python -m puzzler.main --game hyper --size 9 --difficulty easy --seed 1

# 9x9 medium (~30-60s)
python -m puzzler.main --game hyper --size 9 --difficulty medium
```

### Nonconsecutive Sudoku

```bash
# 9x9 easy (~25s)
python -m puzzler.main --game nonconsecutive --size 9 --difficulty easy --seed 1

# 9x9 medium (~25s)
python -m puzzler.main --game nonconsecutive --size 9 --difficulty medium

# 9x9 hard (~60s, ~7-10 indizi — vicino al minimale)
python -m puzzler.main --game nonconsecutive --size 9 --difficulty hard
```

---

## Test

```bash
pytest                   # esegue tutti i test
pytest -v --tb=short     # output verboso
pytest --cov=puzzler     # con copertura del codice
```

---

## Difficoltà

### Sudoku (classico e varianti)

| Livello | Celle visibili (n=9) | Metodo unicità |
|---------|----------------------|----------------|
| easy    | ~55% (~49 indizi)    | Z3             |
| medium  | ~35% (~28 indizi)    | Z3             |
| hard    | minimale             | Z3             |

Per n=16 il check di unicità usa backtracking Python con MRV (Z3 è troppo lento).  
Le varianti (diagonal, hyper, nonconsecutive) supportano solo n=4/9 con Z3.

### KenKen

| Livello | Strategia                | max_cage_size | singleton_rate |
|---------|--------------------------|---------------|----------------|
| easy    | gabbie grandi            | 60% di n      | 5%             |
| medium  | bilanciato               | 40% di n      | 15%            |
| hard    | minimal (greedy)         | 40% di n      | —              |
