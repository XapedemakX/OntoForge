import type { OntoModel, Project } from '../../api'
import type { Kind, Tr } from './model'
import type { Op } from '../editor/types'

export interface SheetCtx {
  p: Project; onto: OntoModel; lang: string; t: Tr
  apply: (ops: Op[], label?: string) => Promise<boolean>
  edit: (fn: (o: OntoModel) => void, label?: string) => Promise<boolean>   // repli : PUT /onto (individus : pas d'opération dédiée)
  go: (iri: string) => void
  toast: (m: string) => void
  icons: Record<string, string>; abstract: Set<string>
  lbl: (iri: string) => string
  ask: (prompt: string, send?: boolean) => void
  select: (iri: string, kind: Kind) => void
}
