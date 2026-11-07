import { useEffect, useRef } from 'react'
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from '@codemirror/language'
import { setDiagnostics, lintGutter } from '@codemirror/lint'
import { json } from '@codemirror/lang-json'
import { cypher } from '@codemirror/legacy-modes/mode/cypher'
import { sparql } from '@codemirror/legacy-modes/mode/sparql'
import { turtle } from '@codemirror/legacy-modes/mode/turtle'
import { javascript } from '@codemirror/legacy-modes/mode/javascript'
import { yaml } from '@codemirror/legacy-modes/mode/yaml'
import { tags as t } from '@lezer/highlight'
// ---------- CodeMirror ----------
const hl = HighlightStyle.define([
  { tag: [t.keyword, t.operatorKeyword, t.modifier], color: 'var(--accent)', fontWeight: '600' },
  { tag: [t.string, t.special(t.string)], color: 'var(--auto)' },
  { tag: [t.number, t.bool, t.atom], color: 'var(--review)' },
  { tag: [t.comment], color: 'var(--muted)', fontStyle: 'italic' },
  { tag: [t.variableName, t.propertyName, t.typeName, t.className], color: 'var(--info)' },
  { tag: [t.meta, t.labelName, t.definition(t.variableName)], color: 'var(--lost)' },
])
const baseTheme = EditorView.theme({
  '&': { color: 'var(--ink)', backgroundColor: 'var(--code-bg)', height: '100%' },
  '.cm-gutters': { backgroundColor: 'var(--panel2)', color: 'var(--muted)', border: 'none' },
  '.cm-activeLine': { backgroundColor: 'transparent' }, '.cm-activeLineGutter': { backgroundColor: 'var(--accent-soft)' },
  '.cm-cursor': { borderLeftColor: 'var(--ink)' }, '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: 'var(--accent-soft) !important' },
  '.cm-content': { caretColor: 'var(--ink)' },
})
export function langFor(name: string): Extension[] {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'json') return [json()]
  if (ext === 'cypher' || ext === 'cql') return [StreamLanguage.define(cypher)]
  if (ext === 'rq' || ext === 'sparql') return [StreamLanguage.define(sparql)]
  if (ext === 'ttl' || ext === 'turtle') return [StreamLanguage.define(turtle)]
  if (ext === 'js' || ext === 'ts' || ext === 'cs') return [StreamLanguage.define(javascript)]
  if (ext === 'yaml' || ext === 'yml') return [StreamLanguage.define(yaml)]
  return []
}

export function CodeEditor({ value, onChange, filename = '', readOnly = false, errors, minHeight }: {
  value: string; onChange?: (v: string) => void; filename?: string; readOnly?: boolean
  errors?: { line: number; message: string }[]; minHeight?: number
}) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const cb = useRef(onChange); cb.current = onChange
  useEffect(() => {
    const v = new EditorView({
      parent: host.current!,
      state: EditorState.create({
        doc: value,
        extensions: [lineNumbers(), history(), keymap.of([...defaultKeymap, ...historyKeymap]), highlightActiveLine(), lintGutter(),
          syntaxHighlighting(hl), baseTheme, EditorView.lineWrapping, ...langFor(filename),
          EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly),
          EditorView.updateListener.of(u => { if (u.docChanged) cb.current?.(u.state.doc.toString()) })],
      }),
    })
    view.current = v
    return () => v.destroy()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filename, readOnly])
  useEffect(() => {
    const v = view.current; if (!v) return
    if (v.state.doc.toString() !== value) v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } })
  }, [value])
  useEffect(() => {
    const v = view.current; if (!v) return
    const doc = v.state.doc
    v.dispatch(setDiagnostics(v.state, (errors ?? []).filter(e => e.line >= 1 && e.line <= doc.lines).map(e => {
      const l = doc.line(e.line); return { from: l.from, to: Math.max(l.to, l.from + 1 > doc.length ? l.from : l.from + 1), severity: 'error' as const, message: e.message }
    })))
  }, [errors, value])
  return <div ref={host} style={{ minHeight, display: 'flex', flex: 1, minWidth: 0 }} className="cmhost" />
}
