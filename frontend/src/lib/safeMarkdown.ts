// Rendu Markdown sûr des textes qui viennent d'un LLM ou d'un fichier importé (L39-secu, SEC-08).
// Règles : HTML brut affiché comme texte ; liens limités à http(s) et mailto (tout autre schéma, dont javascript:, data: et vbscript:,
// devient du texte simple) ; aucune image (le texte de remplacement est affiché) ; liens externes en nouvel onglet sans référent.
import { Marked, type Tokens } from 'marked'

export const escHtml = (s: string): string => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')

/** Adresse admise dans un lien, ou null. Liste blanche : les caractères de contrôle et espaces insérés pour masquer un schéma sont retirés avant l'essai. */
export function safeHref(href: string | null | undefined): string | null {
  const h = (href ?? '').replace(/[\u0000-\u0020\u007f-\u009f\u200b-\u200f\u2028\u2029\ufeff]+/g, '')
  return /^(https?:\/\/|mailto:)/i.test(h) ? h : null
}

const md = new Marked({
  gfm: true,
  async: false,
  renderer: {
    html(tk: Tokens.HTML | Tokens.Tag) { return escHtml(tk.text) },
    link(this: { parser: { parseInline(t: Tokens.Generic[]): string } }, tk: Tokens.Link) {
      const inner = this.parser.parseInline(tk.tokens as Tokens.Generic[])
      const href = safeHref(tk.href)
      return href ? `<a href="${escHtml(href)}" target="_blank" rel="noopener noreferrer">${inner}</a>` : inner
    },
    image(tk: Tokens.Image) { return escHtml(tk.text || '') },
  },
})

export function renderSafeMarkdown(text: string): string {
  return md.parse(text, { async: false }) as string
}
