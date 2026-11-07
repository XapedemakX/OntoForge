// Envoi d'un message à l'assistant (panneau global et écran plein écran) + application des actions validées par l'utilisateur.
import { tr } from '../i18n'
import type { OntoModel, Project } from '../api'
import type { AssistantContext } from '../lib/assistantContext'
import { buildItems, setProposal } from '../lib/proposal'
import { gapi } from './gapi'
import { patchAction, setLastApplied, uid, type AgentAction, type Msg } from './store'

export async function runChat(opts: {
  p: Project; setP: (p: Project) => void; lang: string; history: Msg[]; provider?: string; context: AssistantContext
  attachments?: { name: string; kind: string; content: string }[]; sourceLabel?: string
}): Promise<Msg> {
  const { p, setP, lang, history, provider, context, attachments } = opts
  try {
    const r = await gapi.chat(p.id, history.filter(m => !m.error).slice(-20).map(m => ({ role: m.role, content: m.content })), provider, context, attachments)
    const actions = (r.actions ?? []).map(a => ({ ...a, status: 'idle' as const }))
    let count: number | undefined
    const pa = actions.find(a => a.kind === 'proposal')
    if (pa) {
      const onto = pa.payload.proposal as OntoModel
      const items = buildItems(p.onto, onto, lang)
      count = items.length
      if (items.length) setProposal({ projectId: p.id, onto, source: opts.sourceLabel ?? history[history.length - 1]?.content.slice(0, 60) ?? '', items, onProject: setP })
      pa.payload = { ...pa.payload, proposal: undefined, count, labels: items.slice(0, 8).map(i => ({ label: i.label, kind: i.kind, type: i.type })) }
    }
    return { id: uid(), role: 'assistant', content: r.reply, warnings: [...new Set(r.warnings)], count, actions }
  } catch (e) {
    return { id: uid(), role: 'assistant', content: e instanceof Error ? e.message : String(e), error: true }
  }
}

const notify = (p: Project) => window.dispatchEvent(new CustomEvent('ontoforge:project', { detail: p }))

/** Applique l'action (clic de l'utilisateur). Renvoie vrai si appliquée. */
export async function applyAction(pid: string, msgId: string, idx: number, a: AgentAction, setP: (p: Project) => void): Promise<boolean> {
  patchAction(pid, msgId, idx, { status: 'busy', error: undefined })
  try {
    if (a.kind === 'ops') {
      const r = await gapi.ops(pid, a.payload.ops, 'Assistant : ' + a.summary.slice(0, 80))
      if (!r.ok) throw new Error(r.errors.map(e => e.message).join(' ; ') || tr('ui.refused'))
      setP(r.project); notify(r.project)
    } else if (a.kind === 'shapes') {
      const r = await gapi.shapes(pid, a.payload.patches)
      setP(r.project); notify(r.project)
    }
    patchAction(pid, msgId, idx, { status: 'applied' })
    setLastApplied(pid, `${msgId}:${idx}`)
    return true
  } catch (e) {
    patchAction(pid, msgId, idx, { status: 'error', error: e instanceof Error ? e.message : String(e) })
    return false
  }
}

export async function undoAction(pid: string, msgId: string, idx: number, setP: (p: Project) => void): Promise<boolean> {
  try {
    const r = await gapi.undo(pid)
    setP(r.project); notify(r.project)
    patchAction(pid, msgId, idx, { status: 'undone' }); setLastApplied(pid, null)
    return true
  } catch (e) {
    patchAction(pid, msgId, idx, { status: 'error', error: e instanceof Error ? e.message : String(e) })
    return false
  }
}

export function openGuidedQuery(pid: string, a: AgentAction) {
  try { localStorage.setItem('ontoforge.pending-query.' + pid, JSON.stringify({ ...a.payload, at: Date.now() })) } catch { /* stockage indisponible */ }
  window.dispatchEvent(new CustomEvent('ontoforge:open-query', { detail: a.payload }))
  location.hash = `#/projet/${encodeURIComponent(pid)}/requetes`
}
export const go = (pid: string, screen: string) => { location.hash = screen === 'parametres' ? '#/parametres' : `#/projet/${encodeURIComponent(pid)}/${screen}` }
