import { getAssistantContext, type AssistantContext } from '../lib/assistantContext'

/** Écran de la route -> noms acceptés pour `AssistantContext.screen` (les écrans déclarent leur propre vocabulaire). */
export const ROUTE_SCREEN: Record<string, { name: string; aliases: string[] }> = {
  tableau: { name: 'dashboard', aliases: ['dashboard'] },
  ontologie: { name: 'editor', aliases: ['editor', 'ontology'] },
  'ontologie-liste': { name: 'ontology-list', aliases: ['ontology-list', 'list'] },
  'carte-metier': { name: 'business-map', aliases: ['business-map'] },
  shapes: { name: 'shapes', aliases: ['shapes'] },
  fichiers: { name: 'files', aliases: ['files'] },
  conformite: { name: 'conformance', aliases: ['conformance'] },
  shacl: { name: 'shacl', aliases: ['shacl'] },
  analyse: { name: 'analysis', aliases: ['analysis'] },
  modele: { name: 'model', aliases: ['model'] },
  exports: { name: 'exports', aliases: ['exports'] },
  versions: { name: 'versions', aliases: ['versions'] },
  requetes: { name: 'queries', aliases: ['queries'] },
  assistant: { name: 'assistant', aliases: ['assistant'] },
  documentation: { name: 'documentation', aliases: ['documentation'] },
  parametres: { name: 'settings', aliases: ['settings'] },
  plus: { name: 'mobile', aliases: ['mobile'] },
}

export type CtxMode = 'full' | 'screen' | 'none'

/** Contexte déclaré par l'écran s'il correspond à la route courante, sinon contexte de base déduit de la route. */
export function effectiveContext(route: string, projectId: string, target: string, perimeter: string | null, declared: AssistantContext = getAssistantContext()): AssistantContext {
  const r = ROUTE_SCREEN[route] ?? { name: route || 'unknown', aliases: [route] }
  const base: AssistantContext = { screen: r.name, projectId, target: target as AssistantContext['target'], perimeter: perimeter || null }
  if (declared?.screen === 'sharing' && declared.projectId === projectId) return { ...base, ...declared, screen: 'sharing', projectId }   // le panneau de partage (L40) est ouvert par-dessus l'écran
  if (declared && r.aliases.includes(declared.screen) && (!declared.projectId || declared.projectId === projectId)) return { ...base, ...declared, screen: declared.screen, projectId }
  return base
}

/** Écran Paramètres (L38) : pas de projet. Le contexte déclaré par l'écran porte l'onglet affiché (`extra.section`) et ses suggestions. */
export function settingsContext(declared: AssistantContext = getAssistantContext()): AssistantContext {
  return declared && declared.screen === 'settings' ? { ...declared, projectId: undefined, target: undefined, perimeter: null } : { screen: 'settings' }
}
/** Ce qui part au serveur depuis les Paramètres : l'écran et l'onglet (rien d'autre), ou l'écran seul si l'utilisateur a retiré le contexte. */
export function forSendSettings(ctx: AssistantContext, mode: CtxMode): AssistantContext {
  return mode === 'none' ? { screen: 'settings' } : { screen: 'settings', extra: ctx.extra?.section ? { section: ctx.extra.section } : undefined }
}

export function forSend(ctx: AssistantContext, mode: CtxMode, projectId: string): AssistantContext {
  if (mode === 'none') return { screen: 'unknown', projectId, target: ctx.target }
  if (mode === 'screen') return { screen: ctx.screen, projectId, target: ctx.target, perimeter: ctx.perimeter }
  return ctx
}
