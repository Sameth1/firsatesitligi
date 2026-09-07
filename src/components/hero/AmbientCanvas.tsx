'use client'

/**
 * Form ve sonuç ekranlarının arka planı — hero'nun hafif kardeşi.
 *
 * Hero'da 3B obje + parçacık + gradient var; burada yalnız tek bir fragment
 * shader çalışır (geometri, ışık, model yok). Amaç: sayfa okunurken CPU/GPU'yu
 * meşgul etmeden zeminin "canlı" durması. Açık tema — içerik kartları beyaz
 * olduğu için zemin krem/lavanta tonlarında kalır.
 */

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

const VERT = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, 0.0, 1.0);
  }
`

const FRAG = /* glsl */ `
  precision mediump float;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uAspect;
  uniform float uScroll;

  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
  }
  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; }
    return v;
  }

  void main() {
    vec2 p = vec2(vUv.x * uAspect, vUv.y + uScroll * 0.12);
    float t = uTime * 0.035;

    float n = fbm(p * 1.35 + vec2(t, -t * 0.8));

    vec3 cream    = vec3(0.984, 0.984, 0.996);
    vec3 lavender = vec3(0.925, 0.918, 0.980);
    vec3 mint     = vec3(0.898, 0.965, 0.953);
    vec3 blush    = vec3(0.976, 0.933, 0.965);

    vec3 col = mix(cream, lavender, smoothstep(0.28, 0.85, n));
    col = mix(col, mint,  smoothstep(0.5, 1.0, fbm(p * 1.05 - t * 1.3)) * 0.75);
    col = mix(col, blush, smoothstep(0.6, 1.0, fbm(p * 1.6 + t * 0.9)) * 0.45);

    // ince grain — bant oluşumunu kırar
    col += (hash(vUv * 800.0 + uTime) - 0.5) * 0.018;

    gl_FragColor = vec4(col, 1.0);
  }
`

export default function AmbientCanvas() {
  const hostRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false })
    } catch {
      return // WebGL yok — CSS gradient fallback kalır
    }

    // Arka plan dokusu için yüksek DPR gereksiz; 1.25 tavanı pil dostu
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25))
    renderer.setSize(host.clientWidth, host.clientHeight)
    renderer.domElement.style.display = 'block'
    host.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.Camera()
    const uniforms = {
      uTime: { value: 0 },
      uAspect: { value: host.clientWidth / host.clientHeight },
      uScroll: { value: 0 },
    }
    const geometry = new THREE.PlaneGeometry(2, 2)
    const material = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, uniforms,
      depthWrite: false, depthTest: false,
    })
    scene.add(new THREE.Mesh(geometry, material))

    // ── 3B katman ─────────────────────────────────────────────────────────
    // Gradient'in üstünde yavaşça süzülen yarı saydam düşük-poli objeler.
    // Işık yok: renk fresnel + normal'den türetiliyor (ucuz, tutarlı).
    const objScene = new THREE.Scene()
    const objCamera = new THREE.PerspectiveCamera(50, host.clientWidth / host.clientHeight, 0.1, 60)
    objCamera.position.z = 14

    const SHAPE_FRAG = `
      precision mediump float;
      varying vec3 vNormalW;
      varying vec3 vViewDir;
      uniform vec3 uColorA;
      uniform vec3 uColorB;
      void main() {
        float fres = pow(1.0 - clamp(dot(normalize(vNormalW), normalize(vViewDir)), 0.0, 1.0), 2.0);
        float band = normalize(vNormalW).y * 0.5 + 0.5;
        vec3 col = mix(uColorA, uColorB, band);
        col = mix(col, vec3(1.0), fres * 0.42);
        gl_FragColor = vec4(col, 0.26 + fres * 0.4);
      }
    `
    const SHAPE_VERT = `
      precision mediump float;
      varying vec3 vNormalW;
      varying vec3 vViewDir;
      void main() {
        vNormalW = normalize(mat3(modelMatrix) * normal);
        vec4 world = modelMatrix * vec4(position, 1.0);
        vViewDir = normalize(cameraPosition - world.xyz);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `

    const palette: [number[], number[]][] = [
      [[0.294, 0.255, 0.710], [0.090, 0.659, 0.596]],
      [[0.090, 0.659, 0.596], [0.788, 0.325, 0.612]],
      [[0.788, 0.325, 0.612], [0.294, 0.255, 0.710]],
    ]

    const shapeGeometries = [
      new THREE.IcosahedronGeometry(1, 1),
      new THREE.TorusGeometry(0.8, 0.3, 12, 32),
      new THREE.OctahedronGeometry(1, 0),
      new THREE.DodecahedronGeometry(1, 0),
    ]
    const shapeMaterials: THREE.ShaderMaterial[] = []
    const shapes: { mesh: THREE.Mesh; spin: THREE.Vector3; float: number; baseY: number }[] = []

    // Kenarlarda duran, içerik sütununu boğmayan aksanlar
    const layout = [
      { x: -7.6, y: 3.4, z: -1, s: 1.25 },
      { x: 7.8,  y: 1.6, z: 0,  s: 1.0 },
      { x: -6.8, y: -3.4, z: -2, s: 1.4 },
      { x: 7.2,  y: -4.0, z: -1, s: 1.15 },
      { x: 5.4,  y: 6.4, z: -4, s: 1.4 },
      { x: -2.2, y: -6.2, z: -3, s: 1.3 },
    ]

    layout.forEach((pos, i) => {
      const [a, b] = palette[i % palette.length]
      const mat = new THREE.ShaderMaterial({
        vertexShader: SHAPE_VERT,
        fragmentShader: SHAPE_FRAG,
        uniforms: {
          uColorA: { value: new THREE.Vector3(...a) },
          uColorB: { value: new THREE.Vector3(...b) },
        },
        transparent: true,
        depthWrite: false,
      })
      shapeMaterials.push(mat)
      const mesh = new THREE.Mesh(shapeGeometries[i % shapeGeometries.length], mat)
      mesh.position.set(pos.x, pos.y, pos.z)
      mesh.scale.setScalar(pos.s)
      objScene.add(mesh)
      shapes.push({
        mesh,
        spin: new THREE.Vector3(0.05 + i * 0.012, 0.08 + i * 0.01, 0.03),
        float: 0.5 + i * 0.17,
        baseY: pos.y,
      })
    })

    const pointer = { x: 0, y: 0 }
    const pointerTarget = { x: 0, y: 0 }
    function onPointerMove(e: PointerEvent) {
      pointerTarget.x = (e.clientX / window.innerWidth) * 2 - 1
      pointerTarget.y = -((e.clientY / window.innerHeight) * 2 - 1)
    }
    window.addEventListener('pointermove', onPointerMove, { passive: true })

    function resize() {
      if (!host) return
      renderer.setSize(host.clientWidth, host.clientHeight)
      uniforms.uAspect.value = host.clientWidth / host.clientHeight
      objCamera.aspect = host.clientWidth / host.clientHeight
      objCamera.updateProjectionMatrix()
    }
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(host)

    let scrollTargetValue = 0
    function onScroll() {
      const max = document.body.scrollHeight - window.innerHeight
      scrollTargetValue = max > 0 ? window.scrollY / max : 0
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()

    const clock = new THREE.Clock()
    let raf = 0

    function draw() {
      const t = clock.getElapsedTime()
      uniforms.uTime.value = t
      uniforms.uScroll.value += (scrollTargetValue - uniforms.uScroll.value) * 0.06

      pointer.x += (pointerTarget.x - pointer.x) * 0.04
      pointer.y += (pointerTarget.y - pointer.y) * 0.04

      for (const s of shapes) {
        s.mesh.rotation.x += s.spin.x * 0.01
        s.mesh.rotation.y += s.spin.y * 0.01
        s.mesh.position.y = s.baseY + Math.sin(t * 0.35 * s.float) * 0.45
      }
      objCamera.position.x = pointer.x * 0.9
      objCamera.position.y = pointer.y * 0.6 - uniforms.uScroll.value * 2.4
      objCamera.lookAt(0, -uniforms.uScroll.value * 2.4, 0)

      renderer.autoClear = true
      renderer.render(scene, camera)
      renderer.autoClear = false
      renderer.clearDepth()          // gradient katmanının derinliğini sıfırla
      renderer.render(objScene, objCamera)
      renderer.autoClear = true
    }

    function loop() {
      raf = requestAnimationFrame(loop)
      if (document.hidden) return
      draw()
    }

    if (reduced) draw()
    else loop()

    return () => {
      cancelAnimationFrame(raf)
      resizeObserver.disconnect()
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('pointermove', onPointerMove)
      geometry.dispose()
      material.dispose()
      shapeGeometries.forEach(g => g.dispose())
      shapeMaterials.forEach(m => m.dispose())
      renderer.dispose()
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement)
    }
  }, [])

  return (
    <div
      ref={hostRef}
      aria-hidden="true"
      style={{
        // absolute: yalnız kendi <main>'ini kaplar. fixed olsaydı DOM'da
        // sonra geldiği için hero bölümünün üstünü örterdi.
        position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none',
        background: 'linear-gradient(180deg, #fbfbfe 0%, #f6f5fb 45%, #f5f3fa 100%)',
      }}
    />
  )
}
