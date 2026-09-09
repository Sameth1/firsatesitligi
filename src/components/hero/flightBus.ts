/**
 * Hero'daki kağıt uçak uçuşu için minik zaman hattı köprüsü.
 *
 * Neden context/state değil: uçuşun kaynağı Hero'daki GSAP timeline'ı, tüketicisi
 * ise HeroCanvas'ın requestAnimationFrame döngüsü. İkisini React render'ına
 * bağlamak saniyede 60 yeniden render demek olurdu. sceneBus.ts'deki desenle
 * aynı: modül düzeyinde tek bir değer + setter/getter.
 *
 * Tek bir mutasyona uğrayan nesne tutulur (her karede yeni nesne üretilmez).
 */

export type FlightState = {
  /** 0 → 1 uçuş ilerlemesi. Eğri üzerindeki yay-uzunluğu parametresi. */
  t: number
  /** Uçuş şu an oynuyor mu. false ise sahne uçağı ve izi gizler. */
  active: boolean
}

const state: FlightState = { t: 0, active: false }

export function setFlightProgress(t: number) {
  state.t = t
}

export function setFlightActive(active: boolean) {
  state.active = active
  if (!active) state.t = 1
}

export function getFlight(): Readonly<FlightState> {
  return state
}

/**
 * Uçuş yalnız ilk açılışta oynar. İlk çağıran `true` alır; sonrakiler `false`.
 * Hero yeniden mount olsa (kaydırıp geri gelme, route geçişi) animasyon
 * tekrarlanmaz.
 */
let claimed = false

export function claimFlight(): boolean {
  if (claimed) return false
  claimed = true
  return true
}

/** Uçuş tamamlanmadan Hero sökülürse hakkı geri ver (StrictMode çift-mount dahil). */
export function releaseFlight() {
  claimed = false
  state.active = false
  state.t = 0
}

/**
 * WebGL katmanı dinamik import edildiği için Hero'nun effect'inden sonra hazır
 * olabilir. Timeline'ı sahne hazır olana kadar bekletmek, uçuşun ilk karelerinin
 * kaçırılmasını önler. Hero yine de kısa bir timeout ile kendini kurtarır.
 */
let sceneReady = false
const readyWaiters = new Set<() => void>()

export function markFlightSceneReady() {
  if (sceneReady) return
  sceneReady = true
  for (const cb of readyWaiters) cb()
  readyWaiters.clear()
}

export function whenFlightSceneReady(cb: () => void): () => void {
  if (sceneReady) {
    cb()
    return () => {}
  }
  readyWaiters.add(cb)
  return () => { readyWaiters.delete(cb) }
}
