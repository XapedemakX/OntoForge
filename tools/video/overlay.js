// Injecté dans chaque page filmée : faux curseur (Playwright n'en dessine pas), onde au clic, bandeau de sous-titre et chapitre.
(() => {
  if (window.__vid) return
  const css = `
  #vid-cursor { position: fixed; left: 0; top: 0; width: 22px; height: 22px; z-index: 2147483647; pointer-events: none; transform: translate(-3px,-2px); transition: opacity .2s; }
  #vid-cursor svg { filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); }
  .vid-ripple { position: fixed; width: 44px; height: 44px; margin: -22px 0 0 -22px; border-radius: 50%; border: 3px solid #2fc0b0; z-index: 2147483646; pointer-events: none; animation: vidr .55s ease-out forwards; }
  @keyframes vidr { from { transform: scale(.3); opacity: .95 } to { transform: scale(1.5); opacity: 0 } }
  #vid-cap { position: fixed; left: 50%; bottom: 34px; transform: translate(-50%, 16px); max-width: 74%; z-index: 2147483645; pointer-events: none; opacity: 0; transition: opacity .35s, transform .35s;
    background: rgba(8,22,31,.92); color: #eef7f7; font: 500 20px/1.4 'IBM Plex Sans', system-ui, sans-serif; padding: 12px 22px 13px; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.28); border: 1px solid rgba(95,211,198,.35); text-align: center; }
  #vid-cap.on { opacity: 1; transform: translate(-50%, 0); }
  #vid-cap b { color: #5fd3c6; font-weight: 600; }
  #vid-chap { position: fixed; left: 50%; transform: translateX(-50%); bottom: 128px; z-index: 2147483645; pointer-events: none; opacity: 0; transition: opacity .35s; background: #0f766e; color: #fff; font: 600 13px/1 'IBM Plex Sans', system-ui, sans-serif; letter-spacing: .12em; text-transform: uppercase; padding: 8px 12px; border-radius: 999px; }
  #vid-chap.on { opacity: .95; }`
  const add = () => {
    if (document.getElementById('vid-cursor')) return
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st)
    const c = document.createElement('div'); c.id = 'vid-cursor'
    c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.6L21 10.8z" fill="#fff" stroke="#0b2230" stroke-width="1.6" stroke-linejoin="round"/></svg>'
    document.body.appendChild(c)
    const cap = document.createElement('div'); cap.id = 'vid-cap'; document.body.appendChild(cap)
    const ch = document.createElement('div'); ch.id = 'vid-chap'; document.body.appendChild(ch)
    const pos = window.__vidPos || { x: -40, y: -40 }; c.style.left = pos.x + 'px'; c.style.top = pos.y + 'px'
  }
  window.__vid = {
    caption(html) { add(); const el = document.getElementById('vid-cap'); if (!html) { el.classList.remove('on'); return } el.innerHTML = html; el.classList.add('on') },
    chapter(t) { add(); const el = document.getElementById('vid-chap'); if (!t) { el.classList.remove('on'); return } el.textContent = t; el.classList.add('on'); clearTimeout(window.__vidChapT); window.__vidChapT = setTimeout(() => el.classList.remove('on'), 3200) },
  }
  document.addEventListener('mousemove', e => { add(); window.__vidPos = { x: e.clientX, y: e.clientY }; const c = document.getElementById('vid-cursor'); c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px' }, true)
  document.addEventListener('mousedown', e => { const r = document.createElement('div'); r.className = 'vid-ripple'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.body.appendChild(r); setTimeout(() => r.remove(), 600) }, true)
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add); else add()
})()
