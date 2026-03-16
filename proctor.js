// proctor.js — All frontend logic for AI Proctor

// ── Globals ─────────────────────────────────────────────────────────────
let screenStream   = null;   // screen share MediaStream
let mediaRecorder  = null;   // screen recording MediaRecorder
let recordedChunks = [];     // accumulated WebM chunks
let pollTimer      = null;   // interval: polls /api/status every 500ms
let clockTimer     = null;   // interval: updates duration display every 1s
let sessionStart   = null;   // timestamp when session began (ms)
let exitInProgress = false;  // true while exit sequence is running
let sessionActive  = false;  // master flag — ALL violations check this first
let initialWindowW = 0;      // baseline window width captured at session start
let initialWindowH = 0;      // baseline window height captured at session start

// ════════════════════════════════════════════════════════════════════════
//  PAGE 1: Screen Share
// ════════════════════════════════════════════════════════════════════════
async function requestScreenShare() {
  const btn    = document.getElementById('btn-share');
  const status = document.getElementById('share-status');
  btn.disabled = true;
  btn.textContent = 'Waiting for permission…';

  try {
    screenStream = await navigator.mediaDevices.getDisplayMedia({
      video: { cursor: 'always' },
      audio: false
    });

    const track = screenStream.getVideoTracks()[0];
    status.style.display    = 'block';
    status.style.background = '#e6f4ea';
    status.style.border     = '1px solid #a8d5b5';
    status.style.color      = '#1a6b30';
    status.textContent      = '✓ Screen sharing active. Proceed to read the exam rules.';
    btn.textContent         = '✓ Screen Shared';
    btn.style.background    = '#2d7a2d';

    track.addEventListener('ended', () => {
      if (!exitInProgress) {
        alert('Screen sharing was stopped. You must share your screen to continue the exam.');
        location.reload();
      }
    });

    setTimeout(() => {
      document.getElementById('screenshare-page').style.display = 'none';
      document.getElementById('instructions-page').style.display = 'flex';
    }, 800);

  } catch (err) {
    status.style.display    = 'block';
    status.style.background = '#fdecea';
    status.style.border     = '1px solid #f5c2be';
    status.style.color      = '#b00020';
    status.textContent      = '✗ Screen sharing was denied or cancelled. You must share your screen to proceed.';
    btn.disabled    = false;
    btn.textContent = '🖥️  Try Again';
  }
}

// ════════════════════════════════════════════════════════════════════════
//  PAGE 2: Instructions
// ════════════════════════════════════════════════════════════════════════
function toggleConfirm() {
  document.getElementById('btn-confirm').disabled =
    !document.getElementById('consent-check').checked;
}

function goToProctor() {
  document.getElementById('instructions-page').style.display = 'none';
  document.getElementById('proctor-page').style.display      = 'block';
  const tryFS = document.documentElement.requestFullscreen
                ? document.documentElement.requestFullscreen()
                : Promise.resolve();
  tryFS.catch(() => {}).finally(() => {
    setTimeout(() => {
      initialWindowW = window.innerWidth;
      initialWindowH = window.innerHeight;
      checkWindowSize();
    }, 300);
  });
}

// ════════════════════════════════════════════════════════════════════════
//  SCREEN RECORDING
// ════════════════════════════════════════════════════════════════════════
function startScreenRecording() {
  if (!screenStream) return;
  recordedChunks = [];
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
               ? 'video/webm;codecs=vp9' : 'video/webm';
  try {
    mediaRecorder = new MediaRecorder(screenStream, {
      mimeType:           mime,
      videoBitsPerSecond: 100_000,
    });
    mediaRecorder.ondataavailable = e => { if (e.data?.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.start(5000);
  } catch (err) { console.warn('[REC] MediaRecorder failed:', err); }
}

async function stopAndSaveRecording() {
  return new Promise(resolve => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') { resolve(); return; }
    mediaRecorder.onstop = async () => {
      if (!recordedChunks.length) { resolve(); return; }
      const blob = new Blob(recordedChunks, { type: 'video/webm' });
      try {
        await fetch('/api/save_recording', {
          method: 'POST', body: blob,
          headers: { 'Content-Type': 'video/webm' }
        });
      } catch(e) { console.warn('[REC] Upload failed:', e); }
      resolve();
    };
    mediaRecorder.stop();
  });
}

// ════════════════════════════════════════════════════════════════════════
//  SESSION CONTROL
// ════════════════════════════════════════════════════════════════════════
function startSession() {
  resetStats();
  fetch('/api/start', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      if (!d.ok) { alert(d.msg); return; }
      const feed = document.getElementById('feed');
      feed.src = '/video_feed';
      feed.style.display = 'block';
      document.getElementById('cam-placeholder').style.display = 'none';
      document.getElementById('btn-start').disabled = true;
      document.getElementById('btn-stop').disabled  = false;
      document.getElementById('btn-exit').style.display = 'inline-block';
      sessionStart  = Date.now();
      sessionActive = true;
      pollTimer  = setInterval(pollStatus, 500);
      clockTimer = setInterval(tickClock,  1000);
      startScreenRecording();
      checkWindowSize();
      setStatus('Monitoring', 'ok');
    });
}

function stopSession() {
  sessionActive  = false;
  exitInProgress = true;
  if (resizeBlocked) { resizeBlocked = false; hideResizeBlock(); }
  clearTimeout(resizeDebounceTimer);
  clearInterval(pollTimer);
  clearInterval(clockTimer);
  document.getElementById('btn-stop').disabled = true;
  fetch('/api/stop', { method: 'POST' })
    .then(() => setTimeout(showEndedScreen, 600));
}

function showEndedScreen() {
  sessionActive  = false;
  exitInProgress = true;
  if (screenStream) {
    screenStream.getTracks().forEach(t => t.stop());
    screenStream = null;
  }
  document.body.style.transition = 'opacity 0.5s ease';
  document.body.style.opacity    = '0';
  setTimeout(() => window.close(), 520);
}

// ── Exit dialog ──────────────────────────────────────────────────────────
function showExitDialog()  { document.getElementById('exit-overlay').classList.add('show');    }
function closeExitDialog() { document.getElementById('exit-overlay').classList.remove('show'); }

async function confirmExit() {
  sessionActive  = false;
  exitInProgress = true;
  if (resizeBlocked) { resizeBlocked = false; hideResizeBlock(); }
  clearTimeout(resizeDebounceTimer);
  clearInterval(pollTimer);
  clearInterval(clockTimer);

  document.getElementById('exit-confirm-btn').textContent = 'Ending…';
  document.getElementById('exit-confirm-btn').disabled    = true;
  document.getElementById('exit-cancel-btn').disabled     = true;

  document.getElementById('exit-overlay').classList.remove('show');
  await new Promise(r => setTimeout(r, 60));
  document.body.classList.add('closing');
  await new Promise(r => setTimeout(r, 480));

  try { await fetch('/api/stop', { method: 'POST' }); } catch(e) {}
  await stopAndSaveRecording();
  try { if (document.fullscreenElement) await document.exitFullscreen(); } catch(e) {}

  showEndedScreen();
}

// ════════════════════════════════════════════════════════════════════════
//  STATUS POLLING & CLOCK
// ════════════════════════════════════════════════════════════════════════
function pollStatus() {
  fetch('/api/status').then(r => r.json()).then(d => {
    if (!d.running && d.verdict) {
      clearInterval(pollTimer);
      clearInterval(clockTimer);
      showEndedScreen(); return;
    }
    setStatus(d.no_face_raw ? 'NO FACE' : 'Monitoring', d.no_face_raw ? 'alert' : 'ok');

    const fe = document.getElementById('s-face');
    const pe = document.getElementById('s-phone');
    const te = document.getElementById('s-tabswitch');
    const ce = document.getElementById('s-copypaste');

    if (d.running && d.face_out_count > (parseInt(fe.textContent)||0)) showToast('face');
    if (d.running && d.phone_count    > (parseInt(pe.textContent)||0)) showToast('phone');
    fe.textContent = d.face_out_count;
    pe.textContent = d.phone_count;
    te.textContent = d.tab_switch_count  || 0;
    ce.textContent = d.copy_paste_count  || 0;

    fe.className = 'stat-value' + (d.face_out_count        ? ' alert' : ' ok');
    pe.className = 'stat-value' + (d.phone_count           ? ' alert' : ' ok');
    te.className = 'stat-value' + ((d.tab_switch_count||0) ? ' alert' : ' ok');
    ce.className = 'stat-value' + ((d.copy_paste_count||0) ? ' alert' : ' ok');

    const row = document.getElementById('absent-row');
    if (d.no_face_raw) {
      row.style.display = 'block';
      document.getElementById('s-absent').textContent  = d.absent_secs + 's';
      document.getElementById('absent-bar').style.width = Math.min(d.absent_secs/2*100,100) + '%';
    } else {
      row.style.display = 'none';
      document.getElementById('absent-bar').style.width = '0%';
    }
  });
}

function tickClock() {
  if (!sessionStart) return;
  const s  = Math.floor((Date.now() - sessionStart) / 1000);
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  document.getElementById('s-duration').textContent = mm + ':' + ss;
}

function resetStats() {
  ['s-face','s-phone','s-tabswitch','s-copypaste'].forEach(id => {
    document.getElementById(id).textContent = '0';
    document.getElementById(id).className   = 'stat-value';
  });
  document.getElementById('s-duration').textContent = '—';
}

function setStatus(text, cls) {
  const el = document.getElementById('s-status');
  el.textContent = text;
  el.className   = 'stat-value' + (cls ? ' ' + cls : '');
}

// ════════════════════════════════════════════════════════════════════════
//  TAB SWITCH DETECTION
// ════════════════════════════════════════════════════════════════════════
let tabCooldown = false;

function recordTabSwitch() {
  if (!sessionActive || tabCooldown) return;
  tabCooldown = true;
  setTimeout(() => { tabCooldown = false; }, 1500);
  fetch('/api/violation/tab_switch', { method: 'POST' });
  flashViolation('s-tabswitch');
  showToast('tab');
}

document.addEventListener('visibilitychange', () => { if (document.hidden) recordTabSwitch(); });
window.addEventListener('blur', () => {
  setTimeout(() => { if (!document.hasFocus()) recordTabSwitch(); }, 500);
});

// ════════════════════════════════════════════════════════════════════════
//  TOAST BANNERS
// ════════════════════════════════════════════════════════════════════════
function showToast(type) {
  if (!sessionActive) return;
  const el = document.getElementById('toast-' + type);
  if (!el) return;
  el.classList.remove('toast-show');
  const old = el.querySelector('.toast-bar');
  if (old) old.remove();
  const bar = document.createElement('span');
  bar.className = 'toast-bar';
  el.appendChild(bar);
  void el.offsetWidth;   // force reflow
  el.classList.add('toast-show');
  setTimeout(() => el.classList.remove('toast-show'), 3300);
}

// ════════════════════════════════════════════════════════════════════════
//  WINDOW SIZE ENFORCEMENT (fullscreen guard)
// ════════════════════════════════════════════════════════════════════════
let resizeBlocked        = false;
let resizeViolationFired = false;
let resizeDebounceTimer  = null;

function showResizeBlock() {
  const el = document.getElementById('resize-block-overlay');
  el.classList.add('show');
  requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('visible')));
}

function hideResizeBlock() {
  const el = document.getElementById('resize-block-overlay');
  el.classList.remove('visible');
  setTimeout(() => { if (!resizeBlocked) el.classList.remove('show'); }, 380);
}

function goFullscreenFromOverlay() {
  const req = document.documentElement.requestFullscreen
           || document.documentElement.webkitRequestFullscreen;
  if (req) req.call(document.documentElement).catch(() => {});
  setTimeout(() => {
    initialWindowW = window.innerWidth;
    initialWindowH = window.innerHeight;
    _doCheckWindowSize();
  }, 400);
}

function _doCheckWindowSize() {
  if (!sessionActive) {
    if (resizeBlocked) { resizeBlocked = false; hideResizeBlock(); }
    return;
  }
  const refW     = Math.max(initialWindowW, screen.availWidth  * 0.95);
  const refH     = Math.max(initialWindowH, screen.availHeight * 0.95);
  const tooSmall = window.innerWidth < refW * 0.88 || window.innerHeight < refH * 0.88;
  if (tooSmall && !resizeBlocked) {
    resizeBlocked = true;
    showResizeBlock();
    if (!resizeViolationFired) {
      resizeViolationFired = true;
      fetch('/api/violation/tab_switch', { method: 'POST' });
      flashViolation('s-tabswitch');
      showToast('tab');
    }
  } else if (!tooSmall && resizeBlocked) {
    resizeBlocked        = false;
    resizeViolationFired = false;
    hideResizeBlock();
  }
}

function checkWindowSize() {
  clearTimeout(resizeDebounceTimer);
  resizeDebounceTimer = setTimeout(_doCheckWindowSize, 600);
}

window.addEventListener('resize', checkWindowSize);
window.addEventListener('load', () => {
  initialWindowW = window.innerWidth;
  initialWindowH = window.innerHeight;
});

// ════════════════════════════════════════════════════════════════════════
//  COPY / PASTE BLOCKING
// ════════════════════════════════════════════════════════════════════════
function recordCopyPaste(e) {
  if (!sessionActive) return;
  e.preventDefault();
  fetch('/api/violation/copy_paste', { method: 'POST' });
  flashViolation('s-copypaste');
  showToast('copy');
}

document.addEventListener('copy',  recordCopyPaste);
document.addEventListener('cut',   recordCopyPaste);
document.addEventListener('paste', recordCopyPaste);

// ── Keyboard shortcut blocking ────────────────────────────────────────
document.addEventListener('keydown', function(e) {
  if (!sessionActive) return;
  const key     = e.key.toLowerCase();
  const blocked = (e.ctrlKey || e.metaKey) && ['c','v','x','s','u','a'].includes(key)
                  || e.key === 'PrintScreen' || e.key === 'F12';
  if (!blocked) return;
  e.preventDefault();
  if (['c','v','x'].includes(key)) {
    fetch('/api/violation/copy_paste', { method: 'POST' });
    flashViolation('s-copypaste');
    showToast('copy');
  }
});

// ── Right-click block ────────────────────────────────────────────────
document.addEventListener('contextmenu', e => { if (sessionActive) e.preventDefault(); });

// ════════════════════════════════════════════════════════════════════════
//  VIOLATION FLASH BADGE
// ════════════════════════════════════════════════════════════════════════
function flashViolation(statId) {
  const el = document.getElementById(statId);
  if (!el) return;
  const badge = document.createElement('span');
  badge.className   = 'vio-flash';
  badge.textContent = '+1';
  el.parentNode.appendChild(badge);
  setTimeout(() => badge.remove(), 2100);
}