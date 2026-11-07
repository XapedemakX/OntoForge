// Icône et teinte d'une classe : déduites du nom (mots-clés) puis d'un hachage stable. Aucune donnée d'icône dans le modèle.
const KEYS: [RegExp, string][] = [
  [/electric|battery|batter/, 'bolt'], [/vehic|car\b|auto/, 'car-side'], [/engine|motor|moteur/, 'gears'], [/technic|mechanic|worker|employee/, 'user-gear'],
  [/customer|client|person|owner|driver|people/, 'user'], [/garage|workshop|organi|company|site/, 'warehouse'], [/order|ticket|request|job/, 'clipboard-list'],
  [/operation|service|task|action|repair/, 'wrench'], [/brand|make|manufact/, 'tag'], [/model/, 'cubes'], [/code|fault|error|dtc|diagnos/, 'triangle-exclamation'],
  [/warrant|insur|contract/, 'shield-halved'], [/fuel|energy/, 'gas-pump'], [/part|piece|component|spare/, 'puzzle-piece'], [/invoice|bill|payment|price/, 'file-invoice'],
  [/document|report|file/, 'file-lines'], [/place|location|address|city/, 'location-dot'], [/event|date|time/, 'calendar'], [/product|item|article/, 'box'],
]
export function classIcon(name: string): string {
  const n = name.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  for (const [re, ic] of KEYS) if (re.test(n)) return ic
  return 'circle-nodes'
}
/** Teinte parmi trois jetons de sévérité neutres (lagon, bleu encre, ambre). */
export function classTone(iri: string): 't0' | 't1' | 't2' {
  let h = 0; for (let i = 0; i < iri.length; i++) h = (h * 31 + iri.charCodeAt(i)) >>> 0
  return (['t0', 't1', 't2'] as const)[h % 3]
}
