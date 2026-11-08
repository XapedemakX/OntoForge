import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { setDiagnostics, type Diagnostic } from '@codemirror/lint'
import { buildExtensions, type CompletionModel } from './cm'
import type { Diag } from './fapi'

export interface CodeHostApi { goto(line: number, col: number): void; focus(): void }
interface Props {
  path: string; language: string; readOnly: boolean; initial: string; rev: number; lang: string
  diagnostics: Diag[]; getModel: () => CompletionModel
  onChange: (path: string, doc: string) => void
  onCursor: (line: number, col: number, selection: string) => void
  onSave: () => void
}

/** Un seul EditorView ; un EditorState par onglet (l'historique d'annulation de chaque onglet est conservé). */
export const CodeHost = forwardRef<CodeHostApi, Props>(function CodeHost(props, ref) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const states = useRef(new Map<string, { st: EditorState; rev: number }>())
  const cur = useRef(props); cur.current = props

  const make = (doc: string) => EditorState.create({
    doc,
    extensions: buildExtensions({
      doc, language: cur.current.language, readOnly: cur.current.readOnly, lang: cur.current.lang, getModel: () => cur.current.getModel(),
      onChange: d => cur.current.onChange(cur.current.path, d),
      onCursor: (l, c, s) => cur.current.onCursor(l, c, s),
      onSave: () => cur.current.onSave(),
    }),
  })

  useEffect(() => {
    const v = new EditorView({ parent: host.current! })
    view.current = v
    return () => { v.destroy(); view.current = null }
  }, [])

  // changement d'onglet ou rechargement forcé (rev) : on range l'état courant puis on installe celui de l'onglet visé
  const lastPath = useRef<string | null>(null)
  useEffect(() => {
    const v = view.current; if (!v) return
    if (lastPath.current && lastPath.current !== props.path) states.current.set(lastPath.current, { st: v.state, rev: states.current.get(lastPath.current)?.rev ?? 0 })
    const known = states.current.get(props.path)
    if (!known || known.rev !== props.rev || known.st.readOnly !== props.readOnly) {
      const st = make(props.initial); states.current.set(props.path, { st, rev: props.rev }); v.setState(st)
    } else v.setState(known.st)
    lastPath.current = props.path
    { const sel = v.state.selection.main; const l = v.state.doc.lineAt(sel.head); props.onCursor(l.number, sel.head - l.from + 1, sel.empty ? '' : v.state.sliceDoc(sel.from, Math.min(sel.to, sel.from + 4000))) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.path, props.rev, props.readOnly])

  useEffect(() => {
    const v = view.current; if (!v) return
    const doc = v.state.doc
    const ds: Diagnostic[] = []
    for (const d of props.diagnostics) {
      if (d.line < 1 || d.line > doc.lines) continue
      const l = doc.line(d.line)
      const from = Math.min(l.to, l.from + Math.max(0, d.col - 1))
      const m = /^[^\s;,.\])}]+/.exec(l.text.slice(from - l.from))
      const to = Math.min(l.to, from + Math.max(1, m ? m[0].length : 1))
      ds.push({ from: Math.min(from, doc.length), to: Math.max(to, Math.min(from + 1, doc.length)), severity: d.severity, message: `${d.message} [${d.code}]` })
    }
    v.dispatch(setDiagnostics(v.state, ds))
  }, [props.diagnostics, props.path, props.rev])

  useImperativeHandle(ref, () => ({
    goto(line, col) {
      const v = view.current; if (!v) return
      const l = v.state.doc.line(Math.max(1, Math.min(line, v.state.doc.lines)))
      const pos = Math.min(l.to, l.from + Math.max(0, col - 1))
      v.dispatch({ selection: { anchor: pos }, effects: EditorView.scrollIntoView(pos, { y: 'center' }) })
      v.focus()
    },
    focus() { view.current?.focus() },
  }))

  return <div ref={host} className="fx-cm" data-testid="fx-editor" />
})
