/**
 * The 3D backdrop that lives behind the entire storytelling section.
 *
 * Design goals:
 *   • Match the editorial dark-mode aesthetic of patronus.ai / scale.com:
 *     a single hero object that morphs / re-positions as the user scrolls
 *     through the guide steps.
 *   • Zero loading state — we render only procedural meshes (no GLTF) so
 *     the very first paint is interactive.
 *   • <60 KB JS gzipped on top of the existing three.js bundle.
 *
 * It exposes a controlled `step` prop (0..N) that the parent scroll
 * controller updates from a scroll-progress signal. Each step picks a
 * different camera target + rotation so the geometry "tells a story" of
 * the candidate ranking pipeline:
 *
 *   step 0 → wireframe sphere (the noisy 100k candidate pool)
 *   step 1 → re-arranges into a grid plane (schema validation)
 *   step 2 → torus knot (NLP / hybrid retrieval entanglement)
 *   step 3 → tight icosahedron (scored & ranked)
 *   step 4 → glow ring (final shortlist delivered)
 */

import React, { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame, type ThreeElements } from "@react-three/fiber";
import { Float, OrbitControls, Sparkles } from "@react-three/drei";
import * as THREE from "three";

interface Props {
  step: number;
  /** Pointer-driven parallax: x and y are in [-1, 1] */
  parallax?: { x: number; y: number };
}

export const Scene3D: React.FC<Props> = ({ step, parallax }) => {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 45 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
    >
      <color attach="background" args={["#000000"]} />
      <fog attach="fog" args={["#000000", 8, 18]} />
      <ambientLight intensity={0.35} />
      <directionalLight position={[3, 4, 5]} intensity={1.1} color="#ffffff" />
      <directionalLight position={[-4, -2, -3]} intensity={0.5} color="#7a8fc7" />
      <Suspense fallback={null}>
        <StoryObject step={step} parallax={parallax} />
        <Sparkles
          count={140}
          scale={[14, 8, 6]}
          size={2}
          speed={0.3}
          color="#fafafa"
          opacity={0.45}
        />
      </Suspense>
      <OrbitControls enabled={false} />
    </Canvas>
  );
};

// ───────────────────────── The hero object ────────────────────────────────

const STEP_CONFIG = [
  // 0 — Pool of 100k candidates: noisy wireframe sphere.
  {
    geometry: "sphere" as const,
    color: "#9aa9d8",
    scale: 1.4,
    rotation: 0.0025,
    wire: true,
    distort: 0.35,
  },
  // 1 — Schema validation: ordered grid plane.
  {
    geometry: "grid" as const,
    color: "#c1d6c2",
    scale: 1.6,
    rotation: 0.0008,
    wire: true,
    distort: 0.05,
  },
  // 2 — Hybrid retrieval (BM25 + TF-IDF + behavioural): torus knot.
  {
    geometry: "torusKnot" as const,
    color: "#dac3f0",
    scale: 1.1,
    rotation: 0.004,
    wire: false,
    distort: 0.18,
  },
  // 3 — Scoring + reasoning: tight icosahedron.
  {
    geometry: "icosa" as const,
    color: "#fafafa",
    scale: 1.0,
    rotation: 0.006,
    wire: false,
    distort: 0.0,
  },
  // 4 — Final shortlist: bright halo ring.
  {
    geometry: "torus" as const,
    color: "#fafafa",
    scale: 1.6,
    rotation: 0.002,
    wire: false,
    distort: 0.0,
  },
];

const StoryObject: React.FC<{ step: number; parallax?: { x: number; y: number } }> = ({
  step,
  parallax,
}) => {
  const groupRef = useRef<THREE.Group>(null!);
  const meshRef = useRef<THREE.Mesh>(null!);

  const idx = Math.max(0, Math.min(STEP_CONFIG.length - 1, Math.floor(step)));
  const config = STEP_CONFIG[idx];

  // Per-frame interpolation: rotate continuously, smooth-lerp scale +
  // parallax-driven tilt towards the requested step.
  useFrame((_, delta) => {
    if (!groupRef.current || !meshRef.current) return;
    meshRef.current.rotation.y += config.rotation * 60 * delta;
    meshRef.current.rotation.x += config.rotation * 30 * delta;

    const targetScale = config.scale;
    const cur = meshRef.current.scale.x;
    const next = cur + (targetScale - cur) * Math.min(1, delta * 4);
    meshRef.current.scale.setScalar(next);

    if (parallax) {
      const tx = parallax.x * 0.35;
      const ty = -parallax.y * 0.25;
      groupRef.current.rotation.y +=
        (tx - groupRef.current.rotation.y) * Math.min(1, delta * 2.5);
      groupRef.current.rotation.x +=
        (ty - groupRef.current.rotation.x) * Math.min(1, delta * 2.5);
    }
  });

  const geometry = useMemo(() => buildGeometry(config.geometry), [config.geometry]);
  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(config.color),
        roughness: 0.35,
        metalness: 0.55,
        wireframe: config.wire,
        emissive: new THREE.Color(config.color).multiplyScalar(0.08),
      }),
    [config.color, config.wire]
  );

  return (
    <group ref={groupRef}>
      <Float speed={1.2} rotationIntensity={0.4} floatIntensity={0.6}>
        <mesh ref={meshRef} geometry={geometry} material={material} castShadow receiveShadow />
      </Float>
    </group>
  );
};

function buildGeometry(kind: string): THREE.BufferGeometry {
  switch (kind) {
    case "sphere":
      return new THREE.IcosahedronGeometry(1.2, 6);
    case "grid":
      return new THREE.TorusGeometry(1.2, 0.04, 4, 80);
    case "torusKnot":
      return new THREE.TorusKnotGeometry(1.0, 0.32, 220, 32);
    case "icosa":
      return new THREE.IcosahedronGeometry(1.1, 1);
    case "torus":
      return new THREE.TorusGeometry(1.3, 0.07, 24, 96);
    default:
      return new THREE.SphereGeometry(1, 32, 32);
  }
}

export default Scene3D;
