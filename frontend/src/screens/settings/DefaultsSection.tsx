import { useState } from 'react'
import { Button, Card, Field, Icon, IconButton, Segmented, Select } from '../../kit'
import { useT } from '../../i18n'
import { settingsApi, type SettingsView, type Target } from './settingsApi'
import { SaveBar, useSaver } from './shared'

const CASES = ['PascalCase', 'camelCase', 'snake_case', 'UPPER_SNAKE', 'kebab-case']

export function DefaultsSection({ s, reload }: { s: SettingsView; reload: () => Promise<void> }) {
  const t = useT()
  const d = s.defaults
  const [iri, setIri] = useState(d.base_iri)
  const [target, setTarget] = useState<Target>(d.target)
  const [naming, setNaming] = useState(d.naming)
  const [rows, setRows] = useState<[string, string][]>(Object.entries(d.prefixes))
  const saver = useSaver()
  const save = () => saver.run(async () => {
    if (!/^[a-z][a-z0-9+.-]*:/i.test(iri.trim())) throw new Error(t('settings.def.iriInvalid'))
    const pf: Record<string, string> = {}
    for (const [k, v] of rows) {
      const key = k.trim(); if (!key && !v.trim()) continue
      if (!/^[A-Za-z_][\w.-]*$/.test(key)) throw new Error(t('settings.def.prefixInvalid', { p: key || '∅' }))
      if (key in pf) throw new Error(t('settings.def.prefixDup', { p: key }))
      if (!/^[a-z][a-z0-9+.-]*:/i.test(v.trim())) throw new Error(t('settings.def.prefixIri', { p: key }))
      pf[key] = v.trim()
    }
    await settingsApi.put({ defaults: { base_iri: iri.trim(), prefixes: pf, target, naming } })
    await reload()
  })
  const caseOpts = CASES.map(c => ({ value: c, label: c }))
  const setRow = (i: number, j: 0 | 1, v: string) => setRows(r => r.map((x, k) => (k === i ? (j === 0 ? [v, x[1]] : [x[0], v]) : x) as [string, string]))
  return (
    <Card title={<><Icon name="sliders" /> {t('settings.def.title')}</>}>
      <p className="set-hint">{t('settings.def.intro')}</p>
      <div className="set-grid" style={{ marginTop: 'var(--s3)' }}>
        <Field label={t('settings.def.baseIri')} hint={t('settings.def.baseIriHint')}><input type="text" className="mono" value={iri} onChange={e => setIri(e.target.value)} /></Field>
        <div className="f"><span className="muted" style={{ fontSize: 'var(--fs-xs)' }}>{t('settings.def.target')}</span>
          <Segmented label={t('settings.def.target')} value={target} onChange={setTarget} items={[['curiosity', 'Curiosity'], ['neo4j', 'Neo4j']]} /></div>
        <Field label={t('settings.def.nameClass')}><Select value={naming.class ?? 'PascalCase'} options={caseOpts} onChange={e => setNaming({ ...naming, class: e.target.value })} /></Field>
        <Field label={t('settings.def.nameProp')}><Select value={naming.property ?? 'camelCase'} options={caseOpts} onChange={e => setNaming({ ...naming, property: e.target.value })} /></Field>
      </div>
      <h3 style={{ margin: 'var(--s4) 0 var(--s2)', fontSize: 'var(--fs-md)' }}>{t('settings.def.prefixes')}</h3>
      {rows.length === 0 && <p className="set-hint">{t('settings.def.prefixesNone')}</p>}
      {rows.map(([k, v], i) => (
        <div className="set-prefix" key={i}>
          <input type="text" aria-label={t('settings.def.prefix')} placeholder="ex" value={k} onChange={e => setRow(i, 0, e.target.value)} />
          <input type="text" aria-label="IRI" placeholder="https://example.org/ns#" value={v} onChange={e => setRow(i, 1, e.target.value)} />
          <IconButton icon="trash" label={t('common.delete')} onClick={() => setRows(r => r.filter((_, j) => j !== i))} />
        </div>))}
      <Button size="sm" icon="plus" onClick={() => setRows(r => [...r, ['', '']])}>{t('settings.def.addPrefix')}</Button>
      <SaveBar saver={saver} onSave={save} />
    </Card>)
}
