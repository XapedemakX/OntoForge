// Moteur d'édition de l'écran Fichiers : extensions CodeMirror 6 (langages, repli, recherche, multi-curseur, autocomplétion, thème).
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection, rectangularSelection, crosshairCursor, dropCursor } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { HighlightStyle, StreamLanguage, bracketMatching, foldGutter, foldKeymap, foldService, indentOnInput, syntaxHighlighting, type StreamParser } from '@codemirror/language'
import { search, searchKeymap, highlightSelectionMatches, openSearchPanel } from '@codemirror/search'
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap, type CompletionContext, type CompletionResult, type Completion } from '@codemirror/autocomplete'
import { lintGutter, lintKeymap } from '@codemirror/lint'
import { json } from '@codemirror/lang-json'
import { cypher } from '@codemirror/legacy-modes/mode/cypher'
import { sparql } from '@codemirror/legacy-modes/mode/sparql'
import { turtle } from '@codemirror/legacy-modes/mode/turtle'
import { csharp } from '@codemirror/legacy-modes/mode/clike'
import { tags as t } from '@lezer/highlight'
import type { OntoModel } from '../../api'
import { curie, localName } from '../../api'

// ---- GraphQL : mode simple maison (aucun paquet GraphQL CodeMirror 6 épinglé dans le projet) ----
const GQL_KW = new Set(['type', 'input', 'enum', 'interface', 'union', 'scalar', 'schema', 'query', 'mutation', 'subscription', 'fragment', 'extend', 'implements', 'directive', 'on', 'repeatable'])
const graphql: StreamParser<unknown> = {
  token(stream) {
    if (stream.eatSpace()) return null
    if (stream.match('"""')) { while (!stream.eol() && !stream.match('"""')) stream.next(); return 'string' }
    if (stream.peek() === '#') { stream.skipToEnd(); return 'comment' }
    if (stream.peek() === '"') { stream.next(); while (!stream.eol()) { const c = stream.next(); if (c === '\\') stream.next(); else if (c === '"') break } return 'string' }
    if (stream.match(/^-?\d+(\.\d+)?/)) return 'number'
    if (stream.match(/^@[A-Za-z_]\w*/)) return 'meta'
    if (stream.match(/^\$[A-Za-z_]\w*/)) return 'variableName'
    if (stream.match(/^[A-Za-z_]\w*/)) {
      const w = stream.current()
      if (GQL_KW.has(w)) return 'keyword'
      if (w === 'true' || w === 'false' || w === 'null') return 'atom'
      return /^[A-Z]/.test(w) ? 'typeName' : 'propertyName'
    }
    stream.next(); return null
  },
}

// ---- repli de code pour Turtle : une déclaration = sa première ligne + les lignes indentées qui suivent ----
const foldTurtle = foldService.of((state, from) => {
  const line = state.doc.lineAt(from)
  if (!line.text.trim() || /^\s/.test(line.text) || /^(#|@|prefix\b|base\b)/i.test(line.text)) return null
  let end = line.number
  for (let n = line.number + 1; n <= state.doc.lines; n++) {
    const l = state.doc.line(n)
    if (/^\s+\S/.test(l.text)) end = n
    else if (!l.text.trim()) continue
    else break
  }
  return end > line.number ? { from: line.to, to: state.doc.line(end).to } : null
})

export function languageFor(language: string): Extension[] {
  switch (language) {
    case 'turtle': case 'trig': return [StreamLanguage.define(turtle), foldTurtle]
    case 'sparql': return [StreamLanguage.define(sparql)]
    case 'json': return [json()]
    case 'csharp': return [StreamLanguage.define(csharp)]
    case 'cypher': return [StreamLanguage.define(cypher)]
    case 'graphql': return [StreamLanguage.define(graphql)]
    default: return []
  }
}

const hl = HighlightStyle.define([
  { tag: [t.keyword, t.operatorKeyword, t.modifier], color: 'var(--accent)', fontWeight: '600' },
  { tag: [t.string, t.special(t.string)], color: 'var(--auto)' },
  { tag: [t.number, t.bool, t.atom], color: 'var(--review)' },
  { tag: [t.comment], color: 'var(--muted)', fontStyle: 'italic' },
  { tag: [t.variableName, t.propertyName, t.typeName, t.className], color: 'var(--info)' },
  { tag: [t.meta, t.labelName, t.definition(t.variableName)], color: 'var(--lost)' },
])

const theme = EditorView.theme({
  '&': { color: 'var(--ink)', backgroundColor: 'var(--code-bg)', height: '100%', fontSize: '13px' },
  '.cm-scroller': { fontFamily: "'IBM Plex Mono', ui-monospace, monospace", lineHeight: '1.55' },
  '.cm-gutters': { backgroundColor: 'var(--panel2)', color: 'var(--muted)', border: 'none' },
  '.cm-activeLine': { backgroundColor: 'color-mix(in srgb, var(--accent-soft) 45%, transparent)' },
  '.cm-activeLineGutter': { backgroundColor: 'var(--accent-soft)', color: 'var(--ink)' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--ink)' },
  '&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground': { backgroundColor: 'var(--accent-soft)' },
  '.cm-selectionMatch': { backgroundColor: 'color-mix(in srgb, var(--accent) 22%, transparent)' },
  '&.cm-focused .cm-matchingBracket': { backgroundColor: 'color-mix(in srgb, var(--accent) 30%, transparent)', outline: '1px solid var(--accent)' },
  '.cm-foldPlaceholder': { backgroundColor: 'var(--panel2)', border: '1px solid var(--line)', color: 'var(--muted)' },
  '.cm-panels': { backgroundColor: 'var(--panel)', color: 'var(--ink)', borderColor: 'var(--line)' },
  '.cm-panels input, .cm-panels button': { fontSize: '12px' },
  '.cm-panels .cm-textfield': { background: 'var(--code-bg)', color: 'var(--ink)', border: '1px solid var(--line-strong)', borderRadius: '4px' },
  '.cm-panels .cm-button': { backgroundImage: 'none', background: 'var(--panel2)', color: 'var(--ink)', border: '1px solid var(--line-strong)', borderRadius: '4px' },
  '.cm-searchMatch': { backgroundColor: 'color-mix(in srgb, var(--review) 30%, transparent)' },
  '.cm-searchMatch-selected': { backgroundColor: 'color-mix(in srgb, var(--review) 55%, transparent)' },
  '.cm-tooltip': { backgroundColor: 'var(--panel)', color: 'var(--ink)', border: '1px solid var(--line-strong)', borderRadius: '6px' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': { backgroundColor: 'var(--accent-soft)', color: 'var(--ink)' },
  '.cm-completionDetail': { color: 'var(--muted)', fontStyle: 'normal', marginLeft: '8px' },
  '.cm-diagnostic': { fontFamily: 'inherit' },
})

const FR: Record<string, string> = {
  Find: 'Rechercher', Replace: 'Remplacer', next: 'suivant', previous: 'précédent', all: 'tout', 'match case': 'respecter la casse',
  regexp: 'regex', 'by word': 'mot entier', replace: 'remplacer', 'replace all': 'tout remplacer', close: 'fermer',
  'Go to line': 'Aller à la ligne', go: 'OK', 'Fold code': 'Replier', 'Unfold code': 'Déplier', 'Folded lines': 'Lignes repliées',
  'Unfolded lines': 'Lignes dépliées', 'folded code': 'code replié', unfold: 'déplier', 'Control character': 'Caractère de contrôle',
  'replaced $ matches': '$ occurrences remplacées', 'replaced match on line $': 'occurrence remplacée ligne $', 'on line': 'ligne',
  'current match': 'occurrence courante', 'Selection deleted': 'Sélection supprimée', 'Diagnostics': 'Diagnostics', 'No diagnostics': 'Aucun diagnostic',
}

// ---- autocomplétion : préfixes déclarés, IRIs du projet (nom local et libellé), mots-clés Turtle et SHACL ----
export interface CompletionModel { onto: OntoModel | null; lang: string }
const TTL_KW = ['@prefix', '@base', 'PREFIX', 'BASE', 'a', 'true', 'false']
const VOCAB: Record<string, [string, string[]]> = {
  owl: ['http://www.w3.org/2002/07/owl#', ['Class', 'ObjectProperty', 'DatatypeProperty', 'AnnotationProperty', 'Ontology', 'NamedIndividual', 'Restriction', 'onProperty', 'someValuesFrom', 'allValuesFrom', 'minCardinality', 'maxCardinality', 'cardinality', 'equivalentClass', 'disjointWith', 'inverseOf', 'FunctionalProperty', 'TransitiveProperty', 'SymmetricProperty', 'versionIRI', 'imports', 'unionOf', 'intersectionOf', 'complementOf', 'oneOf']],
  rdfs: ['http://www.w3.org/2000/01/rdf-schema#', ['label', 'comment', 'subClassOf', 'subPropertyOf', 'domain', 'range', 'seeAlso', 'isDefinedBy', 'Datatype']],
  rdf: ['http://www.w3.org/1999/02/22-rdf-syntax-ns#', ['type', 'Property', 'List', 'first', 'rest', 'nil', 'langString']],
  xsd: ['http://www.w3.org/2001/XMLSchema#', ['string', 'integer', 'int', 'long', 'decimal', 'double', 'float', 'boolean', 'date', 'dateTime', 'anyURI', 'nonNegativeInteger', 'positiveInteger']],
  sh: ['http://www.w3.org/ns/shacl#', ['NodeShape', 'PropertyShape', 'targetClass', 'targetNode', 'targetSubjectsOf', 'targetObjectsOf', 'property', 'path', 'datatype', 'class', 'nodeKind', 'minCount', 'maxCount', 'minLength', 'maxLength', 'pattern', 'flags', 'in', 'hasValue', 'node', 'or', 'and', 'not', 'xone', 'closed', 'ignoredProperties', 'uniqueLang', 'languageIn', 'minInclusive', 'maxInclusive', 'minExclusive', 'maxExclusive', 'name', 'description', 'message', 'severity', 'deactivated', 'inversePath', 'alternativePath', 'zeroOrMorePath', 'oneOrMorePath', 'zeroOrOnePath', 'qualifiedValueShape', 'qualifiedMinCount', 'qualifiedMaxCount', 'sparql', 'IRI', 'Literal', 'BlankNode', 'Violation', 'Warning', 'Info']],
}
const SHACL_ONLY = new Set(['sh'])

export function prefixesOf(text: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const m of text.matchAll(/^\s*(?:@prefix|prefix)\s+([A-Za-z][\w.-]*)?:\s*<([^>]*)>/gim)) out[m[1] ?? ''] = m[2]
  return out
}

export function turtleCompletions(getModel: () => CompletionModel) {
  return (ctx: CompletionContext): CompletionResult | null => {
    const iriCtx = ctx.matchBefore(/<[^<>\s]*/)
    const word = ctx.matchBefore(/[@\w][\w.:#\-@]*|:[\w.\-]*/)
    if (!word && !iriCtx && !ctx.explicit) return null
    const text = ctx.state.doc.toString()
    const pm = prefixesOf(text)
    const model = getModel()
    const opts: Completion[] = []
    const fr = model.lang === 'fr'
    if (iriCtx) {
      if (model.onto) for (const [iri, e] of entities(model.onto)) opts.push({ label: `<${iri}`, apply: `<${iri}>`, detail: e.label || localName(iri), type: e.type })
      for (const ns of Object.values(pm)) opts.push({ label: `<${ns}`, apply: `<${ns}`, type: 'namespace' })
      return { from: iriCtx.from, options: opts, validFor: /^<[^<>\s]*$/ }
    }
    const from = word ? word.from : ctx.pos
    const typed = word ? word.text.toLowerCase() : ''
    // préfixes déclarés (nom:)
    for (const p of Object.keys(pm)) opts.push({ label: p + ':', type: 'namespace', detail: fr ? 'préfixe déclaré' : 'declared prefix', boost: 3 })
    // IRIs du projet : nom local et libellé
    if (model.onto) {
      for (const [iri, e] of entities(model.onto)) {
        const c = curie(iri, pm)
        const form = c.includes(':') && Object.keys(pm).some(p => pm[p] && iri.startsWith(pm[p])) ? c : `<${iri}>`
        const hay = `${form} ${localName(iri)} ${e.label}`.toLowerCase()
        if (!typed || hay.includes(typed.replace(/^@/, ''))) opts.push({ label: form, detail: e.label ? `${e.label}` : kindLabel(e.type, fr), type: e.type, boost: 2 })
      }
    }
    // vocabulaires standard (owl, rdfs, sh…) : le préfixe doit être déclaré, sinon on propose l'IRI complète
    for (const [pre, [ns, names]] of Object.entries(VOCAB)) {
      const decl = Object.entries(pm).find(([, v]) => v === ns)?.[0]
      for (const n of names) {
        const label = decl !== undefined ? `${decl}:${n}` : `${pre}:${n}`
        opts.push({ label, type: SHACL_ONLY.has(pre) ? 'property' : 'keyword', detail: SHACL_ONLY.has(pre) ? 'SHACL' : pre.toUpperCase(), boost: decl !== undefined ? 1 : -1,
          ...(decl === undefined ? { info: fr ? `Déclarez @prefix ${pre}: <${ns}> .` : `Declare @prefix ${pre}: <${ns}> .` } : {}) })
      }
    }
    for (const k of TTL_KW) opts.push({ label: k, type: 'keyword', boost: -2 })
    const f = typed
    const filtered = f ? opts.filter(o => (o.label + ' ' + (o.detail ?? '')).toLowerCase().includes(f.replace(/^@/, ''))) : opts
    return { from, options: filtered, filter: false }
  }
}

function kindLabel(type: string | undefined, fr: boolean): string {
  const m: Record<string, [string, string]> = { class: ['classe', 'class'], property: ['propriété', 'property'], function: ['propriété', 'property'], variable: ['individu', 'individual'] }
  const x = m[type ?? '']; return x ? (fr ? x[0] : x[1]) : ''
}
function entities(o: OntoModel): [string, { label: string; type: string }][] {
  const lab = (e: { labels: Record<string, string> }) => e.labels.fr || e.labels.en || Object.values(e.labels)[0] || ''
  const out: [string, { label: string; type: string }][] = []
  for (const [iri, e] of Object.entries(o.classes)) out.push([iri, { label: lab(e), type: 'class' }])
  for (const [iri, e] of Object.entries(o.object_properties)) out.push([iri, { label: lab(e), type: 'property' }])
  for (const [iri, e] of Object.entries(o.datatype_properties)) out.push([iri, { label: lab(e), type: 'property' }])
  return out
}

export interface BuildOpts {
  doc: string; language: string; readOnly: boolean; lang: string
  getModel: () => CompletionModel
  onChange: (doc: string) => void
  onCursor: (line: number, col: number, selection: string) => void
  onSave: () => void
}

export function buildExtensions(o: BuildOpts): Extension[] {
  const completion = o.language === 'turtle' || o.language === 'trig' ? [autocompletion({ override: [turtleCompletions(o.getModel)], activateOnTyping: true })] : [autocompletion()]
  return [
    lineNumbers(), highlightActiveLineGutter(), foldGutter(), lintGutter(), history(), drawSelection(), dropCursor(), indentOnInput(), bracketMatching(),
    EditorState.allowMultipleSelections.of(true), rectangularSelection(), crosshairCursor(), highlightActiveLine(), highlightSelectionMatches(),
    search({ top: true }), closeBrackets(), ...completion,
    keymap.of([
      { key: 'Mod-s', preventDefault: true, run: () => { o.onSave(); return true } },
      { key: 'Mod-h', preventDefault: true, run: v => { openSearchPanel(v); return true } },
      ...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...foldKeymap, ...completionKeymap, ...lintKeymap, indentWithTab,
    ]),
    syntaxHighlighting(hl), theme, ...languageFor(o.language),
    ...(o.lang === 'fr' ? [EditorState.phrases.of(FR)] : []),
    EditorState.readOnly.of(o.readOnly), EditorView.editable.of(!o.readOnly),
    EditorView.contentAttributes.of({ 'aria-label': o.language }),
    EditorView.updateListener.of(u => {
      if (u.docChanged) o.onChange(u.state.doc.toString())
      if (u.docChanged || u.selectionSet) {
        const s = u.state.selection.main; const l = u.state.doc.lineAt(s.head)
        o.onCursor(l.number, s.head - l.from + 1, s.empty ? '' : u.state.sliceDoc(s.from, Math.min(s.to, s.from + 4000)))
      }
    }),
  ]
}
