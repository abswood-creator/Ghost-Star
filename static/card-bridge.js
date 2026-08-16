/**
 * Ghost Hunter — Mini App bridge for the original animated cards.
 * Injected into each static card page. Syncs progress with the API
 * and routes the practice button through /api/practice.
 */
(function () {
  const GHOST_META = {
    sparky: {
      btn: 'zapBtn',
      fill: 'chargeFill',
      label: 'chargePct',
      labelMode: 'pct', // show remaining % like the original
    },
    'bed-crawler': {
      btn: 'playBtn',
      fill: 'distanceFill',
      label: 'distancePct',
      labelMode: 'pct',
    },
    'window-stalker': {
      btn: 'playBtn',
      fill: 'fogFill',
      label: 'fogPct',
      labelMode: 'pct',
    },
    'red-aura-wraith': {
      btn: 'playBtn',
      fill: 'auraFill',
      label: 'auraPct',
      labelMode: 'pct',
    },
    'rockstar-specter': {
      btn: 'playBtn',
      fill: 'presenceFill',
      label: 'presencePct',
      labelMode: 'pct',
    },
  };

  // Ghost id from the page: set by the server as window.__GHOST_ID__
  const ghostId = window.__GHOST_ID__;
  if (!ghostId || !GHOST_META[ghostId]) return;

  const meta = GHOST_META[ghostId];
  const tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      tg.setHeaderColor('#0b0812');
      tg.setBackgroundColor('#0b0812');
    } catch (_) {}
  }
  const initData = (tg && tg.initData) || '';

  function headers() {
    const h = { 'Content-Type': 'application/json' };
    if (initData) {
      h['X-Telegram-Init-Data'] = initData;
      h['Authorization'] = 'tma ' + initData;
    }
    return h;
  }

  async function api(path, opts) {
    const res = await fetch(path, {
      ...(opts || {}),
      headers: { ...headers(), ...((opts && opts.headers) || {}) },
    });
    if (!res.ok) {
      const body = await res.json().catch(function () { return {}; });
      throw new Error(body.detail || res.statusText || 'Request failed');
    }
    return res.json();
  }

  function setBar(progress, repsNeeded) {
    const fill = document.getElementById(meta.fill);
    const label = document.getElementById(meta.label);
    // Cards animate "remaining" charge (100% full → 0% empty)
    const remainingPct = repsNeeded
      ? Math.max(0, Math.round(((repsNeeded - progress) / repsNeeded) * 100))
      : 100;
    if (fill) fill.style.width = remainingPct + '%';
    if (label) {
      if (meta.labelMode === 'pct') label.textContent = remainingPct + '%';
      else label.textContent = progress + '/' + repsNeeded;
    }
  }

  function setFooter(st) {
    const el = document.getElementById('defeatCount');
    if (el) el.textContent = String(st.ghosts_defeated);
  }

  function showVictory(detail) {
    const victory = document.getElementById('victory');
    const detailEl = document.getElementById('victoryDetail');
    if (detailEl && detail) detailEl.textContent = detail;
    if (victory) victory.classList.add('show');
  }

  function hideVictory() {
    const victory = document.getElementById('victory');
    if (victory) victory.classList.remove('show');
  }

  let currentStatus = null;
  let busy = false;

  function applyStatus(st) {
    currentStatus = st;
    setFooter(st);

    const isCurrent = st.current_ghost && st.current_ghost.id === ghostId;
    const defeated = st.roster.some(function (g) {
      return g.id === ghostId && g.defeated;
    });
    const btn = document.getElementById(meta.btn);

    if (isCurrent) {
      hideVictory();
      const g = st.current_ghost;
      setBar(g.progress, g.reps_needed);
      if (btn) {
        btn.disabled = false;
        // keep original button label
      }
    } else if (defeated) {
      setBar(1, 1); // 0% remaining
      showVictory('Already banished.');
      if (btn) btn.disabled = true;
    } else {
      setBar(0, 1); // full bar, not yet active
      if (btn) btn.disabled = true;
    }
  }

  async function doPractice(ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
    }
    if (busy) return;
    if (!initData) {
      alert('Open this card from the Telegram bot menu to log practice.');
      return;
    }
    if (!currentStatus || !currentStatus.current_ghost || currentStatus.current_ghost.id !== ghostId) {
      return;
    }

    busy = true;
    const btn = document.getElementById(meta.btn);
    if (btn) btn.disabled = true;

    // Visual feedback — shake frame if present
    const frame = document.getElementById('frame');
    if (frame) {
      frame.classList.remove('shake');
      void frame.offsetWidth;
      frame.classList.add('shake');
    }

    try {
      const data = await api('/api/practice', { method: 'POST' });
      applyStatus(data.status);

      if (tg) {
        try {
          if (data.event && data.event.defeated_ghost) {
            tg.HapticFeedback.notificationOccurred('success');
          } else {
            tg.HapticFeedback.impactOccurred('medium');
          }
        } catch (_) {}
      }

      if (data.event && data.event.encore) {
        const flash = document.getElementById('encoreFlash');
        if (flash) {
          flash.classList.add('show');
          setTimeout(function () { flash.classList.remove('show'); }, 1200);
        }
      }

      if (data.event && data.event.defeated_ghost && data.event.defeated_ghost.id === ghostId) {
        showVictory(
          data.event.defeated_ghost.name + ' banished!'
        );
        setTimeout(function () {
          window.location.href = '/';
        }, 2000);
      } else if (btn && currentStatus && currentStatus.current_ghost && currentStatus.current_ghost.id === ghostId) {
        btn.disabled = false;
      }
    } catch (e) {
      console.error(e);
      if (btn) btn.disabled = false;
      alert(e.message || String(e));
    } finally {
      busy = false;
    }
  }

  // Wire button — replace original local-only handler
  function wireButton() {
    const btn = document.getElementById(meta.btn);
    if (!btn) return;
    // Clone to strip existing listeners from the prototype cards
    const clone = btn.cloneNode(true);
    btn.parentNode.replaceChild(clone, btn);
    clone.addEventListener('click', doPractice);
  }

  // Also disable / rewire reset so it doesn't desync local state
  function wireReset() {
    const reset = document.getElementById('resetBtn');
    if (!reset) return;
    const clone = reset.cloneNode(true);
    reset.parentNode.replaceChild(clone, reset);
    clone.addEventListener('click', function () {
      window.location.href = '/';
    });
    clone.textContent = 'Back to roster';
  }

  // Back link
  function addBackLink() {
    if (document.getElementById('gh-back')) return;
    const a = document.createElement('a');
    a.id = 'gh-back';
    a.href = '/';
    a.textContent = '← Roster';
    a.style.cssText =
      'position:fixed;top:12px;left:12px;z-index:50;font-family:JetBrains Mono,monospace;' +
      'font-size:12px;letter-spacing:.08em;color:#9b6bff;text-decoration:none;' +
      'background:rgba(11,8,18,.75);padding:6px 10px;border-radius:8px;';
    document.body.appendChild(a);
  }

  async function boot() {
    addBackLink();
    wireButton();
    wireReset();

    if (!initData) {
      // Preview outside Telegram — leave visual as-is
      return;
    }
    try {
      const st = await api('/api/status');
      applyStatus(st);
    } catch (e) {
      console.error('status load failed', e);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
