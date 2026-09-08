'use client'

/**
 * Hero'nun WebGL katmanı — saf three.js (React Three Fiber yok).
 *
 * İki katman:
 *  1) Tam ekran shader düzlemi: akışkan gradient + film grain. Marka moru
 *     (#534AB7) etrafında turkuaz/macenta salınımı.
 *  2) Merkezdeki obje: vertex'i noise ile deforme edilen ikosahedron; üstüne
 *     fresnel + iridescent renk. Higgsfield'dan gelen GLB varsa (public/hero/
 *     hero-object.glb) o yüklenir ve prosedürel obje devre dışı kalır.
 *
 * Performans: DPR 1.75 ile sınırlı, hero görünmezken (IntersectionObserver) ve
 * sekme arkadayken rAF durur, prefers-reduced-motion'da tek kare çizilir.
 */

import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

const VERT_FULLSCREEN = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`

// Akışkan gradient — üç marka rengi arasında domain-warped noise.
const FRAG_BACKDROP = /* glsl */ `
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform vec2  uMouse;
  uniform float uAspect;

  // hash + value noise (ucuz, mobilde de akıcı)
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

  void main() {
    vec2 uv = vUv;
    vec2 p = vec2(uv.x * uAspect, uv.y);

    float t = uTime * 0.06;
    vec2 warp = vec2(fbm(p * 1.6 + t), fbm(p * 1.6 - t + 4.7));
    float n = fbm(p * 2.1 + warp * 1.4 + uMouse * 0.25);

    vec3 deepViolet = vec3(0.208, 0.176, 0.541);   // #352D8A
    vec3 brandViolet = vec3(0.325, 0.290, 0.717);  // #534AB7
    vec3 teal        = vec3(0.059, 0.431, 0.396);  // #0F6E65
    vec3 magenta     = vec3(0.788, 0.325, 0.612);  // #C9539C
    vec3 space       = vec3(0.027, 0.024, 0.086);  // #070616 — form bölümünün zemini

    vec3 col = mix(deepViolet, brandViolet, smoothstep(0.15, 0.75, n));
    col = mix(col, teal,    smoothstep(0.45, 0.95, fbm(p * 1.3 - t * 1.7)));
    col = mix(col, magenta, smoothstep(0.55, 1.0,  fbm(p * 1.9 + t * 1.2)) * 0.55);

    // aşağı doğru uzay moruna iniş — hero ile koyu form bölümü arasında
    // görünür bir kesik kalmasın (eskiden krem'e yıkanıyordu).
    col = mix(col, space, smoothstep(0.40, 0.0, uv.y) * 0.96);
    // üst tarafı hafif koyulaştır — beyaz başlık için kontrast
    col *= 1.0 - smoothstep(0.55, 1.0, uv.y) * 0.18;

    // merkezden dışa hafif vignette
    float d = distance(uv, vec2(0.5, 0.42));
    col *= 1.0 - smoothstep(0.35, 0.95, d) * 0.35;

    // grain — düz gradient'in "dijital" hissini kırar
    float grain = (hash(uv * 900.0 + uTime) - 0.5) * 0.045;
    gl_FragColor = vec4(col + grain, 1.0);
  }
`

const VERT_BLOB = /* glsl */ `
  precision highp float;
  uniform float uTime;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying float vNoise;

  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i  = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
              i.z + vec4(0.0, i1.z, i2.z, 1.0))
            + i.y + vec4(0.0, i1.y, i2.y, 1.0))
            + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
  }

  void main() {
    float t = uTime * 0.25;
    float n = snoise(normal * 1.05 + vec3(t, t * 0.7, t * 1.3));
    vNoise = n;

    vec3 displaced = position + normal * n * 0.2;
    vec4 mvPosition = modelViewMatrix * vec4(displaced, 1.0);

    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - (modelMatrix * vec4(displaced, 1.0)).xyz);

    gl_Position = projectionMatrix * mvPosition;
  }
`

const FRAG_BLOB = /* glsl */ `
  precision highp float;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying float vNoise;
  uniform float uTime;

  void main() {
    float fres = pow(1.0 - clamp(dot(normalize(vNormalW), normalize(vViewDir)), 0.0, 1.0), 2.4);

    vec3 violet  = vec3(0.404, 0.353, 0.902);
    vec3 teal    = vec3(0.192, 0.784, 0.702);
    vec3 magenta = vec3(0.949, 0.463, 0.776);
    vec3 cream   = vec3(1.0, 0.996, 0.988);

    float band = vNoise * 0.5 + 0.5;
    vec3 col = mix(violet, teal, smoothstep(0.25, 0.85, band + sin(uTime * 0.4) * 0.08));
    col = mix(col, magenta, smoothstep(0.6, 1.0, band) * 0.7);
    col = mix(col, cream, fres * 0.9);

    gl_FragColor = vec4(col, 0.88);
  }
`

export default function HeroCanvas() {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
    } catch {
      return // WebGL yok — CSS gradient fallback'i görünür kalır
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75))
    renderer.setSize(host.clientWidth, host.clientHeight)
    renderer.domElement.style.display = 'block'
    host.appendChild(renderer.domElement)

    // ── Katman 1: tam ekran gradient ──────────────────────────────────────
    const bgScene = new THREE.Scene()
    const bgCamera = new THREE.Camera()
    const bgUniforms = {
      uTime: { value: 0 },
      uMouse: { value: new THREE.Vector2(0, 0) },
      uAspect: { value: host.clientWidth / host.clientHeight },
    }
    const bgMaterial = new THREE.ShaderMaterial({
      vertexShader: VERT_FULLSCREEN,
      fragmentShader: FRAG_BACKDROP,
      uniforms: bgUniforms,
      depthWrite: false,
    })
    const bgGeometry = new THREE.PlaneGeometry(2, 2)
    bgScene.add(new THREE.Mesh(bgGeometry, bgMaterial))

    // ── Katman 2: merkezdeki obje + parçacıklar ───────────────────────────
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, host.clientWidth / host.clientHeight, 0.1, 100)
    camera.position.set(0, 0, 4.2)

    const blobUniforms = { uTime: { value: 0 } }
    const blobMaterial = new THREE.ShaderMaterial({
      vertexShader: VERT_BLOB,
      fragmentShader: FRAG_BLOB,
      uniforms: blobUniforms,
      transparent: true,
    })
    const blob = new THREE.Mesh(new THREE.IcosahedronGeometry(0.85, 48), blobMaterial)
    scene.add(blob)

    // Konum ekran oranına bağlı: geniş ekranda metnin sağ omzunda, dar/mobil
    // ekranda başlığın üstünde durur (yoksa kadrajın dışında kalıyor).
    let blobBaseX = 1.92
    let blobBaseY = 0.72
    function placeBlob(aspect: number) {
      const portrait = aspect < 0.9
      blobBaseX = portrait ? 0.55 : 1.92
      blobBaseY = portrait ? 1.02 : 0.72
      blob.scale.setScalar(portrait ? 0.62 : 1)
      blob.position.x = blobBaseX
    }
    placeBlob(host.clientWidth / host.clientHeight)

    // ── Üretilmiş 3D obje (varsa) ─────────────────────────────────────────
    // Varsayılan: public/hero/hero-object.glb (repoya konur, sürümlenir).
    // NEXT_PUBLIC_HERO_MODEL_URL verilirse oradan yüklenir — modeli repoya
    // koymadan denemek için. Dosya yoksa sahne prosedürel objeyle çalışır;
    // 404 gürültüsü olmasın diye önce HEAD ile varlık kontrol edilir.
    const MODEL_URL = process.env.NEXT_PUBLIC_HERO_MODEL_URL || '/hero/hero-object.glb'
    let heroObject: THREE.Object3D | null = null
    let cancelled = false

    // GLB'ye uygulanacak iridesan cam materyali (ışık gerektirmez)
    const heroObjectMaterial = new THREE.ShaderMaterial({
      vertexShader: /* glsl */ `
        varying vec3 vNormalW;
        varying vec3 vViewDir;
        void main() {
          vNormalW = normalize(mat3(modelMatrix) * normal);
          vec4 world = modelMatrix * vec4(position, 1.0);
          vViewDir = normalize(cameraPosition - world.xyz);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        precision mediump float;
        varying vec3 vNormalW;
        varying vec3 vViewDir;
        uniform float uTime;
        void main() {
          vec3 N = normalize(vNormalW);
          vec3 V = normalize(vViewDir);
          float fres = pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 2.2);
          float ang = dot(N, V);
          vec3 irid = 0.5 + 0.5 * cos(6.28318 * (vec3(0.0, 0.33, 0.67) + ang * 2.0 + uTime * 0.05));
          vec3 col = mix(vec3(0.42, 0.33, 0.90), vec3(0.16, 0.85, 0.78), N.y * 0.5 + 0.5);
          col = mix(col, irid, 0.42);
          col = mix(col, min(col * 2.2 + 0.2, vec3(1.0)), fres * 0.75);
          gl_FragColor = vec4(col, 0.90);
        }
      `,
      uniforms: { uTime: { value: 0 } },
      transparent: true,
    })

    fetch(MODEL_URL, { method: 'HEAD' })
      .then(res => {
        if (!res.ok || cancelled) return
        new GLTFLoader().load(MODEL_URL, gltf => {
          if (cancelled) return
          heroObject = gltf.scene

          // modeli birim küreye normalize et — üretici ölçeği rastgele olabilir
          const box = new THREE.Box3().setFromObject(heroObject)
          const size = box.getSize(new THREE.Vector3())
          const center = box.getCenter(new THREE.Vector3())
          const maxAxis = Math.max(size.x, size.y, size.z) || 1
          heroObject.position.sub(center)

          // Üretilen mesh dokusuz geliyor; kendi materyalimiz olmadan gri
          // plastik gibi duruyordu. Sahnenin iridesan cam dilini uyguluyoruz.
          heroObject.traverse(node => {
            const mesh = node as THREE.Mesh
            if (!mesh.isMesh) return
            const previous = mesh.material
            for (const m of Array.isArray(previous) ? previous : [previous]) m?.dispose()
            mesh.material = heroObjectMaterial
          })

          const holder = new THREE.Group()
          holder.add(heroObject)
          holder.scale.setScalar(1.15 / maxAxis)
          scene.add(holder)
          heroObject = holder

          // GLB geldiyse blob arkada yumuşak bir hale olarak kalsın
          blob.scale.multiplyScalar(0.62)
          blob.position.z -= 0.9
        })
      })
      .catch(() => { /* asset yok — prosedürel sahne yeterli */ })

    // ince parçacık alanı — derinlik hissi
    const count = 420
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const r = 2.6 + Math.random() * 2.6
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6
      positions[i * 3 + 2] = r * Math.cos(phi)
    }
    const dustGeometry = new THREE.BufferGeometry()
    dustGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    // PointsMaterial varsayılanı kare piksel çizer; radyal alfa dokusuyla yuvarlatıyoruz
    const spriteCanvas = document.createElement('canvas')
    spriteCanvas.width = spriteCanvas.height = 64
    const sctx = spriteCanvas.getContext('2d')!
    const grad = sctx.createRadialGradient(32, 32, 0, 32, 32, 32)
    grad.addColorStop(0, 'rgba(255,255,255,1)')
    grad.addColorStop(0.45, 'rgba(255,255,255,0.55)')
    grad.addColorStop(1, 'rgba(255,255,255,0)')
    sctx.fillStyle = grad
    sctx.fillRect(0, 0, 64, 64)
    const dustTexture = new THREE.CanvasTexture(spriteCanvas)

    const dustMaterial = new THREE.PointsMaterial({
      size: 0.055,
      map: dustTexture,
      color: 0xffffff,
      transparent: true,
      opacity: 0.6,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    const dust = new THREE.Points(dustGeometry, dustMaterial)
    scene.add(dust)

    // ── Etkileşim ─────────────────────────────────────────────────────────
    const pointer = { x: 0, y: 0 }
    const target = { x: 0, y: 0 }
    function onPointerMove(e: PointerEvent) {
      const rect = host!.getBoundingClientRect()
      target.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
      target.y = -(((e.clientY - rect.top) / rect.height) * 2 - 1)
    }
    window.addEventListener('pointermove', onPointerMove, { passive: true })

    function resize() {
      if (!host) return
      const w = host.clientWidth
      const h = host.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      bgUniforms.uAspect.value = w / h
      placeBlob(w / h)
    }
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(host)

    // Hero ekranda değilken çizme — pil ve CPU tasarrufu
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
      bgUniforms.uTime.value = t
      blobUniforms.uTime.value = t

      pointer.x += (target.x - pointer.x) * 0.045
      pointer.y += (target.y - pointer.y) * 0.045
      bgUniforms.uMouse.value.set(pointer.x, pointer.y)

      blob.rotation.y = t * 0.16 + pointer.x * 0.35
      blob.rotation.x = Math.sin(t * 0.22) * 0.14 + pointer.y * 0.22
      blob.position.y = blobBaseY + Math.sin(t * 0.6) * 0.07

      if (heroObject) {
        heroObjectMaterial.uniforms.uTime.value = t
        heroObject.position.set(blobBaseX, blobBaseY + Math.sin(t * 0.55) * 0.09, -0.4)
        heroObject.rotation.y = t * 0.28 + pointer.x * 0.4
        heroObject.rotation.z = Math.sin(t * 0.4) * 0.09
      }

      dust.rotation.y = t * 0.03
      camera.position.x = pointer.x * 0.35
      camera.position.y = pointer.y * 0.22
      camera.lookAt(0, 0, 0)

      renderer.autoClear = true
      renderer.render(bgScene, bgCamera)
      renderer.autoClear = false
      renderer.render(scene, camera)
      renderer.autoClear = true
    }

    function loop() {
      raf = requestAnimationFrame(loop)
      if (!visible || document.hidden) return
      draw()
    }

    if (reduced) {
      draw() // tek kare: hareket yok ama sahne görünür
    } else {
      loop()
    }

    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      if (heroObject) {
        // Materyal tüm mesh'lerde ortak — geometrileri burada, materyali
        // aşağıda bir kez bırakıyoruz.
        heroObject.traverse(node => {
          const mesh = node as THREE.Mesh
          if (mesh.isMesh) mesh.geometry?.dispose()
        })
        scene.remove(heroObject)
      }
      heroObjectMaterial.dispose()
      io.disconnect()
      resizeObserver.disconnect()
      window.removeEventListener('pointermove', onPointerMove)
      bgGeometry.dispose()
      bgMaterial.dispose()
      blob.geometry.dispose()
      blobMaterial.dispose()
      dustGeometry.dispose()
      dustMaterial.dispose()
      dustTexture.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement)
    }
  }, [])

  return (
    <div
      ref={hostRef}
      aria-hidden="true"
      style={{
        position: 'absolute', inset: 0, zIndex: 0,
        // WebGL yoksa/geç yüklenirse arkada duran statik gradient
        background: 'linear-gradient(165deg, #352D8A 0%, #534AB7 34%, #2B2270 68%, #070616 100%)',
      }}
    />
  )
}
