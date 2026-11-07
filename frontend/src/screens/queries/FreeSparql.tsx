import { useState } from 'react'
import { api, type TranslationResult } from '../../api'
import { Button, Icon, SeverityBadge } from '../../kit'
import { useT } from '../../i18n'
import { CodeEditor, copy, ErrorView, Tabs, useToast } from '../../ui'
import type { Target } from '../../api'

/** Onglet « SPARQL libre » : saisie SPARQL, exécution sur l'endpoint actif et traduction vers la cible (écran Requêtes d'origine). */
export function FreeSparql({ pid, target, sparql, setSparql, onRun, busy }: { pid: string; target: Target; sparql: string; setSparql: (s: string) => void; onRun: () => void; busy: boolean }) {
  const t = useT(); const toast = useToast()
  const [res, setRes] = useState<TranslationResult | null>(null)
  const [err, setErr] = useState<unknown>(null)
  const [tab, setTab] = useState<'cypher' | 'curiosity' | 'graphql'>('cypher')
  const [tb, setTb] = useState(false)
  const translate = async () => { setTb(true); setErr(null); try { setRes(await api.translate(pid, target, sparql)) } catch (e) { setErr(e) } finally { setTb(false) } }
  const out = res?.[tab] ?? ''
  return (
    <div className="qfree">
      <div className="qfree-ed">
        <div className="qcode-hd"><b>SPARQL</b><span className="grow" />
          <Button size="sm" icon="language" disabled={tb || !sparql.trim()} onClick={translate}>{t('q.free.translate')}</Button>
          <Button size="sm" variant="primary" icon="play" disabled={busy || !sparql.trim()} onClick={onRun}>{t('q.run')}</Button></div>
        <div className="qfree-box"><CodeEditor value={sparql} onChange={setSparql} filename="q.sparql" /></div>
      </div>
      <div className="qfree-out">
        <div className="qcode-hd"><b>{t('q.free.result')}</b>{res && <SeverityBadge severity={res.lossy ? 'review' : 'auto'} label={res.lossy ? t('q.code.lossy') : t('q.code.exact')} />}<span className="grow" />
          {out && <Button size="sm" icon="copy" onClick={async () => toast((await copy(out)) ? t('q.copied', { l: tab }) : t('q.copy.fail'))}>{t('q.copy')}</Button>}</div>
        <Tabs value={tab} onChange={setTab} items={[['cypher', 'Cypher'], ['curiosity', 'Curiosity'], ['graphql', 'GraphQL']]} />
        <div className="qfree-box">{res ? <CodeEditor key={tab + out.length} value={out || t('q.free.nolang')} readOnly filename={tab === 'cypher' ? 'a.cypher' : 'a.txt'} /> : <p className="muted qcode-none">{t('q.free.hint')}</p>}</div>
        <ErrorView error={err} what={t('q.free.translate')} />
        {res && res.notes.length > 0 && <ul className="qnotes">{res.notes.map((n, i) => <li key={i}><Icon name="circle-info" /><span>{n}</span></li>)}</ul>}
      </div>
    </div>
  )
}
