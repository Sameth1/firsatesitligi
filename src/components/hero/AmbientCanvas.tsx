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
    const material = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms })
    scene.add(new THREE.Mesh(geometry, material))

    function resize() {
      if (!host) return
      renderer.setSize(host.clientWidth, host.clientHeight)
      uniforms.uAspect.value = host.clientWidth / host.clientHeight
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
      uniforms.uTime.value = clock.getElapsedTime()
      uniforms.uScroll.value += (scrollTargetValue - uniforms.uScroll.value) * 0.06
      renderer.render(scene, camera)
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
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement)
    }
  }, [])

  return (
    <div
      ref={hostRef}
      aria-hidden="true"
      style={{
        position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none',
        background: 'linear-gradient(180deg, #fbfbfe 0%, #f6f5fb 45%, #f5f3fa 100%)',
      }}
    />
  )
}
