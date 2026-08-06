/**
 * The Three.js half of the landing bean.
 *
 * Kept in its own module so it can be loaded on demand. Three.js is ~950 kB
 * of JavaScript to parse — trivial on a laptop, but the single biggest cost on
 * a phone, where it delayed first paint by seconds. `BeanScene` decides at
 * runtime whether a device should pay for it; anything else gets the CSS bean.
 */
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'

import type { Phase } from './BeanScene'

const BEAN_SCALE = new THREE.Vector3(1, 1.32, 0.74)

/* ------------------------------------------------------------- bean halves */

function BeanHalf({
  side,
  phase,
  spin,
}: {
  side: 1 | -1
  phase: Phase
  spin: React.MutableRefObject<number>
}) {
  const mesh = useRef<THREE.Mesh>(null)
  const progress = useRef(0)

  // Half-sphere: phiLength = PI carves the bean in two along the crease.
  const geometry = useMemo(() => {
    const g = new THREE.SphereGeometry(1, 72, 52, side === 1 ? 0 : Math.PI, Math.PI)
    g.computeVertexNormals()
    return g
  }, [side])

  useEffect(() => () => geometry.dispose(), [geometry])

  useFrame((_, delta) => {
    if (!mesh.current) return

    const target = phase === 'idle' ? 0 : 1
    progress.current += (target - progress.current) * Math.min(1, delta * 2.6)
    const p = progress.current

    // Ease-out so the split snaps open then settles.
    const eased = 1 - Math.pow(1 - p, 3)

    mesh.current.position.x = side * eased * 1.5
    mesh.current.position.z = eased * -0.35
    mesh.current.rotation.z = side * eased * 0.55
    mesh.current.rotation.y = spin.current + side * eased * 0.4
    mesh.current.scale.set(
      BEAN_SCALE.x * (1 - eased * 0.06),
      BEAN_SCALE.y * (1 - eased * 0.06),
      BEAN_SCALE.z * (1 - eased * 0.06),
    )
  })

  return (
    <mesh ref={mesh} geometry={geometry} castShadow receiveShadow>
      <meshPhysicalMaterial
        color="#43291a"
        roughness={0.52}
        metalness={0.12}
        clearcoat={0.55}
        clearcoatRoughness={0.35}
        sheen={0.4}
        sheenColor="#c68b59"
        side={THREE.DoubleSide}
      />
    </mesh>
  )
}

/**
 * The crease down the middle of the bean.
 *
 * Without this the two halves sit flush and the silhouette reads as a plain
 * ellipsoid, not a coffee bean. A thin dark tube along the seam — bowed
 * slightly, the way a real bean's fissure runs — gives it the identity.
 */
function Crease({ phase }: { phase: Phase }) {
  const group = useRef<THREE.Group>(null)
  const progress = useRef(0)

  /** Trace the seam across the ellipsoid surface so the ends never float free. */
  const buildCurve = (side: 1 | -1) => {
    const points: THREE.Vector3[] = []
    const STEPS = 30
    for (let i = 0; i <= STEPS; i++) {
      // Stop just short of the poles, where the surface pinches to nothing.
      const t = -0.94 + (i / STEPS) * 1.88
      const y = t * BEAN_SCALE.y
      const shrink = Math.sqrt(Math.max(0, 1 - t * t))
      // A gentle S-wave, the way a real bean's fissure meanders.
      const x = Math.sin(t * Math.PI * 1.1) * 0.075 * shrink
      const z = side * (BEAN_SCALE.z * shrink + 0.015)
      points.push(new THREE.Vector3(x, y, z))
    }
    return new THREE.CatmullRomCurve3(points)
  }

  const geometries = useMemo(() => {
    const make = (side: 1 | -1) =>
      new THREE.TubeGeometry(buildCurve(side), 72, 0.055, 10, false)
    return [make(1), make(-1)]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => () => geometries.forEach((g) => g.dispose()), [geometries])

  useFrame((_, delta) => {
    if (!group.current) return
    const target = phase === 'idle' ? 0 : 1
    progress.current += (target - progress.current) * Math.min(1, delta * 2.6)
    // The crease is exactly where the bean splits, so it retreats as it opens.
    const p = progress.current
    group.current.scale.set(1 - p, 1, 1 - p)
    group.current.visible = p < 0.92
  })

  return (
    <group ref={group}>
      {geometries.map((g, i) => (
        <mesh key={i} geometry={g}>
          <meshStandardMaterial color="#170C05" roughness={0.98} metalness={0} />
        </mesh>
      ))}
    </group>
  )
}

/** The lighter roasted interior, revealed as the halves separate. */
function BeanCore({ phase }: { phase: Phase }) {
  const mesh = useRef<THREE.Mesh>(null)
  const mat = useRef<THREE.MeshStandardMaterial>(null)

  useFrame((state, delta) => {
    if (!mesh.current || !mat.current) return
    const target = phase === 'idle' ? 0 : 1
    const next = THREE.MathUtils.damp(mat.current.opacity, target * 0.85, 2.4, delta)
    mat.current.opacity = next
    const t = state.clock.elapsedTime
    // Kept small — it is a glimpse of the roasted interior, not a light source.
    mesh.current.scale.setScalar(0.42 + Math.sin(t * 2) * 0.015 + next * 0.08)
  })

  return (
    <mesh ref={mesh}>
      <sphereGeometry args={[1, 32, 24]} />
      <meshStandardMaterial
        ref={mat}
        color="#d9a05b"
        emissive="#c68b59"
        emissiveIntensity={1.6}
        transparent
        opacity={0}
      />
    </mesh>
  )
}

/* ------------------------------------------------------- smoke / aroma */

function Aroma({ phase, count = 320 }: { phase: Phase; count?: number }) {
  const points = useRef<THREE.Points>(null)

  const { positions, speeds, offsets } = useMemo(() => {
    const positions = new Float32Array(count * 3)
    const speeds = new Float32Array(count)
    const offsets = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2
      const radius = 0.25 + Math.random() * 0.55
      positions[i * 3] = Math.cos(angle) * radius
      positions[i * 3 + 1] = Math.random() * 2.4 - 0.6
      positions[i * 3 + 2] = Math.sin(angle) * radius
      speeds[i] = 0.14 + Math.random() * 0.3
      offsets[i] = Math.random() * Math.PI * 2
    }
    return { positions, speeds, offsets }
  }, [count])

  useFrame((state, delta) => {
    if (!points.current) return
    const attr = points.current.geometry.attributes.position as THREE.BufferAttribute
    const arr = attr.array as Float32Array
    const t = state.clock.elapsedTime
    // After the crack, aroma bursts outward instead of drifting straight up.
    const burst = phase === 'idle' ? 1 : 2.5

    for (let i = 0; i < count; i++) {
      const iy = i * 3 + 1
      arr[iy] += speeds[i] * delta * burst
      arr[i * 3] += Math.sin(t * 0.7 + offsets[i]) * delta * 0.12 * burst
      arr[i * 3 + 2] += Math.cos(t * 0.6 + offsets[i]) * delta * 0.12 * burst
      if (arr[iy] > 2.4) {
        const angle = Math.random() * Math.PI * 2
        const radius = 0.2 + Math.random() * 0.5
        arr[i * 3] = Math.cos(angle) * radius
        arr[iy] = -0.8
        arr[i * 3 + 2] = Math.sin(angle) * radius
      }
    }
    attr.needsUpdate = true
  })

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        color="#e8d5bc"
        transparent
        opacity={0.34}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

/** Roasted fragments thrown outward at the moment of the crack. */
function Fragments({ phase, count = 26 }: { phase: Phase; count?: number }) {
  const group = useRef<THREE.Group>(null)
  const life = useRef(0)

  const seeds = useMemo(
    () =>
      Array.from({ length: count }, () => ({
        dir: new THREE.Vector3(
          (Math.random() - 0.5) * 2,
          (Math.random() - 0.3) * 1.6,
          (Math.random() - 0.5) * 2,
        ).normalize(),
        speed: 1.4 + Math.random() * 2.4,
        spin: (Math.random() - 0.5) * 4,
        size: 0.05 + Math.random() * 0.08,
      })),
    [count],
  )

  useFrame((_, delta) => {
    if (!group.current) return
    if (phase === 'idle') {
      life.current = 0
      group.current.visible = false
      return
    }
    group.current.visible = true
    life.current = Math.min(life.current + delta, 3)
    const t = life.current

    group.current.children.forEach((child, i) => {
      const s = seeds[i]
      child.position.set(
        s.dir.x * s.speed * t,
        s.dir.y * s.speed * t - 0.9 * t * t, // gravity
        s.dir.z * s.speed * t,
      )
      child.rotation.x += s.spin * delta
      child.rotation.y += s.spin * delta
      const mat = (child as THREE.Mesh).material as THREE.MeshStandardMaterial
      mat.opacity = Math.max(0, 1 - t / 2.4)
    })
  })

  return (
    <group ref={group} visible={false}>
      {seeds.map((s, i) => (
        <mesh key={i}>
          <dodecahedronGeometry args={[s.size, 0]} />
          <meshStandardMaterial color="#5a3a24" roughness={0.85} transparent opacity={1} />
        </mesh>
      ))}
    </group>
  )
}

/* ---------------------------------------------------------------- scene */

function Scene({ phase, onCrack }: { phase: Phase; onCrack: () => void }) {
  const group = useRef<THREE.Group>(null)
  const spin = useRef(0)
  const dragState = useRef({ active: false, startX: 0, travelled: 0 })
  const { gl } = useThree()

  useFrame((state, delta) => {
    if (!group.current) return
    if (phase === 'idle' && !dragState.current.active) {
      spin.current += delta * 0.42
    }
    group.current.rotation.y = spin.current
    // Gentle bob + slight lean toward the pointer for parallax.
    const t = state.clock.elapsedTime
    group.current.position.y = Math.sin(t * 0.9) * 0.06
    group.current.rotation.x = THREE.MathUtils.damp(
      group.current.rotation.x,
      state.pointer.y * 0.22,
      2,
      delta,
    )
  })

  useEffect(() => {
    const el = gl.domElement
    const down = (e: PointerEvent) => {
      dragState.current = { active: true, startX: e.clientX, travelled: 0 }
    }
    const move = (e: PointerEvent) => {
      if (!dragState.current.active) return
      const dx = e.clientX - dragState.current.startX
      dragState.current.travelled = Math.abs(dx)
      spin.current += dx * 0.006
      dragState.current.startX = e.clientX
      // A decisive drag cracks the bean, same as a click.
      if (dragState.current.travelled > 90) {
        dragState.current.active = false
        onCrack()
      }
    }
    const up = () => {
      dragState.current.active = false
    }
    el.addEventListener('pointerdown', down)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      el.removeEventListener('pointerdown', down)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [gl, onCrack])

  return (
    <>
      <ambientLight intensity={0.5} color="#f5e6d3" />
      <directionalLight position={[4, 6, 5]} intensity={2.1} color="#ffd9a0" castShadow />
      <directionalLight position={[-5, -2, -4]} intensity={0.7} color="#c68b59" />
      <pointLight position={[0, 0, 2.6]} intensity={2.4} color="#d9a05b" distance={9} />

      <group ref={group}>
        <BeanHalf side={1} phase={phase} spin={spin} />
        <BeanHalf side={-1} phase={phase} spin={spin} />
        <Crease phase={phase} />
        <BeanCore phase={phase} />
        <Fragments phase={phase} />
      </group>

      <Aroma phase={phase} />
    </>
  )
}

/* ------------------------------------------------------------- fallback */

/** Default export so `React.lazy` can pick it up. */
export default function Bean3D({
  phase,
  onCrack,
}: {
  phase: Phase
  onCrack: () => void
}) {
  return (
    <Canvas
      dpr={[1, 2]}
      // Pulled back and raised so the bean sits in the upper half of the frame,
      // leaving the lower third clear for the caption and CTA.
      camera={{ position: [0, 0.55, 6.6], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      onCreated={({ gl }) => {
        gl.domElement.style.cursor = 'grab'
      }}
      onClick={onCrack}
      style={{ touchAction: 'none' }}
    >
      <Scene phase={phase} onCrack={onCrack} />
    </Canvas>
  )
}
