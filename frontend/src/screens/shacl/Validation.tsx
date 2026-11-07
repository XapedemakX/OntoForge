import { useMemo, useState } from 'react'
import { curie, labelOf, type Project, type ShaclReport, type ShaclResult } from '../../api'
import { Button, EmptyState, Icon, IconButton } from '../../kit'
import { useI18n } from '../../i18n'
import { constraintKey, ownerOf, pathLabel, sev, SEV_ICON, shapeTitle } from './helpers'

export function Validation({ p, rep, fileName, busy, onFile, onOpenShape, onAsk }: {
  p: Project; rep: ShaclReport | null; fileName: string; busy: boolean
  onFile: (f: File) => void; onOpenShape: (shapeId: string, propId?: string) => void; onAsk: (r: ShaclResult, shapeId: string | null) => void
}) {
  const { t, lang } = useI18n()
  const [drag, setDrag] = useState(false)
  const pf = { ...p.shapes.prefixes, ...p.onto.meta.prefixes }
  const owner = useMemo(() => ownerOf(p.shapes), [p.shapes])
  const groups = useMemo(() => {
    if (!rep) return []
    const g = new Map<string, Map<string, ShaclResult[]>>()
    for (const r of rep.results) {
      const sid = (r.shape && (owner[r.shape] ?? (p.shapes.shapes[r.shape] ? r.shape : null))) || ''
      if (!g.has(sid)) g.set(sid, new Map())
      const m = g.get(sid)!; if (!m.has(r.focus)) m.set(r.focus, []); m.get(r.focus)!.push(r)
    }
    return [...g.entries()]
  }, [rep, owner, p.shapes])
  const nodeLabel = (iri: string) => { const i = p.onto.individuals[iri]; return i ? labelOf(i, iri, lang) : curie(iri, pf) }
  return (
    <div className="shv" data-tour="shacl-valid">
      <div className={'shv-drop' + (drag ? ' on' : '')} onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f) }}>
        <Icon name="file-arrow-up" />
        <div className="grow"><b>{t('sh.v.drop')}</b><span className="muted">{fileName ? t('sh.v.last', { v: fileName }) : t('sh.v.hint')}</span></div>
        <label className="btn primary"><Icon name="folder-open" />{busy ? t('sh.v.running') : t('sh.v.choose')}<input type="file" hidden data-testid="valid-file" accept=".ttl,.rdf,.owl,.nt,.jsonld,.json,.xml,text/turtle" onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = '' }} /></label>
      </div>
      {!rep && <EmptyState title={t('sh.v.empty.t')} pose="accueil">{t('sh.v.empty.d')}</EmptyState>}
      {rep?.conforms && <div className="shv-ok"><Icon name="circle-check" /><div><b>{t('sh.v.ok')}</b><span>{t('sh.v.ok.d', { v: fileName })}</span></div></div>}
      {rep && !rep.conforms && (
        <>
          <p className="shv-sum"><Icon name="circle-xmark" /><b>{t('sh.v.sum', { n: rep.results.length, s: groups.length })}</b><span className="muted">{fileName}</span></p>
          {groups.map(([sid, nodes]) => {
            const shape = sid ? p.shapes.shapes[sid] : null
            const total = [...nodes.values()].reduce((a, l) => a + l.length, 0)
            return (
              <section className="shv-group" key={sid || '_'}>
                <header>
                  <h3>{shape ? shapeTitle(shape, p.onto, lang).title : t('sh.v.noshape')}</h3>
                  {shape && <span className="mono muted">{curie(shape.id, pf)}</span>}
                  <span className="grow" />
                  <span className="badge Violation">{t(total === 1 ? 'sh.v.n1' : 'sh.v.n', { n: total })}</span>
                  {shape && <Button size="sm" icon="arrow-up-right-from-square" onClick={() => onOpenShape(shape.id, rep.results.find(r => r.shape && owner[r.shape] === sid)?.shape ?? undefined)}>{t('sh.v.open')}</Button>}
                </header>
                {[...nodes.entries()].map(([focus, list]) => (
                  <div className="shv-node" key={focus}>
                    <div className="shv-nodehd"><Icon name="circle-dot" /><b>{nodeLabel(focus)}</b><span className="mono muted" title={focus}>{curie(focus, pf)}</span></div>
                    <table className="shgrid shv-tab">
                      <colgroup><col className="v-sev" /><col className="v-path" /><col className="v-con" /><col className="v-msg" /><col className="v-val" /><col className="c-act" /></colgroup>
                      <tbody>
                        {list.map((r, i) => {
                          const s = sev(r.severity)
                          return (
                            <tr key={i}>
                              <td><span className={'shsev static ' + s}><Icon name={SEV_ICON[s]} />{t('sh.sev.' + s)}</span></td>
                              <td><div className="pth"><b>{r.path ? pathLabel({ kind: 'predicate', iri: r.path, args: [] }, p.onto, lang) : '—'}</b><span className="mono">{r.path ? curie(r.path, pf) : ''}</span></div></td>
                              <td>{t('sh.cc.' + constraintKey(r.constraint)) !== 'sh.cc.' + constraintKey(r.constraint) ? t('sh.cc.' + constraintKey(r.constraint)) : constraintKey(r.constraint)}</td>
                              <td>{r.message}</td>
                              <td className="mono">{r.value ?? ''}</td>
                              <td className="act"><IconButton icon="wand-magic-sparkles" label={t('sh.k.why')} onClick={() => onAsk(r, sid || null)} /></td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                ))}
              </section>
            )
          })}
        </>
      )}
    </div>
  )
}
