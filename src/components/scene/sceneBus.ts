/**
 * Form ↔ 3B sahne arasındaki minik olay hattı.
 *
 * Neden context değil: sahne <canvas> içinde requestAnimationFrame ile dönüyor,
 * React render döngüsüne bağlanması gereksiz yeniden çizimler doğurur. Kullanıcı
 * bir seçim yaptığında sahneye tek yönlü bir "darbe" göndermek yetiyor.
 */

export type ScenePulse = {
  /** Darbenin rengi (0-1 aralığında RGB). Seçilen alanın vurgu rengi. */
  color?: [number, number, number]
  /** 0-1; varsayılan 1. Küçük etkileşimler (slider sürükleme) için düşük. */
  strength?: number
}

type Listener = (pulse: ScenePulse) => void

const listeners = new Set<Listener>()

export function pulseScene(pulse: ScenePulse = {}) {
  for (const listener of listeners) listener(pulse)
}

export function onScenePulse(listener: Listener) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** '#4B41B5' → [0.294, 0.255, 0.710] */
export function hexToRgb01(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}
