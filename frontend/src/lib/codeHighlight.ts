// Coloration syntaxique minimale pour les blocs de code de la documentation (aucune dépendance).
// Volontairement simple : commentaires, chaînes, IRI, nombres, mots-clés. Le résultat est du HTML échappé.
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const KW = {
  py: 'and as assert async await break class continue def del elif else except finally for from global if import in is lambda not or pass raise return try while with yield None True False self',
  js: 'async await break case catch class const continue default delete else export extends finally for from function if import in instanceof let new of return static switch this throw try typeof var void while yield null true false undefined interface type',
  cs: 'abstract as async await break case catch class const continue default else enum false finally for foreach if in interface internal is namespace new null override private protected public readonly return static string struct switch this throw true try using var virtual void while int bool double long',
  sql: 'select from where join left right inner outer on group by order having limit insert into values update set delete create table alter drop index and or not null as distinct union with case when then else end',
  cypher: 'match optional where return with create merge set delete detach remove unwind order by skip limit union call yield and or not null as distinct in is starts ends contains constraint index unique require for on assert if exists node relationship true false',
  sparql: 'select construct ask describe where from named optional filter union minus bind values group by order having limit offset distinct reduced prefix base graph service not exists in a asc desc str lang datatype regex count sum min max avg true false',
  ttl: '@prefix @base prefix base a true false',
  sh: 'if then else elif fi for while do done case esac function in return export local cd echo exit source set unset docker npm npx pip python node git make curl cp mv rm mkdir cat grep',
  yaml: 'true false null',
  json: 'true false null',
}
type Fam = keyof typeof KW | 'none'
const ALIAS: Record<string, Fam> = {
  py: 'py', python: 'py', js: 'js', javascript: 'js', ts: 'js', typescript: 'js', tsx: 'js', jsx: 'js', json: 'json', jsonc: 'json', bash: 'sh', sh: 'sh', shell: 'sh', console: 'sh', zsh: 'sh',
  sql: 'sql', cypher: 'cypher', sparql: 'sparql', turtle: 'ttl', ttl: 'ttl', n3: 'ttl', trig: 'ttl', csharp: 'cs', cs: 'cs', 'c#': 'cs', yaml: 'yaml', yml: 'yaml', toml: 'yaml', dockerfile: 'sh',
}
const COMMENT: Record<Fam, string | null> = { py: '#[^\\n]*', js: '//[^\\n]*|/\\*[\\s\\S]*?\\*/', cs: '//[^\\n]*|/\\*[\\s\\S]*?\\*/', sql: '--[^\\n]*', cypher: '//[^\\n]*', sparql: '#[^\\n]*', ttl: '#[^\\n]*', sh: '#[^\\n]*', yaml: '#[^\\n]*', json: null, none: null }

export function highlight(code: string, lang?: string): string {
  const fam: Fam = ALIAS[(lang ?? '').toLowerCase().split(/[\s{]/)[0]] ?? 'none'
  if (fam === 'none') return esc(code)
  const kws = new Set(KW[fam].split(' '))
  const ci = fam === 'sql' || fam === 'cypher' || fam === 'sparql'
  const parts = [COMMENT[fam] ? `(?<c>${COMMENT[fam]})` : '', '(?<s>"(?:\\\\.|[^"\\\\\\n])*"|\'(?:\\\\.|[^\'\\\\\\n])*\')',
    fam === 'ttl' || fam === 'sparql' ? '(?<i><[A-Za-z][\\w+.-]*:[^<>\\s"]*>)' : '', '(?<n>\\b\\d+(?:\\.\\d+)?\\b)', '(?<w>@?[A-Za-z_$?][\\w-]*)'].filter(Boolean)
  const re = new RegExp(parts.join('|'), 'g')
  let out = '', last = 0, m: RegExpExecArray | null
  while ((m = re.exec(code))) {
    out += esc(code.slice(last, m.index)); last = m.index + m[0].length
    const g = m.groups ?? {}, txt = esc(m[0])
    if (g.c) out += `<span class="tk-c">${txt}</span>`
    else if (g.s) out += `<span class="${fam === 'json' && /^\s*:/.test(code.slice(last)) ? 'tk-k' : 'tk-s'}">${txt}</span>`
    else if (g.i) out += `<span class="tk-i">${txt}</span>`
    else if (g.n) out += `<span class="tk-n">${txt}</span>`
    else if (g.w && kws.has(ci ? g.w.toLowerCase() : g.w)) out += `<span class="tk-w">${txt}</span>`
    else out += txt
  }
  return out + esc(code.slice(last))
}
