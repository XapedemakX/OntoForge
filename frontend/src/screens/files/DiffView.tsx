import { useEffect, useRef } from 'react'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { MergeView } from '@codemirror/merge'
import { useI18n } from '../../i18n'

/** Diff côte à côte (CodeMirror merge) entre le texte actuel du projet et le texte résultant de l'application. */
export function DiffView({ a, b }: { a: string; b: string }) {
  const host = useRef<HTMLDivElement>(null)
  const { lang } = useI18n()
  useEffect(() => {
    const ro = [...(lang === 'fr' ? [EditorState.phrases.of({ '$ unchanged lines': '$ lignes inchangées' })] : []), EditorState.readOnly.of(true), EditorView.editable.of(false), EditorView.lineWrapping]
    const mv = new MergeView({ a: { doc: a, extensions: ro }, b: { doc: b, extensions: ro }, parent: host.current!, highlightChanges: true, gutter: true, collapseUnchanged: { margin: 2, minSize: 6 } })
    return () => mv.destroy()
  }, [a, b, lang])
  return <div ref={host} className="fx-diff" data-testid="fx-diff" />
}
