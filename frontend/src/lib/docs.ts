// Documentation embarquée (L28) : les fichiers docs/guide/*.md sont compilés avec le front (import Vite ?raw, un chunk par fichier),
// donc lisibles hors ligne et toujours à la version de l'application. Rendu Markdown avec `marked` (déjà épinglé) + coloration maison.
import { Marked, type Tokens } from 'marked'
import helpMapJson from '../../../backend/ontoforge/assistant/help_map.json'
import { highlight } from './codeHighlight'

const RAW = import.meta.glob('../../../docs/guide/*.md', { query: '?raw', import: 'default' }) as Record<string, () => Promise<string>>

export type Lang = 'fr' | 'en'
/** Ordre d'affichage ; les autres fichiers du dossier suivent par ordre alphabétique. */
const ORDER = ['utilisateur', 'deploiement', 'limites', 'contribuer', 'api', 'architecture', 'regles', 'glossaire', 'changelog']
const FILES: Record<string, Partial<Record<Lang, () => Promise<string>>>> = {}
for (const [path, load] of Object.entries(RAW)) {
  const m = /\/([^/]+?)(\.en)?\.md$/.exec(path); if (!m) continue
  const id = m[1].toLowerCase()
  ;(FILES[id] ??= {})[m[2] ? 'en' : 'fr'] = load
}
export const DOC_PAGES: string[] = Object.keys(FILES).sort((a, b) => (ORDER.indexOf(a) + 1 || 99) - (ORDER.indexOf(b) + 1 || 99) || a.localeCompare(b))
export const DEFAULT_PAGE = 'utilisateur'
export const hasPage = (id: string) => id in FILES

export interface LoadedDoc { md: string; shown: Lang; fallback: boolean }
/** Version dans la langue demandée si elle existe, sinon la version française (fallback = vrai : bandeau « French only »). */
export async function loadPage(id: string, lang: Lang): Promise<LoadedDoc | null> {
  const f = FILES[id]; if (!f) return null
  if (lang === 'en' && f.en) return { md: await f.en(), shown: 'en', fallback: false }
  const fr = f.fr ?? f.en; if (!fr) return null
  return { md: await fr(), shown: f.fr ? 'fr' : 'en', fallback: lang === 'en' && !!f.fr }
}

// ----------------------------------------------------------------------------- ancres
/** Ancre par défaut d'un titre sans `{#id}` : sans accents, sans numéro de section, minuscules, tirets. Même algorithme que backend/tests/test_help_map.py. */
export function slugify(text: string): string {
  const t = text.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[`*_]/g, '')
  const base = t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/œ/g, 'oe').replace(/æ/g, 'ae')
    .trim().replace(/^\d+(?:\.\d+)*\.?\s+/, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
  return base || 'section'
}

export const docHash = (pid: string, page = DEFAULT_PAGE, anchor?: string | null) =>
  `#/projet/${encodeURIComponent(pid)}/documentation/${page}${anchor ? '/' + encodeURIComponent(anchor) : ''}`
export function openDoc(pid: string, page = DEFAULT_PAGE, anchor?: string | null): void { location.hash = docHash(pid, page, anchor) }
export function parseDocHash(h = location.hash): { page: string; anchor: string | null } {
  const m = /^#\/projet\/[^/]+\/documentation(?:\/([\w-]+))?(?:\/([^?]+))?/.exec(h)
  let anchor: string | null = null
  try { anchor = m?.[2] ? decodeURIComponent(m[2]) : null } catch { anchor = m?.[2] ?? null }
  return { page: m?.[1] && hasPage(m[1].toLowerCase()) ? m[1].toLowerCase() : DEFAULT_PAGE, anchor }
}

// ----------------------------------------------------------------------------- correspondance écran -> section (partagée avec Krakie)
export interface HelpEntry { page: string; anchor: string; title: { fr: string; en: string }; summary: { fr: string; en: string } }
const HELP = (helpMapJson as { screens: Record<string, HelpEntry> }).screens
/** `screen` = nom du contexte assistant (dashboard, editor, shapes…) ; section générale si inconnu. */
export const helpFor = (screen: string): HelpEntry => HELP[screen] ?? HELP.default
export const HELP_SCREENS = Object.keys(HELP)

// ----------------------------------------------------------------------------- rendu
/** Identifiant explicite en fin de titre : `## Titre {#ancre}`. Les versions fr et en d'un fichier portent les mêmes. */
const EXPLICIT_ID = /\s*\{#([\w-]+)\}\s*$/
export interface TocItem { level: number; text: string; id: string }
export interface Rendered { html: string; toc: TocItem[] }
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export function renderMarkdown(md: string, pid: string, page: string, lang: Lang = 'fr'): Rendered {
  const toc: TocItem[] = []
  const seen = new Map<string, number>()
  const unique = (base: string) => { const n = seen.get(base) ?? 0; seen.set(base, n + 1); return n ? `${base}-${n + 1}` : base }
  const mk = new Marked({
    gfm: true,
    renderer: {
      heading(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, tk: Tokens.Heading) {
        // L33 : identifiant explicite `{#id}` en fin de titre (commun aux versions fr et en) ; sinon ancre dérivée du texte
        const ex = EXPLICIT_ID.exec(tk.text)
        const toks = tk.tokens as Tokens.Generic[]
        if (ex) { const last = toks[toks.length - 1]; if (last && typeof last.text === 'string') { last.text = last.text.replace(EXPLICIT_ID, ''); last.raw = last.raw.replace(EXPLICIT_ID, '') } }
        const id = unique(ex ? ex[1] : slugify(tk.text))
        const plain = (ex ? tk.text.replace(EXPLICIT_ID, '') : tk.text).replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[`*_]/g, '')
        if (tk.depth <= 3) toc.push({ level: tk.depth, text: plain, id })
        return `<h${tk.depth} id="${id}">${this.parser.parseInline(tk.tokens)}<a class="doc-h-link" href="${docHash(pid, page, id)}" data-doc-page="${page}" data-doc-anchor="${id}" aria-hidden="true" tabindex="-1">#</a></h${tk.depth}>\n`
      },
      code(tk: Tokens.Code) { return `<pre class="doc-code" data-lang="${esc(tk.lang ?? '')}"><code>${highlight(tk.text, tk.lang)}</code></pre>\n` },
      // les captures du guide vivent dans journal/ (hors de l'image et du build) : légende lisible plutôt qu'une icône d'image cassée
      image(tk: Tokens.Image) { return /^https?:\/\//i.test(tk.href) ? `<img src="${esc(tk.href)}" alt="${esc(tk.text)}" loading="lazy">` : `<span class="doc-fig" role="img" aria-label="${esc(tk.text)}">${lang === 'en' ? 'Screenshot:' : 'Capture :'} ${esc(tk.text)}</span>` },
      html(tk: Tokens.HTML | Tokens.Tag) { return esc(tk.text) },  // le HTML brut du guide est affiché tel quel, jamais interprété
      link(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, tk: Tokens.Link) {
        const inner = this.parser.parseInline(tk.tokens as Tokens.Generic[]), href = tk.href
        const f = /^(?:\.\/)?([A-Za-z0-9_-]+?)(?:\.en)?\.md(?:#(.+))?$/.exec(href)
        if (f && hasPage(f[1].toLowerCase())) { const pg = f[1].toLowerCase(); return `<a href="${docHash(pid, pg, f[2])}" data-doc-page="${pg}" ${f[2] ? `data-doc-anchor="${esc(f[2])}"` : ''}>${inner}</a>` }
        if (href.startsWith('#')) return `<a href="${docHash(pid, page, href.slice(1))}" data-doc-page="${page}" data-doc-anchor="${esc(href.slice(1))}">${inner}</a>`
        if (/^https?:\/\//i.test(href)) return `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${inner}</a>`
        return `<span class="doc-nolink">${inner}</span>`  // fichier du dépôt hors du guide embarqué : pas de lien mort
      },
    },
  })
  const html = (mk.parse(md, { async: false }) as string).replace(/<table>/g, '<div class="doc-table"><table>').replace(/<\/table>/g, '</table></div>')
  return { html, toc }
}
