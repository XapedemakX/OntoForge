/** Bips 8 bits en WebAudio. Coupé par défaut ; le contexte n'est créé qu'à la première activation (geste utilisateur). */
type Note = [freq: number, dur: number, type?: OscillatorType, vol?: number]
const SEQ: Record<string, Note[]> = {
  catch: [[660, 0.05, 'square', 0.04]],
  reset: [[220, 0.08, 'square', 0.04], [180, 0.08, 'square', 0.04]],
  triple: [[523, 0.07], [659, 0.07], [784, 0.07], [1047, 0.14]],
  hit: [[300, 0.1, 'sawtooth', 0.06], [200, 0.1, 'sawtooth', 0.06], [120, 0.18, 'sawtooth', 0.06]],
  bonus: [[880, 0.06], [1175, 0.06], [1568, 0.1]],
  shield: [[440, 0.12, 'triangle', 0.07], [330, 0.08, 'triangle', 0.07]],
  level: [[392, 0.08], [523, 0.08], [659, 0.08], [784, 0.08], [1047, 0.2]],
  over: [[392, 0.15], [330, 0.15], [262, 0.15], [196, 0.35]],
}
export class Sfx {
  enabled = false
  private ctx: AudioContext | null = null
  setEnabled(on: boolean) {
    this.enabled = on
    if (!on) return
    try {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!this.ctx && AC) this.ctx = new AC()
      void this.ctx?.resume()
    } catch { this.ctx = null }
  }
  play(name: string) {
    const ctx = this.ctx
    if (!this.enabled || !ctx || ctx.state !== 'running') return
    let t = ctx.currentTime
    for (const [f, d, type = 'square', vol = 0.05] of SEQ[name] ?? []) {
      const o = ctx.createOscillator(), g = ctx.createGain()
      o.type = type; o.frequency.value = f
      g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + d)
      o.connect(g).connect(ctx.destination); o.start(t); o.stop(t + d + 0.02)
      t += d
    }
  }
  close() { try { void this.ctx?.close() } catch { /* ignoré */ } this.ctx = null }
}
