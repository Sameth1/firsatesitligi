'use client'

/**
 * Arama ve sonuç ekranlarının 3B zemini.
 *
 * Eskiden burada krem tonlu tek bir gradient shader vardı; ekran "beyaz kağıt"
 * gibi duruyordu. Artık üç katman var:
 *
 *  1) Backdrop shader — domain-warped fbm ile akan aurora + ekran uzayında
 *     hesaplanan sonsuz ızgara zemin (ek geometri yok) + vinyet + film grain.
 *  2) Obje katmanı — eğitim temalı, prosedürel üretilmiş düşük-poli objeler
 *     (mezuniyet kepi, kitap, küre, kağıt uçak, diploma, kalem). Yüzey rengi
 *     fresnel + ince-film irizasyonundan türetiliyor; doku/ışık dosyası yok.
 *  3) Parçacık alanı — additive blending ile derinlik.
 *
 * Etkileşim: fare paralaksı, kaydırma, ve sceneBus üzerinden gelen "darbe"ler
 * (kullanıcı formda bir seçim yaptığında sahne o rengin tonuna doğru parlar).
 *
 * Performans: canvas sticky bir kutuda tek ekran boyunda kalır (sayfa uzadıkça
 * büyümez), DPR 1.5 ile sınırlı, sekme arkadayken ve sahne görünmezken rAF
 * durur, prefers-reduced-motion'da tek kare çizilir.
 */

import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { onScenePulse } from './sceneBus'

const VERT_FULLSCREEN = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`

const FRAG_BACKDROP = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uAspect;
  uniform float uScroll;
  uniform float uPulse;
  uniform vec3  uPulseColor;
  uniform vec2  uMouse;
  uniform float uDensity;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.02; a *= 0.5; }
    return v;
  }

  // Tam sayı koordinatlarda çizgi. fwidth kullanmıyoruz — türev uzantısı
  // GLSL ES 1.00'da garanti değil; kalınlığı uzaklıkla kendimiz büyütüyoruz.
  float gridAxis(float coord, float width) {
    float d = abs(fract(coord - 0.5) - 0.5);
    return 1.0 - smoothstep(0.0, width, d);
  }

  void main() {
    vec2 uv = vUv;
    vec2 p = vec2(uv.x * uAspect, uv.y + uScroll * 0.35);
    float t = uTime * 0.045;

    // ── Aurora ────────────────────────────────────────────────────────────
    vec2 warp = vec2(fbm(p * 1.4 + t), fbm(p * 1.4 - t + 5.2));
    float n  = fbm(p * 1.9 + warp * 1.5 + uMouse * 0.18);
    float n2 = fbm(p * 2.7 - warp * 0.9 - t * 1.4);

    vec3 space   = vec3(0.027, 0.024, 0.086);   // #070616
    vec3 indigo  = vec3(0.129, 0.106, 0.322);   // #211B52
    vec3 violet   = vec3(0.365, 0.271, 0.784);  // #5D45C8
    vec3 teal    = vec3(0.106, 0.749, 0.678);   // #1BBFAD
    vec3 magenta = vec3(0.788, 0.271, 0.596);   // #C94598

    vec3 col = mix(space, indigo, smoothstep(0.18, 0.85, n));
    col = mix(col, violet,  smoothstep(0.52, 1.0, n) * 0.85 * uDensity);
    col = mix(col, teal,    smoothstep(0.60, 1.0, n2) * 0.45 * uDensity);
    col = mix(col, magenta, smoothstep(0.72, 1.0, fbm(p * 2.2 + t * 0.7)) * 0.30 * uDensity);

    // ── Sonsuz ızgara zemin (ekran uzayında) ─────────────────────────────
    vec2 sp = (uv - 0.5) * vec2(uAspect, 1.0);
    float horizon = -0.17;
    if (sp.y < horizon) {
      float depth = 0.26 / (horizon - sp.y);
      vec2 fp = vec2(sp.x * depth * 1.9, depth + uTime * 0.16 + uScroll * 2.4);
      // Kalınlık sınırlanmazsa uzakta smoothstep eşiği 0.5'i aşar ve zemin
      // çizgi yerine dolu bir ışık düzlemine dönüşür.
      float w = min(0.22, 0.016 + depth * 0.011);
      float lines = max(gridAxis(fp.x, w), gridAxis(fp.y, w));
      float fade = exp(-depth * 0.62) * smoothstep(horizon, horizon - 0.05, sp.y);
      col += mix(violet, teal, 0.5 + 0.5 * sin(fp.y * 0.35)) * lines * fade * 0.30;
    }

    // ── Işık havuzları — içerik sütununun arkasını hafifçe aydınlatır ────
    float glow = smoothstep(0.75, 0.0, length((uv - vec2(0.5, 0.72)) * vec2(uAspect, 1.0)));
    col += violet * glow * 0.16 * uDensity;

    // ── Seçim darbesi ────────────────────────────────────────────────────
    float ring = smoothstep(0.55, 0.0, length((uv - vec2(0.5, 0.5)) * vec2(uAspect, 1.0)));
    col += uPulseColor * uPulse * ring * 0.55;

    // vinyet + grain
    col *= 1.0 - 0.42 * pow(length((uv - 0.5) * vec2(uAspect, 1.0)) * 0.95, 2.2);
    col += (hash(uv * 900.0 + uTime) - 0.5) * 0.022;

    gl_FragColor = vec4(col, 1.0);
  }
`

// Objelerin cam/iridesan yüzeyi. Işık kaynağı yok — renk tamamen normal ve
// bakış açısından türetiliyor, bu yüzden ucuz ve tutarlı.
const VERT_GLASS = /* glsl */ `
  precision mediump float;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying float vHeight;
  void main() {
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vec4 world = modelMatrix * vec4(position, 1.0);
    vViewDir = normalize(cameraPosition - world.xyz);
    vHeight = position.y;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const FRAG_GLASS = /* glsl */ `
  precision mediump float;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying float vHeight;
  uniform vec3  uColorA;
  uniform vec3  uColorB;
  uniform float uTime;
  uniform float uPulse;
  uniform float uOpacity;

  void main() {
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(vViewDir);
    float fres = pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 2.4);

    // ince-film irizasyonu: bakış açısına göre kayan gökkuşağı
    float ang = dot(N, V);
    vec3 irid = 0.5 + 0.5 * cos(6.28318 * (vec3(0.0, 0.33, 0.67) + ang * 2.1 + uTime * 0.04));

    vec3 col = mix(uColorA, uColorB, N.y * 0.5 + 0.5);
    col = mix(col, irid, 0.26);
    // Kenar parlaması rengin üstüne eklenir ama doygunluğu korunsun diye
    // beyaza değil, rengin kendi açık tonuna doğru karıştırılıyor.
    col = mix(col, min(col * 2.4 + 0.12, vec3(1.0)), fres * 0.55);
    col += uPulse * 0.30;

    gl_FragColor = vec4(col, (uOpacity + fres * 0.26 + uPulse * 0.15));
  }
`

type Kind = 'cap' | 'book' | 'globe' | 'plane' | 'scroll' | 'pencil'

/** Eğitim temalı düşük-poli objeler — hepsi prosedürel, dosya indirmiyoruz. */
function buildShape(kind: Kind, material: THREE.Material): {
  group: THREE.Group
  geometries: THREE.BufferGeometry[]
} {
  const group = new THREE.Group()
  const geometries: THREE.BufferGeometry[] = []

  const add = (geo: THREE.BufferGeometry, pos: [number, number, number], rot?: [number, number, number]) => {
    geometries.push(geo)
    const mesh = new THREE.Mesh(geo, material)
    mesh.position.set(...pos)
    if (rot) mesh.rotation.set(...rot)
    group.add(mesh)
    return mesh
  }

  if (kind === 'cap') {
    add(new THREE.BoxGeometry(1.75, 0.09, 1.75), [0, 0.30, 0], [0, Math.PI / 4, 0])
    add(new THREE.CylinderGeometry(0.50, 0.60, 0.44, 20), [0, 0.04, 0])
    add(new THREE.SphereGeometry(0.10, 10, 8), [0, 0.38, 0])
    add(new THREE.CylinderGeometry(0.025, 0.025, 0.55, 6), [0.86, 0.06, 0])
    add(new THREE.ConeGeometry(0.11, 0.30, 8), [0.86, -0.34, 0], [Math.PI, 0, 0])
  } else if (kind === 'book') {
    add(new THREE.BoxGeometry(0.95, 0.07, 1.25), [-0.50, 0.10, 0], [0, 0, 0.20])
    add(new THREE.BoxGeometry(0.95, 0.07, 1.25), [0.50, 0.10, 0], [0, 0, -0.20])
    add(new THREE.BoxGeometry(0.80, 0.05, 1.10), [-0.48, 0.20, 0], [0, 0, 0.26])
    add(new THREE.BoxGeometry(0.80, 0.05, 1.10), [0.48, 0.20, 0], [0, 0, -0.26])
    add(new THREE.CylinderGeometry(0.07, 0.07, 1.25, 8), [0, 0.02, 0], [Math.PI / 2, 0, 0])
  } else if (kind === 'globe') {
    add(new THREE.SphereGeometry(0.98, 18, 12), [0, 0, 0])
    // meridyenler — küreyi "dünya" olarak okutan detay
    for (let i = 0; i < 3; i++) {
      add(new THREE.TorusGeometry(1.0, 0.022, 6, 40), [0, 0, 0], [Math.PI / 2, (i * Math.PI) / 3, 0])
    }
    add(new THREE.TorusGeometry(0.86, 0.022, 6, 40), [0, 0.48, 0], [Math.PI / 2, 0, 0])
    add(new THREE.TorusGeometry(0.86, 0.022, 6, 40), [0, -0.48, 0], [Math.PI / 2, 0, 0])
  } else if (kind === 'plane') {
    // kağıt uçak — elle yazılmış dart geometrisi
    const v = new Float32Array([
      0, 0, 1.35, -1.0, 0, -0.85, 0, 0, -0.35,
      0, 0, 1.35, 0, 0, -0.35, 1.0, 0, -0.85,
      0, 0, 1.35, 0, 0.34, -0.62, 0, 0, -0.35,
      0, 0, 1.35, 0, 0, -0.35, 0, -0.10, -0.62,
    ])
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(v, 3))
    geo.computeVertexNormals()
    geometries.push(geo)
    const mesh = new THREE.Mesh(geo, material)
    mesh.material = material
    group.add(mesh)
  } else if (kind === 'scroll') {
    add(new THREE.CylinderGeometry(0.26, 0.26, 1.7, 18), [0, 0, 0], [0, 0, Math.PI / 2])
    add(new THREE.TorusGeometry(0.30, 0.07, 8, 22), [-0.85, 0, 0], [0, Math.PI / 2, 0])
    add(new THREE.TorusGeometry(0.30, 0.07, 8, 22), [0.85, 0, 0], [0, Math.PI / 2, 0])
    add(new THREE.TorusGeometry(0.22, 0.05, 8, 20), [0, -0.30, 0], [Math.PI / 2, 0, 0])
  } else {
    // pencil
    add(new THREE.CylinderGeometry(0.15, 0.15, 1.5, 8), [0, 0.12, 0])
    add(new THREE.ConeGeometry(0.15, 0.38, 8), [0, -0.82, 0])
    add(new THREE.ConeGeometry(0.05, 0.10, 8), [0, -1.05, 0])
    add(new THREE.CylinderGeometry(0.16, 0.16, 0.20, 8), [0, 0.96, 0])
  }

  return { group, geometries }
}

type Placement = {
  kind: Kind
  /** Görünür alanın yarı genişliğine/yüksekliğine oran (-1..1) — mutlak birim
   *  kullanınca objeler dar ekranlarda içerik sütununun üstüne biniyordu. */
  xr: number; yr: number
  z: number
  scale: number
  colors: [number[], number[]]
}

const VIOLET: number[] = [0.365, 0.271, 0.784]
const TEAL: number[]   = [0.106, 0.749, 0.678]
const PINK: number[]   = [0.788, 0.271, 0.596]
const AMBER: number[]  = [0.949, 0.667, 0.302]
const BLUE: number[]   = [0.243, 0.451, 0.898]

// Objeler daima kenarlarda ve geride durur — ortadaki içerik sütununu boğmazlar.
const LAYOUT: Placement[] = [
  { kind: 'cap',    xr: -0.86, yr:  0.44, z: -5.0, scale: 1.15, colors: [VIOLET, TEAL] },
  { kind: 'globe',  xr:  0.87, yr:  0.22, z: -4.0, scale: 1.20, colors: [TEAL, BLUE] },
  { kind: 'book',   xr: -0.84, yr: -0.50, z: -6.0, scale: 1.30, colors: [PINK, VIOLET] },
  { kind: 'plane',  xr:  0.85, yr: -0.58, z: -5.0, scale: 1.10, colors: [BLUE, TEAL] },
  { kind: 'scroll', xr:  0.88, yr:  0.84, z: -8.0, scale: 1.35, colors: [AMBER, PINK] },
  { kind: 'pencil', xr: -0.88, yr:  0.88, z: -7.0, scale: 1.30, colors: [AMBER, VIOLET] },
  { kind: 'globe',  xr: -0.82, yr: -0.94, z: -9.0, scale: 1.25, colors: [VIOLET, PINK] },
]

export default function SearchScene({ density = 1 }: { density?: number }) {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
    } catch {
      return // WebGL yok — CSS gradient fallback görünür kalır
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setSize(host.clientWidth, host.clientHeight)
    renderer.domElement.style.display = 'block'
    host.appendChild(renderer.domElement)

    // ── 1. Backdrop ───────────────────────────────────────────────────────
    const bgScene = new THREE.Scene()
    const bgCamera = new THREE.Camera()
    const bgUniforms = {
      uTime: { value: 0 },
      uAspect: { value: host.clientWidth / Math.max(1, host.clientHeight) },
      uScroll: { value: 0 },
      uPulse: { value: 0 },
      uPulseColor: { value: new THREE.Vector3(...VIOLET) },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uDensity: { value: density },
    }
    const bgGeometry = new THREE.PlaneGeometry(2, 2)
    const bgMaterial = new THREE.ShaderMaterial({
      vertexShader: VERT_FULLSCREEN,
      fragmentShader: FRAG_BACKDROP,
      uniforms: bgUniforms,
      depthWrite: false,
      depthTest: false,
    })
    bgScene.add(new THREE.Mesh(bgGeometry, bgMaterial))

    // ── 2. Objeler ────────────────────────────────────────────────────────
    const objScene = new THREE.Scene()
    const objCamera = new THREE.PerspectiveCamera(52, host.clientWidth / Math.max(1, host.clientHeight), 0.1, 80)
    objCamera.position.z = 14

    const materials: THREE.ShaderMaterial[] = []
    const geometries: THREE.BufferGeometry[] = []
    const shapes: {
      group: THREE.Group
      place: Placement
      spin: THREE.Vector3
      floatSpeed: number
      baseY: number
      baseScale: number
    }[] = []

    LAYOUT.forEach((place, i) => {
      const material = new THREE.ShaderMaterial({
        vertexShader: VERT_GLASS,
        fragmentShader: FRAG_GLASS,
        uniforms: {
          uColorA: { value: new THREE.Vector3(...place.colors[0]) },
          uColorB: { value: new THREE.Vector3(...place.colors[1]) },
          uTime: { value: 0 },
          uPulse: { value: 0 },
          uOpacity: { value: 0.15 },
        },
        transparent: true,
        depthWrite: false,
        side: THREE.DoubleSide,
      })
      materials.push(material)

      const built = buildShape(place.kind, material)
      geometries.push(...built.geometries)
      built.group.position.z = place.z
      built.group.scale.setScalar(place.scale)
      built.group.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0)
      objScene.add(built.group)

      shapes.push({
        group: built.group,
        place,
        spin: new THREE.Vector3(0.06 + i * 0.010, 0.09 + i * 0.008, 0.02 + i * 0.004),
        floatSpeed: 0.45 + i * 0.15,
        baseY: 0,
        baseScale: place.scale,
      })
    })

    /**
     * Objeleri, kendi derinliklerindeki görünür alanın kenarlarına oturtur.
     * Ekran oranı değişince (telefon → masaüstü) tekrar çağrılır, böylece
     * objeler hiçbir zaman içerik sütununun önüne düşmez.
     */
    function placeShapes() {
      const halfFov = (objCamera.fov * Math.PI) / 360
      // Dar ekranda görünür alan daralıyor ama objeler küçülmüyordu; başlığın
      // üstüne binmemeleri için hem ölçek düşer hem de kenara daha çok itilir.
      const wide = Math.min(1, objCamera.aspect / 1.3)
      const sizeFactor = 0.5 + 0.5 * wide
      const pushOut = 1 + (1 - wide) * 0.16

      for (const s of shapes) {
        const distance = objCamera.position.z - s.place.z
        const halfH = Math.tan(halfFov) * distance
        const halfW = halfH * objCamera.aspect
        s.group.position.x = s.place.xr * halfW * pushOut
        s.baseY = s.place.yr * halfH
        s.group.position.y = s.baseY
        s.baseScale = s.place.scale * sizeFactor
        s.group.scale.setScalar(s.baseScale)
      }
    }

    // ── 3. Parçacıklar ────────────────────────────────────────────────────
    const dustCount = 320
    const dustPositions = new Float32Array(dustCount * 3)
    for (let i = 0; i < dustCount; i++) {
      dustPositions[i * 3]     = (Math.random() - 0.5) * 34
      dustPositions[i * 3 + 1] = (Math.random() - 0.5) * 26
      dustPositions[i * 3 + 2] = -Math.random() * 22
    }
    const dustGeometry = new THREE.BufferGeometry()
    dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3))

    // PointsMaterial varsayılanı kare piksel çizer — radyal alfa ile yuvarlatıyoruz
    const spriteCanvas = document.createElement('canvas')
    spriteCanvas.width = spriteCanvas.height = 64
    const sctx = spriteCanvas.getContext('2d')!
    const grad = sctx.createRadialGradient(32, 32, 0, 32, 32, 32)
    grad.addColorStop(0, 'rgba(255,255,255,1)')
    grad.addColorStop(0.4, 'rgba(214,206,255,0.5)')
    grad.addColorStop(1, 'rgba(255,255,255,0)')
    sctx.fillStyle = grad
    sctx.fillRect(0, 0, 64, 64)
    const dustTexture = new THREE.CanvasTexture(spriteCanvas)

    const dustMaterial = new THREE.PointsMaterial({
      size: 0.14,
      map: dustTexture,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const dust = new THREE.Points(dustGeometry, dustMaterial)
    objScene.add(dust)

    // ── Etkileşim ─────────────────────────────────────────────────────────
    const pointer = { x: 0, y: 0 }
    const pointerTarget = { x: 0, y: 0 }
    function onPointerMove(e: PointerEvent) {
      pointerTarget.x = (e.clientX / window.innerWidth) * 2 - 1
      pointerTarget.y = -((e.clientY / window.innerHeight) * 2 - 1)
    }
    window.addEventListener('pointermove', onPointerMove, { passive: true })

    let pulse = 0
    const pulseColor = new THREE.Vector3(...VIOLET)
    const offPulse = onScenePulse(({ color, strength = 1 }) => {
      pulse = Math.min(1.4, pulse + strength)
      if (color) pulseColor.set(...color)
    })

    let scrollTarget = 0
    function onScroll() {
      const max = document.body.scrollHeight - window.innerHeight
      scrollTarget = max > 0 ? window.scrollY / max : 0
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()

    function resize() {
      const w = host!.clientWidth
      const h = Math.max(1, host!.clientHeight)
      renderer.setSize(w, h)
      bgUniforms.uAspect.value = w / h
      objCamera.aspect = w / h
      objCamera.updateProjectionMatrix()
      placeShapes()
    }
    placeShapes()
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(host)

    let visible = true
    const io = new IntersectionObserver(
      entries => { visible = entries[0]?.isIntersecting ?? true },
      { threshold: 0 }
    )
    io.observe(host)

    const clock = new THREE.Clock()
    let raf = 0

    function draw() {
      const t = clock.getElapsedTime()

      pulse *= 0.94                                   // darbe yumuşakça söner
      pointer.x += (pointerTarget.x - pointer.x) * 0.045
      pointer.y += (pointerTarget.y - pointer.y) * 0.045

      bgUniforms.uTime.value = t
      bgUniforms.uScroll.value += (scrollTarget - bgUniforms.uScroll.value) * 0.06
      bgUniforms.uMouse.value.set(pointer.x, pointer.y)
      bgUniforms.uPulse.value = pulse
      bgUniforms.uPulseColor.value.copy(pulseColor)

      for (const m of materials) {
        m.uniforms.uTime.value = t
        m.uniforms.uPulse.value = pulse * 0.7
      }

      for (const s of shapes) {
        s.group.rotation.x += s.spin.x * 0.01 * (1 + pulse)
        s.group.rotation.y += s.spin.y * 0.01 * (1 + pulse)
        s.group.rotation.z += s.spin.z * 0.01
        s.group.position.y = s.baseY + Math.sin(t * 0.35 * s.floatSpeed) * 0.55
        s.group.scale.setScalar(s.baseScale * (1 + pulse * 0.10))
      }

      dust.rotation.y = t * 0.012
      dust.position.y = -bgUniforms.uScroll.value * 3.0

      objCamera.position.x = pointer.x * 1.1
      objCamera.position.y = pointer.y * 0.7 - bgUniforms.uScroll.value * 3.2
      objCamera.lookAt(0, -bgUniforms.uScroll.value * 3.2, 0)

      renderer.autoClear = true
      renderer.render(bgScene, bgCamera)
      renderer.autoClear = false
      renderer.clearDepth()
      renderer.render(objScene, objCamera)
      renderer.autoClear = true
    }

    function loop() {
      raf = requestAnimationFrame(loop)
      if (!visible || document.hidden) return
      draw()
    }

    if (reduced) draw()
    else loop()

    return () => {
      cancelAnimationFrame(raf)
      offPulse()
      io.disconnect()
      resizeObserver.disconnect()
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('pointermove', onPointerMove)
      bgGeometry.dispose()
      bgMaterial.dispose()
      geometries.forEach(g => g.dispose())
      materials.forEach(m => m.dispose())
      dustGeometry.dispose()
      dustMaterial.dispose()
      dustTexture.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement)
    }
  }, [density])

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'absolute', inset: 0, zIndex: 0,
        pointerEvents: 'none', overflow: 'hidden',
        // WebGL yoksa/geç yüklenirse arkada duran statik zemin
        background: 'radial-gradient(120% 90% at 50% 0%, #241C5C 0%, #120E33 45%, #070616 100%)',
      }}
    >
      {/* sticky: sayfa uzasa da WebGL yüzeyi tek ekran boyunda kalır */}
      <div ref={hostRef} style={{ position: 'sticky', top: 0, width: '100%', height: '100svh' }} />
    </div>
  )
}
