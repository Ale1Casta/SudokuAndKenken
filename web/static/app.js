'use strict';

// ── Palette ───────────────────────────────────────────────────────────────────
const LIGHT = {
  bg:'#F7F8FC', panel:'#FFFFFF', accent:'#4F6CF7',
  text:'#1A202C', muted:'#718096',
  clue_bg:'#EEF2FF', user_bg:'#FFFFFF', error_bg:'#FEE2E2', solved_bg:'#D1FAE5',
  diag_tint:'#FFFBEB', hyper_tint:'#FEF3C7', hyper_border:'#D97706',
  line_thin:'#CBD5E0', line_thick:'#2D3748', sel:'#4F6CF7',
  num_clue:'#1A202C', num_user:'#4F6CF7', num_solved:'#059669',
};
const DARK = {
  bg:'#12131F', panel:'#1C1D2E', accent:'#6C8EFF',
  text:'#E2E8F0', muted:'#6B7280',
  clue_bg:'#252848', user_bg:'#1C1D2E', error_bg:'#3B1111', solved_bg:'#0F2E1A',
  diag_tint:'#2A2510', hyper_tint:'#1A1A00', hyper_border:'#D97706',
  line_thin:'#2E3155', line_thick:'#6C8EFF', sel:'#6C8EFF',
  num_clue:'#E2E8F0', num_user:'#6C8EFF', num_solved:'#4ADE80',
};
let C = { ...LIGHT };

// ── Catalogue ─────────────────────────────────────────────────────────────────
const GAME_LABELS = {
  sudoku:'Sudoku', kenken:'KenKen',
  diagonal:'Diagonal Sudoku', hyper:'Hyper Sudoku', nonconsecutive:'Nonconsecutive Sudoku',
};
const GAME_SIZES = {
  sudoku:[4,9,16], kenken:[3,4,5,6,7,8,9],
  diagonal:[4,9], hyper:[9], nonconsecutive:[9],
};
const DIFFS = ['easy','medium','hard'];

// ── State ─────────────────────────────────────────────────────────────────────
let theme   = 'light';
let selGame = 'sudoku';
let selSize = 9;
let selDiff = 'medium';

let G = null; // active game object

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const canvas = $('puzzle-canvas');
const ctx    = canvas.getContext('2d');
const PAD    = 14;

// ── Theme ─────────────────────────────────────────────────────────────────────
function applyTheme() {
  Object.assign(C, theme === 'dark' ? DARK : LIGHT);
  document.documentElement.setAttribute('data-theme', theme);
  $('theme-btn').textContent = theme === 'dark' ? '☀' : '🌙';
  if (G) redraw();
}
$('theme-btn').addEventListener('click', () => {
  theme = theme === 'dark' ? 'light' : 'dark';
  applyTheme();
});

// ── Screens ───────────────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  $(id).classList.add('active');
}

// ── Home screen ───────────────────────────────────────────────────────────────
function buildToggle(containerId, items, getCurrent, onPick) {
  const el = $(containerId);
  el.innerHTML = '';
  items.forEach(item => {
    const b = document.createElement('button');
    b.className = 'btn-toggle' + (item === getCurrent() ? ' active' : '');
    b.textContent = typeof item === 'number' ? `${item}×${item}` : cap(item);
    b.addEventListener('click', () => { onPick(item); buildAllToggles(); });
    el.appendChild(b);
  });
}

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

function buildAllToggles() {
  buildToggle('game-btns', Object.keys(GAME_LABELS), () => selGame, g => {
    selGame = g;
    const sizes = GAME_SIZES[g];
    selSize = sizes.includes(9) ? 9 : sizes[0];
  });
  buildToggle('size-btns', GAME_SIZES[selGame], () => selSize, s => { selSize = s; });
  buildToggle('diff-btns', DIFFS,               () => selDiff, d => { selDiff = d; });
}
buildAllToggles();

$('generate-btn').addEventListener('click', () => {
  startLoading(selGame, selSize, selDiff);
});

// ── Loading ───────────────────────────────────────────────────────────────────
let dotFrame = 0, dotTimer = null;
const RING = [0,1,2,5,8,7,6,3]; // clockwise ring indices in 3×3 grid

function animateDots() {
  const dots = document.querySelectorAll('.dots-grid span');
  dots.forEach(d => d.classList.remove('on'));
  const lit = [RING[dotFrame % 8], RING[(dotFrame+1) % 8], RING[(dotFrame+2) % 8]];
  lit.forEach(i => dots[i].classList.add('on'));
  dotFrame++;
}

function startLoading(game, n, diff) {
  $('loading-title').textContent = GAME_LABELS[game];
  $('loading-sub').textContent   = `${n}×${n}  ·  ${cap(diff)}`;
  showScreen('screen-loading');
  dotFrame = 0;
  animateDots();
  if (dotTimer) clearInterval(dotTimer);
  dotTimer = setInterval(animateDots, 120);

  fetch('/api/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game, n, difficulty: diff }),
  })
  .then(r => r.json())
  .then(data => {
    clearInterval(dotTimer);
    if (data.error) { alert('Errore: ' + data.error); showScreen('screen-home'); return; }
    startGame(game, n, diff, data);
  })
  .catch(err => {
    clearInterval(dotTimer);
    alert('Errore di rete: ' + err);
    showScreen('screen-home');
  });
}

// ── Game setup ────────────────────────────────────────────────────────────────
function startGame(type, n, diff, data) {
  const { puzzle, solution, cages, elapsed, seed } = data;

  // Build cageOf lookup
  let cageOf = null;
  if (cages) {
    cageOf = Array.from({length: n}, () => new Array(n).fill(-1));
    cages.forEach((cage, i) => cage.cells.forEach(([r,c]) => cageOf[r][c] = i));
  }

  // User grid — null = empty
  const userGrid = puzzle.map(row => row.map(v => v || null));
  const isClue   = puzzle.map(row => row.map(v => v !== 0));

  G = {
    type, n, diff, seed, puzzle, solution, cages, cageOf,
    userGrid, isClue,
    selected: null,
    solved: false,
    won: false,
    seconds: 0,
    timerInterval: null,
    elapsed,
  };

  // UI labels
  $('game-title-lbl').textContent = GAME_LABELS[type];
  $('game-meta-lbl').textContent  = `${n}×${n}  ·  ${cap(diff)}  ·  seed ${seed}`;
  $('gen-time-lbl').textContent   = `Generato in ${elapsed}s`;

  setupCanvas();
  buildNumpad();
  showScreen('screen-game');
  redraw();
  startTimer();
}

// ── Canvas ────────────────────────────────────────────────────────────────────
function canvasLogicalSize() {
  const maxW = Math.min(window.innerWidth  - 32, 560);
  const maxH = Math.min(window.innerHeight - 280, 560);
  return Math.max(Math.min(maxW, maxH), 200);
}

function setupCanvas() {
  const dpr  = window.devicePixelRatio || 1;
  const size = canvasLogicalSize();
  canvas.width  = size * dpr;
  canvas.height = size * dpr;
  canvas.style.width  = size + 'px';
  canvas.style.height = size + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function cs() {                          // cell size in logical px
  if (!G) return 40;
  return Math.floor((canvasLogicalSize() - PAD * 2) / G.n);
}

function cellBox(r, c) {
  const s = cs();
  return [PAD + c*s, PAD + r*s, s, s];
}

function fillCell(r, c, color) {
  const [x, y, w, h] = cellBox(r, c);
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w, h);
}

function cellBgColor(r, c) {
  const v = G.userGrid[r][c];
  const n = G.n;
  if (G.isClue[r][c])                                        return C.clue_bg;
  if (G.solved && v !== null && v === G.solution[r][c])      return C.solved_bg;
  if (v !== null && v !== G.solution[r][c])                  return C.error_bg;
  if (G.type === 'diagonal' && (r===c || r===n-1-c))         return C.diag_tint;
  if (G.type === 'hyper'    && inHyperWindow(r,c))           return C.hyper_tint;
  return C.user_bg;
}

function inHyperWindow(r, c) {
  return [[1,1],[1,5],[5,1],[5,5]].some(([wr,wc]) => r>=wr&&r<wr+3&&c>=wc&&c<wc+3);
}

function redraw() {
  if (!G) return;
  const n = G.n, s = cs(), totalPx = PAD*2 + n*s;
  ctx.clearRect(0, 0, totalPx, totalPx);

  // Cell backgrounds
  for (let r=0; r<n; r++)
    for (let c=0; c<n; c++)
      fillCell(r, c, cellBgColor(r, c));

  // Grid lines
  drawLines();

  // Hyper window borders
  if (G.type === 'hyper') drawHyperBorders();

  // Values
  for (let r=0; r<n; r++)
    for (let c=0; c<n; c++)
      drawValue(r, c);

  // Cage labels
  if (G.cages) drawCageLabels();

  // Selection
  if (G.selected && !G.solved && !G.won) {
    const {r, c} = G.selected;
    const [x, y, w, h] = cellBox(r, c);
    ctx.strokeStyle = C.sel;
    ctx.lineWidth   = 2.5;
    ctx.strokeRect(x+2, y+2, w-4, h-4);
  }
}

function drawLines() {
  const n = G.n, s = cs(), total = PAD*2 + n*s;
  if (G.cageOf) {
    // KenKen: thin lattice
    ctx.strokeStyle = C.line_thin; ctx.lineWidth = 1;
    for (let i=0; i<=n; i++) {
      const p = PAD + i*s;
      ctx.beginPath(); ctx.moveTo(p, PAD); ctx.lineTo(p, PAD+n*s); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(PAD, p); ctx.lineTo(PAD+n*s, p); ctx.stroke();
    }
    drawCageBorders();
  } else {
    const box = Math.round(Math.sqrt(n));
    for (let i=0; i<=n; i++) {
      const thick = i % box === 0;
      ctx.strokeStyle = thick ? C.line_thick : C.line_thin;
      ctx.lineWidth   = thick ? 2.5 : 1;
      const p = PAD + i*s;
      ctx.beginPath(); ctx.moveTo(p, PAD);     ctx.lineTo(p, PAD+n*s); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(PAD, p);     ctx.lineTo(PAD+n*s, p); ctx.stroke();
    }
  }
  ctx.strokeStyle = C.line_thick; ctx.lineWidth = 3;
  ctx.strokeRect(PAD, PAD, n*s, n*s);
}

function drawCageBorders() {
  const n = G.n, s = cs();
  ctx.strokeStyle = C.line_thick; ctx.lineWidth = 2.5;
  for (let r=0; r<n; r++) {
    for (let c=0; c<n; c++) {
      const cid = G.cageOf[r][c];
      const [x0,y0,,] = cellBox(r,c);
      const x1=x0+s, y1=y0+s;
      if (c+1<n && G.cageOf[r][c+1]!==cid) {
        ctx.beginPath(); ctx.moveTo(x1,y0); ctx.lineTo(x1,y1); ctx.stroke();
      }
      if (r+1<n && G.cageOf[r+1][c]!==cid) {
        ctx.beginPath(); ctx.moveTo(x0,y1); ctx.lineTo(x1,y1); ctx.stroke();
      }
    }
  }
}

function drawHyperBorders() {
  const s = cs();
  ctx.strokeStyle = C.hyper_border; ctx.lineWidth = 2.5;
  [[1,1],[1,5],[5,1],[5,5]].forEach(([wr,wc]) => {
    ctx.strokeRect(PAD+wc*s, PAD+wr*s, 3*s, 3*s);
  });
}

function drawCageLabels() {
  const s = cs(), n = G.n;
  const fontSize = Math.max(7, Math.min(11, Math.floor(s * 0.26)));
  ctx.font      = `600 ${fontSize}px -apple-system, sans-serif`;
  ctx.fillStyle = C.text;
  ctx.textAlign = 'left'; ctx.textBaseline = 'top';
  G.cages.forEach(cage => {
    const [tr, tc] = cage.cells[0];
    const [x0, y0] = [PAD + tc*s + 3, PAD + tr*s + 2];
    const label = cage.op === '1' ? String(cage.target) : `${cage.target}${cage.op}`;
    ctx.fillText(label, x0, y0);
  });
}

function drawValue(r, c) {
  const v = G.userGrid[r][c];
  if (v === null) return;
  const [x, y, w, h] = cellBox(r, c);
  const s = cs(), n = G.n;
  const fontSize = Math.max(10, Math.floor(s * (n<=4?.5 : n<=9?.42 : .32)));
  ctx.font      = `${G.isClue[r][c] ? '700' : '500'} ${fontSize}px -apple-system, sans-serif`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillStyle = G.isClue[r][c] ? C.num_clue
                : G.solved        ? C.num_solved
                :                   C.num_user;
  ctx.fillText(String(v), x + w/2, y + h/2);
}

// ── Numpad ────────────────────────────────────────────────────────────────────
function buildNumpad() {
  const pad = $('numpad');
  pad.innerHTML = '';
  const n = G.n;
  for (let i=1; i<=n; i++) {
    const b = document.createElement('button');
    b.className   = 'num-btn';
    b.textContent = i;
    b.addEventListener('click', () => inputDigit(i));
    pad.appendChild(b);
  }
  const del = document.createElement('button');
  del.className   = 'num-btn erase';
  del.textContent = '⌫';
  del.addEventListener('click', () => eraseCell());
  pad.appendChild(del);
}

// ── Input ─────────────────────────────────────────────────────────────────────
function getCanvasCoords(e) {
  const rect = canvas.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  return { x: src.clientX - rect.left, y: src.clientY - rect.top };
}

canvas.addEventListener('click', handleCanvasInput);
canvas.addEventListener('touchstart', e => {
  e.preventDefault();
  handleCanvasInput(e);
}, { passive: false });

function handleCanvasInput(e) {
  if (!G || G.solved || G.won) return;
  const { x, y } = getCanvasCoords(e);
  const s = cs();
  const c = Math.floor((x - PAD) / s);
  const r = Math.floor((y - PAD) / s);
  if (r < 0 || r >= G.n || c < 0 || c >= G.n) return;
  if (G.isClue[r][c]) return;
  G.selected = { r, c };
  redraw();
}

// Keyboard (desktop) — multi-digit buffer for 16×16
let _kbBuf = '', _kbTimer = null;
function _kbFlush() {
  if (_kbBuf) { inputDigit(parseInt(_kbBuf)); _kbBuf = ''; }
}

document.addEventListener('keydown', e => {
  if (!G || G.solved || G.won || !G.selected) return;

  if (e.key >= '0' && e.key <= '9') {
    _kbBuf += e.key;
    if (_kbTimer) clearTimeout(_kbTimer);
    const d = parseInt(_kbBuf);
    // Commit immediately if digit is valid and one more digit would definitely exceed n
    if (d >= 1 && d <= G.n && (G.n <= 9 || _kbBuf.length >= 2)) {
      _kbBuf = ''; _kbTimer = null;
      inputDigit(d);
    } else {
      _kbTimer = setTimeout(() => { _kbFlush(); _kbTimer = null; }, 600);
    }
    return;
  }
  _kbFlush();   // any non-digit key commits the buffer first
  if (e.key === 'Backspace' || e.key === 'Delete') { eraseCell(); return; }
  const dirs = { ArrowUp:[-1,0], ArrowDown:[1,0], ArrowLeft:[0,-1], ArrowRight:[0,1] };
  if (dirs[e.key]) {
    const [dr, dc] = dirs[e.key];
    G.selected = {
      r: (G.selected.r + dr + G.n) % G.n,
      c: (G.selected.c + dc + G.n) % G.n,
    };
    redraw();
  }
});

function inputDigit(d) {
  if (!G || G.solved || G.won || !G.selected) return;
  const { r, c } = G.selected;
  if (G.isClue[r][c]) return;
  if (d < 1 || d > G.n) return;
  G.userGrid[r][c] = d;
  redraw();
  checkWin();
}

function eraseCell() {
  if (!G || G.solved || G.won || !G.selected) return;
  const { r, c } = G.selected;
  if (!G.isClue[r][c]) { G.userGrid[r][c] = null; redraw(); }
}

// ── Buttons ───────────────────────────────────────────────────────────────────
$('menu-btn').addEventListener('click', () => {
  stopTimer();
  G = null;
  showScreen('screen-home');
});

$('solve-btn').addEventListener('click', () => {
  if (!G) return;
  stopTimer();
  G.solved   = true;
  G.selected = null;
  G.userGrid = G.solution.map(row => [...row]);
  redraw();
});

// ── Timer ─────────────────────────────────────────────────────────────────────
function fmtTime(s) {
  const m = Math.floor(s/60);
  return `${String(m).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
}
function startTimer() {
  stopTimer();
  G.seconds = 0;
  $('timer-lbl').textContent = '00:00';
  G.timerInterval = setInterval(() => {
    G.seconds++;
    $('timer-lbl').textContent = fmtTime(G.seconds);
  }, 1000);
}
function stopTimer() {
  if (G && G.timerInterval) { clearInterval(G.timerInterval); G.timerInterval = null; }
}

// ── Win ───────────────────────────────────────────────────────────────────────
function checkWin() {
  if (!G) return;
  for (let r=0; r<G.n; r++)
    for (let c=0; c<G.n; c++)
      if (G.userGrid[r][c] !== G.solution[r][c]) return;
  G.won = true;
  stopTimer();
  setTimeout(showWin, 150);
}

function showWin() {
  $('win-time').textContent = fmtTime(G.seconds);
  $('win-info').textContent =
    `${GAME_LABELS[G.type]}  ·  ${G.n}×${G.n}  ·  ${cap(G.diff)}`;
  $('win-overlay').classList.remove('hidden');
}

$('win-close-btn').addEventListener('click', () => {
  $('win-overlay').classList.add('hidden');
});
$('win-new-btn').addEventListener('click', () => {
  $('win-overlay').classList.add('hidden');
  stopTimer(); G = null;
  showScreen('screen-home');
});

// ── Resize ────────────────────────────────────────────────────────────────────
window.addEventListener('resize', () => {
  if (G) { setupCanvas(); redraw(); }
});

// ── PWA service worker ────────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}
