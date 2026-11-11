import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { ScreenProps } from '../../shell/types'
import { Icon } from '../../kit'
import { useI18n } from '../../i18n'
import { useAssistantContext } from '../../lib/assistantContext'
import { DOC_PAGES, docHash, loadPage, openDoc, parseDocHash, renderMarkdown, type LoadedDoc } from '../../lib/docs'
import './docs.css'

// repli de lettre : « é » -> « e », sans changer la longueur du texte (la position d'une occurrence reste valable)
const fold = (s: string) => Array.from(s, c => (c.normalize('NFD')[0] ?? c).toLowerCase()).join('')

/** Surligne les occurrences de `q` dans `root` (texte hors blocs de code colorés compris) et renvoie les éléments <mark>. */
function markHits(root: HTMLElement, q: string): HTMLElement[] {
  const needle = fold(q.trim()); if (needle.length < 2) return []
  const nodes: Text[] = []
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  for (let n = w.nextNode(); n; n = w.nextNode()) if (!(n.parentElement?.closest('.doc-h-link'))) nodes.push(n as Text)
  const marks: HTMLElement[] = []
  for (const node of nodes) {
    const txt = node.nodeValue ?? '', f = fold(txt)
    let i = f.indexOf(needle); if (i < 0) continue
    const frag = document.createDocumentFragment(); let last = 0
    for (; i >= 0; i = f.indexOf(needle, last)) {
      frag.append(txt.slice(last, i))
      const m = document.createElement('mark'); m.className = 'doc-hit'; m.textContent = txt.slice(i, i + needle.length); frag.append(m); marks.push(m)
      last = i + needle.length
    }
    frag.append(txt.slice(last)); node.replaceWith(frag)
  }
  return marks
}

export function Documentation({ p }: ScreenProps) {
  const { t, lang } = useI18n()
  useAssistantContext({ screen: 'documentation', projectId: p.id })
  const [route, setRoute] = useState(parseDocHash())
  const [doc, setDoc] = useState<LoadedDoc | null | undefined>(undefined)  // undefined = chargement, null = page absente
  const [q, setQ] = useState('')
  const [cur, setCur] = useState(0)
  const [hits, setHits] = useState(0)
  const [tocOpen, setTocOpen] = useState(false)
  const [active, setActive] = useState('')
  const [zoom, setZoom] = useState<{ src: string; alt: string; cap: string } | null>(null)  // visionneuse d'une capture
  const [actual, setActual] = useState(false)  // taille réelle (défilable) ou image ajustée
  const opener = useRef<HTMLElement | null>(null)
  const closeBtn = useRef<HTMLButtonElement>(null)
  const article = useRef<HTMLElement>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const marks = useRef<HTMLElement[]>([])

  useEffect(() => { const f = () => { setRoute(parseDocHash()); setTocOpen(false) }; addEventListener('hashchange', f); return () => removeEventListener('hashchange', f) }, [])
  useEffect(() => { let off = false; setDoc(undefined); loadPage(route.page, lang).then(d => { if (!off) setDoc(d) }).catch(() => { if (!off) setDoc(null) }); return () => { off = true } }, [route.page, lang])

  const rendered = useMemo(() => (doc ? renderMarkdown(doc.md, p.id, route.page, doc.shown) : null), [doc, p.id, route.page])

  const scrollToAnchor = useCallback((id: string | null) => {
    const sc = scroller.current; if (!sc) return
    const el = id ? article.current?.querySelector<HTMLElement>(`[id="${CSS.escape(id)}"]`) : null
    if (el) { sc.scrollTo({ top: el.offsetTop - 8 }); setActive(id!) } else sc.scrollTo({ top: 0 })
  }, [])

  // (re)pose du HTML, des surlignages de recherche, puis de la position dans la page
  useLayoutEffect(() => {
    const el = article.current; if (!el) return
    el.innerHTML = rendered?.html ?? ''
    marks.current = q.trim().length >= 2 ? markHits(el, q) : []
    setHits(marks.current.length); setCur(0)
    if (marks.current.length) { marks.current[0].classList.add('cur'); marks.current[0].scrollIntoView({ block: 'center' }) } else scrollToAnchor(route.anchor)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rendered, q])
  useEffect(() => { if (!(marks.current.length)) scrollToAnchor(route.anchor) }, [route.anchor, rendered, scrollToAnchor])
  useEffect(() => {
    marks.current.forEach((m, i) => m.classList.toggle('cur', i === cur))
    marks.current[cur]?.scrollIntoView({ block: 'center' })
  }, [cur, hits])

  // lecture : élément du sommaire correspondant à la position
  useEffect(() => {
    const sc = scroller.current; if (!sc || !rendered) return
    let raf = 0
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => {
      let id = ''
      for (const h of rendered.toc) { const el = article.current?.querySelector<HTMLElement>(`[id="${CSS.escape(h.id)}"]`); if (el && el.offsetTop - 24 <= sc.scrollTop) id = h.id; else if (el) break }
      setActive(id)
    }) }
    sc.addEventListener('scroll', on, { passive: true }); return () => { sc.removeEventListener('scroll', on); cancelAnimationFrame(raf) }
  }, [rendered])

  const openZoom = (img: HTMLImageElement) => { opener.current = img; setActual(false); setZoom({ src: img.currentSrc || img.src, alt: img.alt, cap: img.dataset.docZoom || img.alt }) }
  const closeZoom = useCallback(() => { setZoom(null); opener.current?.focus({ preventScroll: true }) }, [])
  // visionneuse : Échap ferme (avant la recherche), le focus va sur le bouton Fermer puis revient sur l'image
  useEffect(() => {
    if (!zoom) return
    closeBtn.current?.focus()
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeZoom() } }
    window.addEventListener('keydown', k, true); return () => window.removeEventListener('keydown', k, true)
  }, [zoom, closeZoom])
  const onArticleKey = (e: React.KeyboardEvent) => {
    const img = (e.target as HTMLElement).closest<HTMLImageElement>('img.doc-img')
    if (img && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openZoom(img) }
  }
  const onArticleClick = (e: React.MouseEvent) => {
    const img = (e.target as HTMLElement).closest<HTMLImageElement>('img.doc-img'); if (img) { openZoom(img); return }
    const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a[data-doc-page]'); if (!a || e.metaKey || e.ctrlKey) return
    e.preventDefault()
    const pg = a.dataset.docPage!, an = a.dataset.docAnchor || null
    if (pg === route.page) { history.replaceState(null, '', docHash(p.id, pg, an)); setRoute({ page: pg, anchor: an }); scrollToAnchor(an) } else openDoc(p.id, pg, an)
  }
  const step = (d: number) => { if (hits) setCur(c => (c + d + hits) % hits) }
  const title = rendered?.toc.find(x => x.level === 1)?.text
  const fr = !!doc?.fallback

  const side = (
    <nav className={'doc-side' + (tocOpen ? ' open' : '')} aria-label={t('docs.toc')} id="doc-side" data-doc-fallback={fr || undefined}>
      <div className="doc-pages" role="group" aria-label={t('docs.pages')}>
        {DOC_PAGES.map(id => <a key={id} href={docHash(p.id, id)} aria-current={id === route.page ? 'page' : undefined}>{t('docs.page.' + id) === 'docs.page.' + id ? id : t('docs.page.' + id)}</a>)}
      </div>
      <div className="doc-toc-title">{t('docs.toc')}</div>
      <ul className="doc-toc">
        {rendered?.toc.filter(x => x.level > 1).map(x => (
          <li key={x.id} className={'l' + x.level}><a href={docHash(p.id, route.page, x.id)} aria-current={active === x.id ? 'location' : undefined}
            onClick={e => { e.preventDefault(); history.replaceState(null, '', docHash(p.id, route.page, x.id)); setRoute({ page: route.page, anchor: x.id }); setTocOpen(false); scrollToAnchor(x.id) }}>{x.text}</a></li>))}
      </ul>
    </nav>)

  return (
    <div className="doc" data-tour="docs">
      <div className="doc-bar" data-tour="docs-bar">
        <button type="button" className="btn sm doc-toc-btn" aria-expanded={tocOpen} aria-controls="doc-side" onClick={() => setTocOpen(o => !o)}><Icon name="list-ul" />{t('docs.toc')}</button>
        <span className="doc-title" data-doc-fallback={fr || undefined}>{title ?? ''}</span>
        <span className="grow" />
        <div className="doc-search" role="search">
          <Icon name="magnifying-glass" />
          <input type="search" value={q} onChange={e => setQ(e.target.value)} placeholder={t('docs.search')} aria-label={t('docs.search')} data-testid="doc-search"
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); step(e.shiftKey ? -1 : 1) } else if (e.key === 'Escape') setQ('') }} />
          {q.trim().length >= 2 && <span className="doc-count" aria-live="polite" data-testid="doc-count">{hits ? t('docs.count', { n: cur + 1, total: hits }) : t('docs.noHit')}</span>}
          <button type="button" className="btn ghost iconly sm" aria-label={t('docs.prev')} title={t('docs.prev')} disabled={!hits} onClick={() => step(-1)}><Icon name="chevron-up" /></button>
          <button type="button" className="btn ghost iconly sm" aria-label={t('docs.next')} title={t('docs.next')} disabled={!hits} onClick={() => step(1)}><Icon name="chevron-down" /></button>
        </div>
      </div>
      {fr && <div className="notice soon doc-banner" role="note" data-testid="doc-fr-only"><Icon name="language" /><span>{t('docs.frOnly')}</span></div>}
      <div className="doc-body">
        {side}
        <div className="doc-scroll" ref={scroller} data-doc-fallback={fr || undefined}>
          {doc === undefined && <p className="muted doc-msg">…</p>}
          {doc === null && <p className="doc-msg" role="alert">{t('docs.notFound')}</p>}
          <article ref={article} className="doc-article" lang={doc?.shown} onClick={onArticleClick} onKeyDown={onArticleKey} data-testid="doc-article" />
        </div>
      </div>
      {zoom && (
        <div className="doc-zoom" role="dialog" aria-modal="true" aria-label={zoom.alt || t('docs.zoom.label')} data-testid="doc-zoom" onClick={e => { if (e.target === e.currentTarget) closeZoom() }}>
          <button type="button" className="btn iconly doc-zoom-x" ref={closeBtn} aria-label={t('docs.zoom.close')} title={t('docs.zoom.close')} onClick={closeZoom} data-testid="doc-zoom-close"><Icon name="xmark" /></button>
          <div className={'doc-zoom-scroll' + (actual ? ' actual' : '')} onClick={e => { if (e.target === e.currentTarget) closeZoom() }}>
            <img src={zoom.src} alt={zoom.alt} onClick={() => setActual(a => !a)} data-testid="doc-zoom-img" />
          </div>
          <p className="doc-zoom-cap">{zoom.cap} <span className="muted">· {t('docs.zoom.hint')}</span></p>
        </div>)}
    </div>)
}
