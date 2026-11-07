import { getAssistantContext, type AssistantContext } from '../lib/assistantContext'

/** Écran de la route -> noms acceptés pour `AssistantContext.screen` (les écrans déclarent leur propre vocabulaire). */
export const ROUTE_SCREEN: Record<string, { name: string; aliases: string[] }> = {
  tableau: { name: 'dashboard', aliases: ['dashboard'] },
  ontologie: { name: 'editor', aliases: ['editor', 'ontology'] },
  'ontologie-liste': { name: 'ontology-list', aliases: ['ontology-list', 'list'] },
  shapes: { name: 'shapes', aliases: ['shapes'] },
  conformite: { name: 'conformance', aliases: ['conformance'] },
  shacl: { name: 'shacl', aliases: ['shacl'] },
  analyse: { name: 'analysis', aliases: ['analysis'] },
  modele: { name: 'model', aliases: ['model'] },
  exports: { name: 'exports', aliases: ['exports'] },
  requetes: { name: 'queries', aliases: ['queries'] },
  assistant: { name: 'assistant', aliases: ['assistant'] },
}

export type CtxMode = 'full' | 'screen' | 'none'

/** Contexte déclaré par l'écran s'il correspond à la route courante, sinon contexte de base déduit de la route. */
export function effectiveContext(route: string, projectId: string, target: string, perimeter: string | null, declared: AssistantContext = getAssistantContext()): AssistantContext {
  const r = ROUTE_SCREEN[route] ?? { name: route || 'unknown', aliases: [route] }
  const base: AssistantContext = { screen: r.name, projectId, target: target as AssistantContext['target'], perimeter: perimeter || null }
  if (declared && r.aliases.includes(declared.screen) && (!declared.projectId || declared.projectId === projectId)) return { ...base, ...declared, screen: declared.screen, projectId }
  return base
}

export function forSend(ctx: AssistantContext, mode: CtxMode, projectId: string): AssistantContext {
  if (mode === 'none') return { screen: 'unknown', projectId, target: ctx.target }
  if (mode === 'screen') return { screen: ctx.screen, projectId, target: ctx.target, perimeter: ctx.perimeter }
  return ctx
}
