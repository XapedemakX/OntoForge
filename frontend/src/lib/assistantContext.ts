/**
 * Contrat de l'assistant global Krakie (itération 2, retours de Jerem du 4/11).
 *
 * Chaque écran déclare ce qui est affiché (écran, sélection, objets visibles) avec
 * `useAssistantContext(ctx)`. Le bouton Krakie, présent partout, et les boutons
 * contextuels des écrans appellent `openAssistant(...)`. Le panneau de l'assistant
 * global (implémenté dans src/assistant-global/) écoute ces événements, envoie le
 * contexte au serveur et applique les actions proposées après validation de l'utilisateur.
 *
 * Ce module est volontairement sans dépendance : il ne fait que publier et lire un état.
 */
import { useEffect } from 'react'

export type AssistantScreen =
  | 'dashboard' | 'editor' | 'ontology-list' | 'shapes' | 'shacl' | 'files' | 'conformance'
  | 'analysis' | 'model' | 'exports' | 'queries' | 'settings' | 'projects' | 'assistant' | string

export interface AssistantContext {
  screen: AssistantScreen
  projectId?: string
  target?: 'curiosity' | 'neo4j'
  perimeter?: string | null
  /** Élément sélectionné à l'écran (IRI de classe, de propriété, id de shape, de constat…). */
  selection?: { kind: string; id: string; label?: string } | null
  /** Données utiles et compactes propres à l'écran (ex. requête guidée courante, filtre actif). */
  extra?: Record<string, unknown>
  /** Suggestions rapides proposées par l'écran (« Ajoute une propriété à … »). */
  suggestions?: string[]
}

export interface OpenAssistantOptions {
  /** Texte pré-rempli ou envoyé directement si `send` est vrai. */
  prompt?: string
  send?: boolean
  /** Contexte ponctuel qui complète le contexte déclaré par l'écran. */
  context?: Partial<AssistantContext>
}

const CTX_EVENT = 'ontoforge:assistant-context'
const OPEN_EVENT = 'ontoforge:assistant-open'
let current: AssistantContext = { screen: 'unknown' }

export function setAssistantContext(ctx: AssistantContext): void {
  current = ctx
  window.dispatchEvent(new CustomEvent(CTX_EVENT, { detail: ctx }))
}

export function getAssistantContext(): AssistantContext {
  return current
}

/** À appeler dans chaque écran ; `deps` = valeurs qui changent le contexte. */
export function useAssistantContext(ctx: AssistantContext, deps: unknown[] = []): void {
  useEffect(() => {
    setAssistantContext(ctx)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx.screen, ctx.projectId, ctx.target, ctx.perimeter, ctx.selection?.id, ...deps])
}

export function openAssistant(opts: OpenAssistantOptions = {}): void {
  window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: opts }))
}

export function onAssistantOpen(fn: (o: OpenAssistantOptions) => void): () => void {
  const h = (e: Event) => fn((e as CustomEvent).detail || {})
  window.addEventListener(OPEN_EVENT, h)
  return () => window.removeEventListener(OPEN_EVENT, h)
}

export function onAssistantContext(fn: (c: AssistantContext) => void): () => void {
  const h = (e: Event) => fn((e as CustomEvent).detail)
  window.addEventListener(CTX_EVENT, h)
  return () => window.removeEventListener(CTX_EVENT, h)
}
