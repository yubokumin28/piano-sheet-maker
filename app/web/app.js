/* Piano Sheet(自作版)画面の動き */
'use strict';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const LEVEL = { 1: '入門', 2: '初級', 3: '中級', 4: '上級' };
const KEYM = { auto: 'おまかせ', easy: '簡単キー', original: '原曲キー' };
const LEN = { full: 'フル', short: '1コーラス' };
const STYLE = { solo: 'ソロ譜', accomp: '伴奏譜' };
const HELP = {
  level: {
    1: '入門: 右手はメロディだけ(4分音符まで)、左手は1小節に1音。はじめてピアノを弾く人向け。',
    2: '初級: 右手はメロディ(8分音符まで)、左手はコードの根音を2拍ずつ。',
    3: '中級: 右手のメロディに和音を少し足し、左手は2音の和音。',
    4: '上級: 右手はメロディ+和音、休みの所はコードで埋め、左手は8分音符の分散和音。',
  },
  style: { solo: 'ソロ譜: 右手がメロディ、左手が伴奏。', accomp: '伴奏譜: メロディを入れず、右手もコードを弾く(弾き語り・歌の伴奏用)。' },
};

// ---------------- 共通 ----------------
async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('json') ? res.json() : res.text();
}
function toast(msg, ms = 2600) {
  const t = $('#toast');
  t.textContent = msg; t.classList.remove('hidden');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add('hidden'), ms);
}
function openModal(id) { $(id).classList.remove('hidden'); }
function closeModal(id) { $(id).classList.add('hidden'); }
$$('.modal').forEach((m) => {
  m.addEventListener('click', (e) => { if (e.target === m && m.id !== 'dlgCreate') closeModal('#' + m.id); });
  $$('[data-close]', m).forEach((b) => b.addEventListener('click', () => closeModal('#' + m.id)));
});
function confirmBox(title, body, yes = 'OK') {
  return new Promise((resolve) => {
    $('#cfTitle').textContent = title; $('#cfBody').textContent = body; $('#cfYes').textContent = yes;
    openModal('#dlgConfirm');
    const done = (v) => { closeModal('#dlgConfirm'); $('#cfYes').onclick = $('#cfNo').onclick = null; resolve(v); };
    $('#cfYes').onclick = () => done(true);
    $('#cfNo').onclick = () => done(false);
  });
}
function segValue(root, name) { const b = $(`.seg[data-name="${name}"] button.on`, root); return b ? b.dataset.v : null; }
function segSet(root, name, v) { $$(`.seg[data-name="${name}"] button`, root).forEach((b) => b.classList.toggle('on', b.dataset.v === String(v))); }
$$('.seg').forEach((seg) => seg.addEventListener('click', (e) => {
  const b = e.target.closest('button'); if (!b) return;
  $$('button', seg).forEach((x) => x.classList.toggle('on', x === b));
  updateHelp();
}));
const clone = (o) => JSON.parse(JSON.stringify(o));
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---------------- ホーム ----------------
let scores = [];
let pollTimer = null;

async function loadList() {
  try { scores = await api('/api/scores'); } catch (e) { toast('一覧を読めませんでした: ' + e.message); return; }
  renderList();
  clearTimeout(pollTimer);
  if (scores.some((s) => s.status === 'processing')) pollTimer = setTimeout(loadList, 1500);
}

function renderList() {
  const q = $('#search').value.trim().toLowerCase();
  const rows = scores.filter((s) => !q || `${s.title} ${s.artist}`.toLowerCase().includes(q));
  $('#emptyHint').classList.toggle('hidden', scores.length > 0);
  $('#scoreList').innerHTML = rows.map((s) => {
    let right;
    if (s.status === 'processing') {
      right = `<div class="score-prog"><div class="progress"><div class="progress-bar" style="width:${s.progress || 2}%"></div></div><small>${esc(s.message || '変換中')}</small></div>`;
    } else if (s.status === 'error' || s.status === 'cancelled') {
      right = `<span class="chip err">${s.status === 'error' ? '失敗' : 'キャンセル'}</span>`;
    } else {
      right = `<span class="score-date">${esc((s.updated_at || '').slice(0, 16))}</span>`;
    }
    const chips = s.status === 'ready'
      ? `<span class="chip">${LEVEL[s.level] || ''}</span><span class="chip">${STYLE[s.style] || ''}</span><span>${esc(s.key_name || '')}</span><span>${s.tempo ? '♩=' + s.tempo : ''}</span><span>${s.measures ? s.measures + '小節' : ''}</span>`
      : `<span>${esc(s.source_name || '')}</span>${s.error && s.status === 'error' ? `<span class="chip err" title="${esc(s.error)}">${esc(s.error.slice(0, 40))}</span>` : ''}`;
    return `<li class="score-item" data-id="${s.id}" data-status="${s.status}">
      <div class="score-thumb">&#9835;</div>
      <div class="score-main"><div class="score-title">${esc(s.title)}${s.artist ? ` <span style="font-weight:400;color:var(--sub)">/ ${esc(s.artist)}</span>` : ''}</div>
      <div class="score-meta">${chips}</div></div>
      ${right}
      <button class="icon-btn" data-del="${s.id}" title="削除">&#128465;</button>
    </li>`;
  }).join('');
}

$('#search').addEventListener('input', renderList);
$('#scoreList').addEventListener('click', async (e) => {
  const del = e.target.closest('[data-del]');
  if (del) {
    e.stopPropagation();
    const s = scores.find((x) => x.id === del.dataset.del);
    if (await confirmBox('楽譜を削除しますか?', `「${s ? s.title : ''}」を削除します。元に戻せません。`, '削除する')) {
      await api('/api/scores/' + del.dataset.del, { method: 'DELETE' });
      toast('削除しました'); loadList();
    }
    return;
  }
  const li = e.target.closest('.score-item'); if (!li) return;
  if (li.dataset.status === 'ready') openEditor(li.dataset.id);
  else if (li.dataset.status === 'processing') showProgress(li.dataset.id, scores.find((x) => x.id === li.dataset.id)?.title);
  else toast('この楽譜は作れませんでした。削除して、もう一度お試しください。');
});

// ---------------- 新しい楽譜 ----------------
let pickedFile = null;
let watching = null;

function updateHelp() {
  const f = $('#createForm');
  $('#optHelp').innerHTML = `${HELP.level[segValue(f, 'level')] || ''}<br>${HELP.style[segValue(f, 'style')] || ''}`;
}
function pickFile(f) {
  if (!f) return;
  pickedFile = f;
  $('#dropText').textContent = f.name;
  $('#drop').classList.add('has-file');
  $('#btnStart').disabled = false;
}
$('#btnNew').addEventListener('click', () => {
  pickedFile = null; $('#fileInput').value = '';
  $('#dropText').textContent = 'ここに音源をドロップ、またはクリックして選ぶ';
  $('#drop').classList.remove('has-file'); $('#btnStart').disabled = true;
  $('#createForm').classList.remove('hidden'); $('#createProgress').classList.add('hidden');
  updateHelp(); openModal('#dlgCreate');
});
$('#fileInput').addEventListener('change', (e) => pickFile(e.target.files[0]));
const drop = $('#drop');
['dragenter', 'dragover'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', (e) => pickFile(e.dataTransfer.files[0]));

$('#btnStart').addEventListener('click', async () => {
  if (!pickedFile) return;
  const f = $('#createForm');
  const fd = new FormData();
  fd.append('file', pickedFile);
  ['level', 'key_mode', 'length', 'style'].forEach((k) => fd.append(k, segValue(f, k)));
  $('#btnStart').disabled = true;
  try {
    const { id } = await api('/api/scores', { method: 'POST', body: fd });
    showProgress(id, pickedFile.name);
    loadList();
  } catch (e) {
    toast('始められませんでした: ' + e.message);
    $('#btnStart').disabled = false;
  }
});

function showProgress(id, title) {
  watching = id;
  $('#createForm').classList.add('hidden');
  $('#createProgress').classList.remove('hidden');
  $('#progTitle').textContent = title || '';
  $('#progBar').style.width = '2%';
  $('#progMsg').textContent = '準備中';
  openModal('#dlgCreate');
  pollProgress(id);
}
async function pollProgress(id) {
  if (watching !== id) return;
  let s;
  try { s = await api('/api/scores/' + id); } catch (_) { setTimeout(() => pollProgress(id), 1500); return; }
  $('#progBar').style.width = (s.progress || 2) + '%';
  $('#progMsg').textContent = s.message || '';
  if (s.status === 'processing') { setTimeout(() => pollProgress(id), 1000); return; }
  watching = null;
  closeModal('#dlgCreate');
  loadList();
  if (s.status === 'ready') openEditor(id);
  else if (s.status === 'error') toast('作れませんでした: ' + (s.error || ''), 6000);
}
$('#btnCancelConvert').addEventListener('click', async () => {
  if (!watching) return;
  await api(`/api/scores/${watching}/cancel`, { method: 'POST' });
  $('#progMsg').textContent = 'キャンセルしています…';
});
$('#btnBg').addEventListener('click', () => { watching = null; closeModal('#dlgCreate'); loadList(); });

// ================= 楽譜画面 =================
const ED = {
  id: null, model: null, work: null, mode: 'play', zoom: 1, osmd: null,
  index: [], sel: null, undo: [], dirty: false, startBeat: 0, cursorSteps: [], cursorIdx: 0,
};

function showScreen(name) {
  $$('.screen').forEach((s) => s.classList.toggle('active', s.id === name));
}

async function openEditor(id) {
  stopPlayback();
  ED.id = id; ED.sel = null; ED.undo = []; ED.dirty = false; ED.startBeat = 0;
  showScreen('editor');
  setMode('play');
  $('#sheetLoading').classList.remove('hidden');
  try {
    ED.model = await api(`/api/scores/${id}/model`);
    ED.work = clone(ED.model);
    updateHeader();
    const xml = await api(`/api/scores/${id}/musicxml?t=${Date.now()}`);
    await renderXml(xml);
  } catch (e) {
    toast('楽譜を開けませんでした: ' + e.message, 5000);
  } finally {
    $('#sheetLoading').classList.add('hidden');
  }
}

function updateHeader() {
  const m = ED.work.meta;
  $('#edTitle').value = m.title || '';
  const tr = m.transpose ? `(原曲 ${m.orig_key_name} から ${m.transpose > 0 ? '+' : ''}${m.transpose})` : '';
  $('#edSub').textContent = [m.artist, LEVEL[m.level], STYLE[m.style], LEN[m.length], `${m.key_name}${tr}`, `♩=${m.tempo}`, `${m.measures}小節`]
    .filter(Boolean).join(' ・ ');
}

async function renderXml(xml) {
  const el = $('#sheet');
  if (!ED.osmd) {
    ED.osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(el, {
      autoResize: true, backend: 'svg', drawTitle: true, drawComposer: true, drawPartNames: false,
      drawMeasureNumbers: true, followCursor: false, cursorsOptions: [{ type: 0, color: '#e8505b', alpha: 0.35, follow: false }],
    });
    ED.osmd.handleResize(() => {}, () => afterRender());
  }
  await ED.osmd.load(xml);
  ED.osmd.zoom = ED.zoom;
  ED.osmd.render();
  afterRender();
}

function afterRender() {
  buildIndex();
  buildCursor();
  highlightSel();
}

// ---- 描いた音符と model の対応表を作る(クリックで選ぶため) ----
function buildIndex() {
  ED.index = [];
  const gs = ED.osmd.GraphicSheet;
  if (!gs) return;
  gs.MeasureList.forEach((row) => {
    row.forEach((gm, staff) => {
      if (!gm) return;
      gm.staffEntries.forEach((se) => se.graphicalVoiceEntries.forEach((gve) => gve.notes.forEach((gn) => {
        const sn = gn.sourceNote;
        let el = null;
        try { el = gn.getSVGGElement(); } catch (_) {}
        if (!el) return;
        const ts = sn.getAbsoluteTimestamp ? sn.getAbsoluteTimestamp().RealValue
          : sn.SourceMeasure.AbsoluteTimestamp.RealValue + sn.voiceEntry.Timestamp.RealValue;
        const entry = {
          el, hand: staff === 0 ? 'rh' : 'lh', beat: ts * 4, len: sn.Length.RealValue * 4,
          rest: sn.isRest(), midi: sn.isRest() ? null : sn.halfTone + 12,
        };
        ED.index.push(entry);
        if (!el.dataset.bound) {
          el.dataset.bound = '1';
          el.addEventListener('click', (ev) => { ev.stopPropagation(); onNoteClick(el); });
        }
      })));
    });
  });
}

function onNoteClick(el) {
  const cands = ED.index.filter((x) => x.el === el);
  if (!cands.length) return;
  if (ED.mode === 'play') {
    seekTo(cands[0].beat);
    if (Tone.Transport.state === 'started') { pausePlayback(); startPlayback(); }
    return;
  }
  // 和音は、クリックするたびに上の音から順に選び直す
  cands.sort((a, b) => (b.midi || 0) - (a.midi || 0));
  let next = cands[0];
  if (ED.sel && ED.sel.el === el) {
    const i = cands.findIndex((c) => c.midi === ED.sel.midi);
    next = cands[(i + 1) % cands.length];
  }
  ED.sel = { ...next };
  highlightSel();
  updateSelInfo();
}

function highlightSel() {
  $$('#sheet svg .sel').forEach((g) => g.classList.remove('sel'));
  if (!ED.sel) return;
  const m = ED.index.find((x) => x.hand === ED.sel.hand && Math.abs(x.beat - ED.sel.beat) < 1e-3 && x.midi === ED.sel.midi)
    || ED.index.find((x) => x.hand === ED.sel.hand && Math.abs(x.beat - ED.sel.beat) < 1e-3);
  if (m) { ED.sel.el = m.el; m.el.classList.add('sel'); }
}

const NAMES_S = ['ド', 'ド#', 'レ', 'レ#', 'ミ', 'ファ', 'ファ#', 'ソ', 'ソ#', 'ラ', 'ラ#', 'シ'];
const NAMES_F = ['ド', 'レ♭', 'レ', 'ミ♭', 'ミ', 'ファ', 'ソ♭', 'ソ', 'ラ♭', 'ラ', 'シ♭', 'シ'];
function pitchName(m) {
  const f = ED.work.meta.fifths || 0;
  const pc = m % 12;
  const sharp = f >= 2 || (f > -2 && f >= 0 && pc === 6);
  return `${(sharp ? NAMES_S : NAMES_F)[pc]}${Math.floor(m / 12) - 1}`;
}
function durName(d) {
  const t = { 0.25: '16分', 0.5: '8分', 0.75: '付点8分', 1: '4分', 1.5: '付点4分', 2: '2分', 3: '付点2分', 4: '全音符' };
  return t[d] || `${d}拍`;
}

function findNote(sel) {
  const arr = ED.work[sel.hand];
  const eps = 1e-3;
  let idx = arr.findIndex((n) => n.p.includes(sel.midi) && n.o <= sel.beat + eps && sel.beat < n.o + n.d - eps);
  if (idx < 0) idx = arr.findIndex((n) => Math.abs(n.o - sel.beat) < eps);
  return idx;
}

function updateSelInfo() {
  const s = ED.sel;
  if (!s) { $('#selInfo').textContent = '音符をクリックして選んでください'; return; }
  const measure = Math.floor(s.beat / 4) + 1;
  const hand = s.hand === 'rh' ? '右手' : '左手';
  if (s.rest) {
    $('#selInfo').textContent = `${measure}小節目 ${hand} 休符`;
    $('#btnToggleRest').textContent = '音符にする';
    $('#durSel').value = String(Math.min(4, snapDur(s.len)));
    return;
  }
  const i = findNote(s);
  const n = i >= 0 ? ED.work[s.hand][i] : null;
  $('#selInfo').textContent = `${measure}小節目 ${hand} ${pitchName(s.midi)}${n ? ' ・ ' + durName(n.d) : ''}`;
  $('#btnToggleRest').textContent = '休符にする';
  $('#btnHide').textContent = n && n.h ? '表示する' : '非表示にする';
  if (n) $('#durSel').value = String(snapDur(n.d));
}
function snapDur(d) {
  const opts = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4];
  return opts.reduce((a, b) => (Math.abs(b - d) < Math.abs(a - d) ? b : a));
}

// ---- 編集の操作 ----
async function applyEdit(fn) {
  if (!ED.sel) { toast('先に音符をクリックして選んでください'); return; }
  const before = clone(ED.work);
  const ok = fn();
  if (ok === false) return;
  ED.undo.push(before);
  if (ED.undo.length > 100) ED.undo.shift();
  ED.dirty = true;
  await refreshPreview();
}

async function refreshPreview() {
  $('#sheetLoading').classList.remove('hidden');
  try {
    const xml = await api(`/api/scores/${ED.id}/preview`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ED.work),
    });
    const top = $('#sheetWrap').scrollTop;
    await renderXml(xml);
    $('#sheetWrap').scrollTop = top;
    updateSelInfo();
  } catch (e) {
    toast('表示を更新できませんでした: ' + e.message);
  } finally {
    $('#sheetLoading').classList.add('hidden');
  }
}

function overwriteAfter(arr, n) {
  // 伸ばした音と重なる、後ろの音を消す(上書き)
  const end = n.o + n.d - 1e-6;
  for (let i = arr.length - 1; i >= 0; i--) {
    const x = arr[i];
    if (x !== n && x.o > n.o + 1e-6 && x.o < end) arr.splice(i, 1);
  }
}

function editAction(act) {
  applyEdit(() => {
    const s = ED.sel;
    const arr = ED.work[s.hand];
    if (s.rest) {
      if (act === 'toggleRest') {
        const prev = [...arr].reverse().find((n) => n.o < s.beat);
        const p = prev ? prev.p[prev.p.length - 1] : (s.hand === 'rh' ? 72 : 48);
        const d = Number($('#durSel').value) || snapDur(s.len);
        const n = { o: s.beat, d, p: [p] };
        arr.push(n); arr.sort((a, b) => a.o - b.o);
        overwriteAfter(arr, n);
        ED.sel = { hand: s.hand, beat: s.beat, midi: p, rest: false, len: d };
        return true;
      }
      toast('休符には「音符にする」だけ使えます');
      return false;
    }
    const i = findNote(s);
    if (i < 0) { toast('この音を見つけられませんでした'); return false; }
    const n = arr[i];
    const j = n.p.indexOf(s.midi);
    const setPitch = (np) => {
      np = Math.max(21, Math.min(108, np));
      if (j >= 0) n.p[j] = np; else n.p.push(np);
      n.p = [...new Set(n.p)].sort((a, b) => a - b);
      s.midi = np;
    };
    switch (act) {
      case 'up': setPitch(s.midi + 1); break;
      case 'down': setPitch(s.midi - 1); break;
      case 'octUp': setPitch(s.midi + 12); break;
      case 'octDown': setPitch(s.midi - 12); break;
      case 'addTone': {
        const np = s.midi + ((ED.work.meta.mode === 'minor') ? 3 : 4);
        n.p = [...new Set([...n.p, np])].sort((a, b) => a - b);
        s.midi = np; break;
      }
      case 'hide': n.h = n.h ? 0 : 1; break;
      case 'toggleRest':
      case 'delete':
        n.p = n.p.filter((p) => p !== s.midi);
        if (!n.p.length) arr.splice(i, 1);
        ED.sel = { hand: s.hand, beat: s.beat, midi: null, rest: true, len: n.d };
        break;
      default: return false;
    }
    return true;
  });
}

$$('#editBar [data-act]').forEach((b) => b.addEventListener('click', () => editAction(b.dataset.act)));
$('#durSel').addEventListener('change', () => {
  if (!ED.sel || ED.sel.rest) return;
  applyEdit(() => {
    const arr = ED.work[ED.sel.hand];
    const i = findNote(ED.sel);
    if (i < 0) return false;
    const n = arr[i];
    n.d = Number($('#durSel').value);
    overwriteAfter(arr, n);
    return true;
  });
});
$('#btnUndo').addEventListener('click', async () => {
  if (!ED.undo.length) { toast('これ以上戻せません'); return; }
  ED.work = ED.undo.pop();
  ED.dirty = ED.undo.length > 0;
  await refreshPreview();
});
$('#btnEditSave').addEventListener('click', saveEdits);
async function saveEdits() {
  try {
    await api(`/api/scores/${ED.id}/model`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(ED.work),
    });
    ED.model = clone(ED.work); ED.undo = []; ED.dirty = false;
    toast('保存しました');
    loadList();
  } catch (e) { toast('保存できませんでした: ' + e.message); }
}
$('#btnEditCancel').addEventListener('click', async () => {
  if (!ED.dirty) { setMode('play'); return; }
  if (!(await confirmBox('編集を取り消しますか?', '保存していない変更は消えます。', '取り消す'))) return;
  ED.work = clone(ED.model); ED.undo = []; ED.dirty = false; ED.sel = null;
  await refreshPreview();
  setMode('play');
});

function setMode(mode) {
  if (mode === 'edit') stopPlayback();
  ED.mode = mode;
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === mode));
  $('#playBar').classList.toggle('hidden', mode !== 'play');
  $('#editBar').classList.toggle('hidden', mode !== 'edit');
  $('#editor').classList.toggle('editing', mode === 'edit');
  if (mode === 'play') { ED.sel = null; highlightSel(); }
  updateSelInfo();
}
$$('.tab').forEach((t) => t.addEventListener('click', () => setMode(t.dataset.tab)));

$('#btnHome').addEventListener('click', async () => {
  if (ED.dirty && !(await confirmBox('保存していない変更があります', '保存せずに一覧へ戻りますか?', '戻る'))) return;
  stopPlayback();
  ED.dirty = false;
  showScreen('home');
  loadList();
});

$('#edTitle').addEventListener('change', async () => {
  const title = $('#edTitle').value.trim();
  if (!title) { $('#edTitle').value = ED.work.meta.title; return; }
  try {
    await api('/api/scores/' + ED.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }) });
    ED.model.meta.title = ED.work.meta.title = title;
    const xml = await api(`/api/scores/${ED.id}/musicxml?t=${Date.now()}`);
    if (!ED.dirty) await renderXml(xml);
    toast('曲名を変えました');
  } catch (e) { toast('変更できませんでした: ' + e.message); }
});

// ---- 拡大・縮小 ----
function setZoom(z) {
  ED.zoom = Math.max(0.5, Math.min(2, Math.round(z * 10) / 10));
  $('#zoomVal').textContent = Math.round(ED.zoom * 100) + '%';
  if (ED.osmd) { ED.osmd.zoom = ED.zoom; ED.osmd.render(); afterRender(); }
}
$('#zoomIn').addEventListener('click', () => setZoom(ED.zoom + 0.1));
$('#zoomOut').addEventListener('click', () => setZoom(ED.zoom - 0.1));

// ================= 再生 =================
let sampler = null;
let click = null;
let rafId = null;
let playOrigin = 0;

const SAMPLE_NOTES = ['A0', 'C1', 'D#1', 'F#1', 'A1', 'C2', 'D#2', 'F#2', 'A2', 'C3', 'D#3', 'F#3', 'A3', 'C4', 'D#4', 'F#4',
  'A4', 'C5', 'D#5', 'F#5', 'A5', 'C6', 'D#6', 'F#6', 'A6', 'C7', 'D#7', 'F#7', 'A7', 'C8'];

async function ensureSampler() {
  if (sampler) return;
  const urls = {};
  SAMPLE_NOTES.forEach((n) => { urls[n] = n.replace('#', 's') + '.mp3'; });
  sampler = new Tone.Sampler({ urls, baseUrl: 'vendor/piano/', release: 1.2 }).toDestination();
  click = new Tone.MembraneSynth({ volume: -14, envelope: { attack: 0.001, decay: 0.08, sustain: 0 } }).toDestination();
  toast('ピアノの音を読み込んでいます…', 1500);
  await Tone.loaded();
}

function buildCursor() {
  const c = ED.osmd && ED.osmd.cursor;
  ED.cursorSteps = [];
  if (!c) return;
  c.show();
  c.reset();
  let guard = 0;
  while (!c.Iterator.EndReached && guard++ < 20000) {
    ED.cursorSteps.push(c.Iterator.currentTimeStamp.RealValue * 4);
    c.next();
  }
  c.reset();
  ED.cursorIdx = 0;
  seekTo(ED.startBeat, true);
}

function moveCursorTo(idx) {
  const c = ED.osmd.cursor;
  if (idx < ED.cursorIdx) { c.reset(); ED.cursorIdx = 0; }
  while (ED.cursorIdx < idx && !c.Iterator.EndReached) { c.next(); ED.cursorIdx++; }
  if ($('#follow').checked) {
    const el = c.cursorElement;
    const wrap = $('#sheetWrap');
    if (el) {
      const r = el.getBoundingClientRect(); const w = wrap.getBoundingClientRect();
      if (r.top < w.top + 40 || r.bottom > w.bottom - 40) wrap.scrollTop += r.top - w.top - w.height * 0.3;
    }
  }
}

function stepIndexFor(beat) {
  let i = 0;
  while (i + 1 < ED.cursorSteps.length && ED.cursorSteps[i + 1] <= beat + 1e-6) i++;
  return i;
}

function seekTo(beat, quiet) {
  ED.startBeat = Math.max(0, beat);
  if (ED.osmd && ED.cursorSteps.length) moveCursorTo(stepIndexFor(ED.startBeat));
  if (!quiet && ED.mode === 'play') toast(`${Math.floor(ED.startBeat / 4) + 1}小節目から再生します`, 1200);
}

function secPerBeat() {
  return 60 / (ED.work.meta.tempo * (Number($('#speed').value) / 100));
}

async function startPlayback() {
  await Tone.start();
  await ensureSampler();
  const T = Tone.Transport;
  T.stop(); T.cancel(0);
  const spb = secPerBeat();
  const from = ED.startBeat;
  const total = ED.work.meta.measures * 4;
  const hands = [];
  if ($('#muteR').checked) hands.push(['rh', 0.75]);
  if ($('#muteL').checked) hands.push(['lh', 0.55]);
  hands.forEach(([h, vel]) => {
    ED.work[h].forEach((n) => {
      if (n.o + 1e-6 < from) return;
      const names = n.p.map((m) => Tone.Frequency(m, 'midi').toNote());
      T.schedule((time) => sampler.triggerAttackRelease(names, Math.max(n.d * spb * 0.95, 0.08), time, vel), (n.o - from) * spb);
    });
  });
  if ($('#metro').checked) {
    for (let b = Math.ceil(from - 1e-6); b < total; b++) {
      const strong = b % 4 === 0;
      T.schedule((time) => click.triggerAttackRelease(strong ? 'C3' : 'G2', '32n', time), (b - from) * spb);
    }
  }
  T.schedule(() => { setTimeout(stopPlayback, 0); }, (total - from) * spb + 1.2);
  playOrigin = from;
  T.start('+0.05');
  $('#btnPlay').innerHTML = '&#10074;&#10074;';
  clearInterval(rafId);
  rafId = setInterval(() => {
    if (T.state !== 'started') return;  // 開始直後(+0.05秒)はまだ stopped のことがある
    const beat = playOrigin + T.seconds / spb;
    const idx = stepIndexFor(beat);
    if (idx !== ED.cursorIdx) moveCursorTo(idx);
  }, 30);
}

function pausePlayback() {
  const T = Tone.Transport;
  if (T.state === 'started') {
    ED.startBeat = playOrigin + T.seconds / secPerBeat();
  }
  T.stop(); T.cancel(0);
  if (sampler) sampler.releaseAll();
  clearInterval(rafId);
  $('#btnPlay').innerHTML = '&#9654;';
}

function stopPlayback() {
  if (typeof Tone === 'undefined') return;
  pausePlayback();
  ED.startBeat = 0;
  if (ED.osmd && ED.cursorSteps.length) moveCursorTo(0);
}

$('#btnPlay').addEventListener('click', () => {
  if (Tone.Transport.state === 'started') pausePlayback(); else startPlayback();
});
$('#btnStop').addEventListener('click', stopPlayback);
$('#speed').addEventListener('input', () => {
  $('#speedVal').textContent = $('#speed').value + '%';
});
$('#speed').addEventListener('change', () => {
  if (Tone.Transport.state === 'started') { pausePlayback(); startPlayback(); }
});
['#muteR', '#muteL', '#metro'].forEach((s) => $(s).addEventListener('change', () => {
  if (Tone.Transport.state === 'started') { pausePlayback(); startPlayback(); }
}));

document.addEventListener('keydown', (e) => {
  if (!$('#editor').classList.contains('active')) return;
  if (e.target.matches('input, select, textarea')) return;
  if (!$$('.modal').every((m) => m.classList.contains('hidden'))) return;
  if (ED.mode === 'play' && e.code === 'Space') { e.preventDefault(); $('#btnPlay').click(); }
  if (ED.mode === 'edit') {
    if (e.key === 'ArrowUp') { e.preventDefault(); editAction(e.shiftKey ? 'octUp' : 'up'); }
    if (e.key === 'ArrowDown') { e.preventDefault(); editAction(e.shiftKey ? 'octDown' : 'down'); }
    if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); editAction('delete'); }
    if (e.ctrlKey && e.key.toLowerCase() === 'z') { e.preventDefault(); $('#btnUndo').click(); }
    if (e.ctrlKey && e.key.toLowerCase() === 's') { e.preventDefault(); saveEdits(); }
  }
});

// ================= 作り直す =================
$('#btnRecreate').addEventListener('click', () => {
  const m = ED.work.meta; const d = $('#dlgRecreate');
  segSet(d, 'level', m.level); segSet(d, 'key_mode', m.key_mode); segSet(d, 'length', m.length); segSet(d, 'style', m.style);
  openModal('#dlgRecreate');
});
$('#btnRecreateGo').addEventListener('click', async () => {
  const d = $('#dlgRecreate');
  const body = { level: Number(segValue(d, 'level')), key_mode: segValue(d, 'key_mode'), length: segValue(d, 'length'), style: segValue(d, 'style') };
  closeModal('#dlgRecreate');
  stopPlayback();
  $('#sheetLoading').classList.remove('hidden');
  try {
    await api(`/api/scores/${ED.id}/recreate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    toast('作り直しました');
    loadList();
    await openEditor(ED.id);
  } catch (e) { toast('作り直せませんでした: ' + e.message); $('#sheetLoading').classList.add('hidden'); }
});

// ================= 書き出す =================
$('#btnExport').addEventListener('click', () => {
  if (ED.dirty) toast('保存していない変更は書き出しに入りません。先に「保存」してください。', 4000);
  openModal('#dlgExport');
});
$$('.export-item').forEach((b) => b.addEventListener('click', async () => {
  closeModal('#dlgExport');
  const fmt = b.dataset.fmt;
  if (fmt === 'xml') return download(`/api/scores/${ED.id}/musicxml?download=1`);
  if (fmt === 'midi') return download(`/api/scores/${ED.id}/midi`);
  if (fmt === 'band') { toast('バンド音源を作っています…(数秒)', 4000); return download(`/api/scores/${ED.id}/band`); }
  if (fmt === 'pdf') return exportPdf();
}));
function download(url) {
  const a = document.createElement('a');
  a.href = url; a.download = ''; document.body.appendChild(a); a.click(); a.remove();
  toast('ダウンロードフォルダに保存しました');
}

async function exportPdf() {
  toast('PDFを作っています…', 8000);
  const stage = $('#pdfStage');
  stage.innerHTML = '';
  try {
    const xml = await api(`/api/scores/${ED.id}/musicxml?t=${Date.now()}`);
    const o = new opensheetmusicdisplay.OpenSheetMusicDisplay(stage, {
      autoResize: false, backend: 'svg', pageFormat: 'A4_P', pageBackgroundColor: '#FFFFFF',
      drawTitle: true, drawComposer: true, drawPartNames: false,
    });
    await o.load(xml);
    o.render();
    const svgs = $$('svg', stage);
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' });
    for (let i = 0; i < svgs.length; i++) {
      const canvas = await svgToCanvas(svgs[i], 2.5);
      if (i > 0) doc.addPage();
      doc.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', 0, 0, 210, 297);
    }
    doc.save(`${ED.work.meta.title || 'score'}.pdf`);
    toast(`PDF(${svgs.length}ページ)をダウンロードフォルダに保存しました`, 4000);
  } catch (e) {
    toast('PDFを作れませんでした: ' + e.message, 5000);
  } finally {
    stage.innerHTML = '';
  }
}

function svgToCanvas(svg, scale) {
  return new Promise((resolve, reject) => {
    const w = parseFloat(svg.getAttribute('width')) || svg.clientWidth;
    const h = parseFloat(svg.getAttribute('height')) || svg.clientHeight;
    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const data = new XMLSerializer().serializeToString(clone);
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = Math.round(w * scale); c.height = Math.round(h * scale);
      const g = c.getContext('2d');
      g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
      g.drawImage(img, 0, 0, c.width, c.height);
      resolve(c);
    };
    img.onerror = () => reject(new Error('SVGの変換に失敗'));
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(data);
  });
}

// ---------------- 起動 ----------------
loadList();
