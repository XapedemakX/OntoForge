import { useState } from 'react'
import { Button, Icon, SeverityBadge } from '../../kit'
import { useT } from '../../i18n'
import { CodeEditor, copy, useToast } from '../../ui'
import type { BuildResult } from './qapi'

type Lang = 'sparql' | 'cypher' | 'curiosity' | 'graphql'
const LANGS: [Lang, string][] = [['sparql', 'SPARQL'], ['cypher', 'Cypher'], ['curiosity', 'Curiosity'], ['graphql', 'GraphQL']]
const FILE: Record<Lang, string> = { sparql: 'q.sparql', cypher: 'q.cypher', curiosity: 'q.cs', graphql: 'q.graphql' }

function Pane({ lang, label, code, solo }: { lang: Lang; label: string; code: string | null; solo?: boolean }) {
  const t = useT(); const toast = useToast()
  return (
    <div className="qcode-pane">
      <div className="qcode-hd"><b>{label}</b><span className="grow" />
        <Button size="sm" icon="copy" disabled={!code} onClick={async () => toast((await copy(code ?? '')) ? t('q.copied', { l: label }) : t('q.copy.fail'))}>{t('q.copy')}</Button></div>
      <div className={`qcode-ed ${solo ? 'solo' : ''}`}>
        {code ? <CodeEditor key={lang + code.length} value={code} readOnly filename={FILE[lang]} /> : <p className="muted qcode-none">{t('q.code.none', { l: label })}</p>}
      </div>
    </div>
  )
}

export function CodePanel({ build, error, building }: { build: BuildResult | null; error: string | null; building: boolean }) {
  const t = useT()
  const [tab, setTab] = useState<Lang>('sparql')
  const [side, setSide] = useState(false)
  const sevOf = (n: string) => (n.startsWith('[perte]') ? 'lost' : n.startsWith('[info]') ? 'info' : 'review') as 'lost' | 'info' | 'review'
  return (
    <section className="qcode" aria-label={t('q.code')} aria-busy={building}>
      <div className="qcode-top">
        <h2>{t('q.code')}</h2>
        {build && <span className={`sev ${build.lossy ? 'review' : 'auto'}`}><Icon name={build.lossy ? 'scale-balanced' : 'circle-check'} />{build.lossy ? t('q.code.lossy') : t('q.code.exact')}</span>}
        <span className="grow" />
        <label className="qt"><input type="checkbox" checked={side} onChange={e => setSide(e.target.checked)} />{t('q.code.side')}</label>
      </div>
      {error && <div className="notice error" role="alert">{error}</div>}
      {!build && !error && <p className="muted qcode-none">{t('q.code.idle')}</p>}
      {build && (side
        ? <div className="qcode-side">{LANGS.map(([k, l]) => <Pane key={k} lang={k} label={l} code={build[k]} />)}</div>
        : <>
            <div className="tabs" role="tablist">{LANGS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{build[k] == null && k !== 'sparql' && <Icon name="ban" className="tabno" />}</button>)}</div>
            <Pane lang={tab} label={LANGS.find(x => x[0] === tab)![1]} code={build[tab]} solo />
          </>)}
      {build && build.notes.length > 0 && (
        <ul className="qnotes" aria-label={t('q.notes')}>
          {build.notes.map((n, i) => <li key={i}><SeverityBadge severity={sevOf(n)} label={t('q.note.' + sevOf(n))} /><span>{n.replace(/^\[(perte|info|[^\]]+)\]\s*/, '')}</span></li>)}
        </ul>
      )}
    </section>
  )
}
