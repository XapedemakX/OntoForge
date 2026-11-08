// REGISTRE DES ÉCRANS — pour brancher un écran : ajouter une entrée ici (voir journal/L11/rapport.md).
import { lazy, type ReactNode } from 'react'
import type { ScreenProps } from './types'
const Ontology = lazy(() => import('../screens/ontology-list').then(m => ({ default: m.OntologyList })))
const Editor = lazy(() => import('../screens/editor/Editor').then(m => ({ default: m.Editor })))
const Conformance = lazy(() => import('../screens/Conformance').then(m => ({ default: m.Conformance })))
const Shacl = lazy(() => import('../screens/shacl').then(m => ({ default: m.Shacl })))
const Analysis = lazy(() => import('../screens/Analysis').then(m => ({ default: m.Analysis })))
const Model = lazy(() => import('../screens/Model').then(m => ({ default: m.Model })))
const Exports = lazy(() => import('../screens/Exports').then(m => ({ default: m.Exports })))
const Queries = lazy(() => import('../screens/queries').then(m => ({ default: m.Queries })))
const Dashboard = lazy(() => import('../screens/Dashboard').then(m => ({ default: m.Dashboard })))
const Files = lazy(() => import('../screens/files').then(m => ({ default: m.Files })))
const AssistantScreen = lazy(() => import('../screens/assistant').then(m => ({ default: m.AssistantScreen })))

export type StepKey = 'concevoir' | 'verifier' | 'transposer' | 'generer'
export interface ScreenDef {
  key: string                    // segment de l'URL : #/projet/<id>/<key>
  labelKey: string               // clé i18n (nav.*)
  icon: string                   // Font Awesome solid
  step?: StepKey                 // groupe du parcours ; absent = entrée hors parcours (tableau, outils)
  render: (props: ScreenProps) => ReactNode
  editing?: boolean              // écran d'édition : bandeau « consultation » sur mobile
  fullBleed?: boolean            // pas de padding : l'écran gère sa mise en page (éditeur, assistant)
  badge?: 'pending'              // pastille du nombre de constats à arbitrer
}
export const SCREENS: ScreenDef[] = [
  { key: 'tableau', labelKey: 'nav.tableau', icon: 'gauge-high', render: p => <Dashboard {...p} /> },
  { key: 'ontologie', labelKey: 'nav.ontologie', icon: 'sitemap', step: 'concevoir', editing: true, fullBleed: true, render: p => <Editor {...p} /> },
  { key: 'ontologie-liste', labelKey: 'nav.liste', icon: 'list-ul', step: 'concevoir', editing: true, fullBleed: true, render: p => <Ontology {...p} /> },
  { key: 'shapes', labelKey: 'nav.shapes', icon: 'shapes', step: 'concevoir', editing: true, render: p => <Shacl {...p} initialTab="shapes" /> },
  { key: 'fichiers', labelKey: 'nav.fichiers', icon: 'file-code', step: 'concevoir', editing: true, fullBleed: true, render: p => <Files {...p} /> },
  { key: 'conformite', labelKey: 'nav.conformite', icon: 'clipboard-check', step: 'verifier', render: p => <Conformance {...p} /> },
  { key: 'shacl', labelKey: 'nav.shacl', icon: 'shield-halved', step: 'verifier', render: p => <Shacl {...p} initialTab="valid" /> },
  { key: 'analyse', labelKey: 'nav.analyse', icon: 'scale-balanced', step: 'transposer', badge: 'pending', render: p => <Analysis {...p} /> },
  { key: 'modele', labelKey: 'nav.modele', icon: 'diagram-project', step: 'transposer', render: p => <Model {...p} /> },
  { key: 'exports', labelKey: 'nav.exports', icon: 'file-export', step: 'generer', render: p => <Exports {...p} /> },
  { key: 'requetes', labelKey: 'nav.requetes', icon: 'magnifying-glass-chart', step: 'generer', editing: true, render: p => <Queries {...p} /> },
  { key: 'assistant', labelKey: 'nav.assistant', icon: 'wand-magic-sparkles', fullBleed: true, render: p => <AssistantScreen {...p} /> },
]
export const STEPS: StepKey[] = ['concevoir', 'verifier', 'transposer', 'generer']
