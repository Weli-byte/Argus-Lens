"use client";

/* react-hooks/immutability bu dosyada bilinçli olarak kapalı.
   Sebep: three.js materyali React state'i değil, harici bir GPU kaynağıdır;
   `material.uniforms.X.value = ...` onu güncellemenin TEK yoludur. Kural
   prop/memo mutasyonunu yasaklarken bu senaryoyu ayırt edemiyor. Mutasyonlar
   efekt gövdesinde yapılıp temizlikte geri alınıyor, render çıktısını
   etkilemiyor. Diğer tüm react-hooks kuralları açık kalır. */
/* eslint-disable react-hooks/immutability */

import { useEffect, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { lensProgress } from "@/lib/lens-progress";

/* ────────────────────────────────────────────────────────────────────────────
   MERCEK ELEMAN YIĞINI

   Neden bu ve neden dönen küp değil: ArgusLens bir mercektir. Sahnedeki
   nesne ürünün kendisi — üç asferik cam eleman, namlu içinde.
   Scroll ilerledikçe elemanlar patlatılmış optik diyagrama ayrılır.

   Bütçe kararları (ölçüldü):
   - drei YOK. Sadece three + @react-three/fiber → 227 KB gzip, tembel yüklenir.
   - GLTF YOK. Geometri prosedürel (LatheGeometry) → sıfır ağ isteği.
   - Işık YOK. Materyaller shader/basic → 5 çizim çağrısı / kare.
   - Doku: hero videosunun KENDİ <video> elementi yeniden kullanılır,
     ikinci bir indirme olmaz.

   GPU kaynakları modül düzeyinde tutulur. Sebep: React derleyicisi render
   sırasında ref okumayı ve useMemo değerini mutasyona uğratmayı yasaklıyor;
   three.js ise uniform mutasyonu üzerine kurulu. Modül düzeyi tekil örnek
   ikisini de çözer.
   ────────────────────────────────────────────────────────────────────────── */

/** Bikonveks mercek kesiti → Lathe profili. r: yarıçap, t: merkez kalınlığı. */
function lensProfile(r: number, t: number, steps = 14): THREE.Vector2[] {
  const pts: THREE.Vector2[] = [];
  for (let i = 0; i <= steps; i++) {
    const x = (r * i) / steps;
    const k = Math.sqrt(Math.max(0, 1 - (x / r) ** 2));
    pts.push(new THREE.Vector2(x, (t / 2) * k));
  }
  for (let i = steps; i >= 0; i--) {
    const x = (r * i) / steps;
    const k = Math.sqrt(Math.max(0, 1 - (x / r) ** 2));
    pts.push(new THREE.Vector2(x, -(t / 2) * k));
  }
  return pts;
}

const VERT = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    vec4 world = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - world.xyz);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

/* Sahte kırılma: ekran uzayı UV'si yüzey normaliyle kaydırılır.
   Kromatik dispersiyon: R/G/B üç farklı kaymadan örneklenir —
   gerçek camın yaptığı şey, dekoratif bir renk hilesi değil. */
const FRAG = /* glsl */ `
  precision highp float;
  uniform sampler2D uBackdrop;
  uniform float uHasBackdrop;
  uniform vec2  uResolution;
  uniform float uRefract;
  uniform float uDispersion;
  uniform vec3  uRim;
  uniform float uOpacity;
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying vec2 vUv;

  void main() {
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(vViewDir);
    float fres = pow(1.0 - clamp(dot(N, V), 0.0, 1.0), 2.6);

    vec2 suv = gl_FragCoord.xy / uResolution;
    vec2 off = N.xy * uRefract;

    vec3 refr;
    if (uHasBackdrop > 0.5) {
      float r = texture2D(uBackdrop, suv + off * (1.0 + uDispersion)).r;
      float g = texture2D(uBackdrop, suv + off).g;
      float b = texture2D(uBackdrop, suv + off * (1.0 - uDispersion)).b;
      refr = vec3(r, g, b);
    } else {
      // Yedek: iris lifi deseni — doku yüklenemezse sahne boş kalmaz
      float d = length(vUv - 0.5) * 2.0;
      float fib = 0.5 + 0.5 * sin(atan(vUv.y - 0.5, vUv.x - 0.5) * 42.0);
      refr = mix(vec3(0.06, 0.09, 0.09), uRim * 0.42, fib * (1.0 - d) * 0.6);
    }

    // Cam: merkez neredeyse şeffaf, yalnız kenar kaplama rengiyle yanar.
    vec3 col = mix(refr, uRim, fres * 0.62);
    float a = clamp(fres * 0.8 + uOpacity, 0.0, 0.72);
    gl_FragColor = vec4(col, a);
  }
`;

type ElementSpec = {
  r: number;
  t: number;
  /** başlangıç ve patlatılmış konum (z) */
  z0: number;
  z1: number;
  refract: number;
  dispersion: number;
  opacity: number;
};

const ELEMENTS: ElementSpec[] = [
  { r: 1.15, t: 0.3, z0: 0.0, z1: 0.85, refract: 0.055, dispersion: 0.16, opacity: 0.1 },
  { r: 0.92, t: 0.22, z0: -0.55, z1: -1.35, refract: 0.038, dispersion: 0.1, opacity: 0.08 },
  { r: 0.7, t: 0.17, z0: -1.05, z1: -3.1, refract: 0.026, dispersion: 0.06, opacity: 0.07 },
];

/* ── GPU kaynakları: modül düzeyinde, tembel, tek örnek ─────────────────── */
type Resources = {
  lens: Array<{ geometry: THREE.LatheGeometry; material: THREE.ShaderMaterial }>;
  ringGeo: THREE.TorusGeometry;
  ringMat: THREE.MeshBasicMaterial;
};

let RES: Resources | null = null;

function resources(): Resources {
  if (RES) return RES;
  RES = {
    lens: ELEMENTS.map((spec) => ({
      geometry: new THREE.LatheGeometry(lensProfile(spec.r, spec.t), 44),
      material: new THREE.ShaderMaterial({
        vertexShader: VERT,
        fragmentShader: FRAG,
        transparent: true,
        depthWrite: false,
        side: THREE.FrontSide,
        blending: THREE.NormalBlending,
        uniforms: {
          uBackdrop: { value: null },
          uHasBackdrop: { value: 0 },
          uResolution: { value: new THREE.Vector2(1, 1) },
          uRefract: { value: spec.refract },
          uDispersion: { value: spec.dispersion },
          // Kaplama rengi = markanın cyan'ı. Ölçüm değil; rengin fiziksel
          // kaynağı bu — anti-reflektif kaplamanın yansıması.
          uRim: { value: new THREE.Color("#00d4ff") },
          uOpacity: { value: spec.opacity },
        },
      }),
    })),
    ringGeo: new THREE.TorusGeometry(1.24, 0.006, 6, 72),
    ringMat: new THREE.MeshBasicMaterial({
      color: new THREE.Color("#00d4ff"),
      transparent: true,
      opacity: 0.26,
    }),
  };
  return RES;
}

function disposeResources() {
  if (!RES) return;
  for (const k of RES.lens) {
    k.geometry.dispose();
    k.material.dispose();
  }
  RES.ringGeo.dispose();
  RES.ringMat.dispose();
  RES = null;
}

function LensElement({ index }: { index: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const { size, viewport } = useThree();
  const spec = ELEMENTS[index];
  const { geometry, material } = resources().lens[index];

  useEffect(() => {
    material.uniforms.uResolution.value.set(
      size.width * viewport.dpr,
      size.height * viewport.dpr
    );
  }, [material, size.width, size.height, viewport.dpr]);

  // Hero videosunun kendi elementini doku olarak paylaş — ikinci indirme yok.
  useEffect(() => {
    const el = document.querySelector<HTMLVideoElement>("video[data-priority]");
    if (!el) return;
    const tex = new THREE.VideoTexture(el);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.minFilter = THREE.LinearFilter;
    material.uniforms.uBackdrop.value = tex;
    material.uniforms.uHasBackdrop.value = 1;
    return () => {
      material.uniforms.uHasBackdrop.value = 0;
      material.uniforms.uBackdrop.value = null;
      tex.dispose();
    };
  }, [material]);

  useFrame(() => {
    const m = ref.current;
    if (!m) return;
    const p = lensProgress.value;
    m.position.z = spec.z0 + (spec.z1 - spec.z0) * p;
    // Patlatılmış diyagramda elemanlar hafifçe yana açılır
    m.position.x = p * (index - 1) * 0.42 + lensProgress.px * 0.09;
    m.position.y = lensProgress.py * 0.07;
    // Lathe ekseni Y'dir; merceği kameraya çevirmek için X'te -PI/2 gerekir.
    m.rotation.x = -Math.PI / 2 + p * 0.2 + lensProgress.py * 0.05;
    m.rotation.z = p * 0.14 + lensProgress.px * 0.05;
  });

  return <mesh ref={ref} geometry={geometry} material={material} />;
}

/** Namlu halkaları — elemanların oturduğu mekanik çerçeve. */
function BarrelRings() {
  const ref = useRef<THREE.Group>(null);
  const { ringGeo, ringMat } = resources();

  useFrame(() => {
    const g = ref.current;
    if (!g) return;
    const p = lensProgress.value;
    g.position.z = -0.55 + p * -0.4;
    g.rotation.x = lensProgress.py * 0.06;
    g.rotation.y = lensProgress.px * 0.06;
    g.scale.setScalar(1 + p * 0.12);
  });

  return (
    <group ref={ref}>
      <mesh geometry={ringGeo} material={ringMat} />
      <mesh
        geometry={ringGeo}
        material={ringMat}
        position={[0, 0, -0.9]}
        scale={0.82}
      />
    </group>
  );
}

function Rig() {
  useFrame(({ camera }) => {
    const p = lensProgress.value;
    // Odak dalışı: kamera içeri girer, alan derinliği daralır
    camera.position.z = 4.6 - p * 1.5;
    camera.updateProjectionMatrix();
  });
  return null;
}

export default function LensScene() {
  useEffect(() => disposeResources, []);

  return (
    <Canvas
      camera={{ position: [0, 0, 4.6], fov: 32, near: 0.1, far: 24 }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      dpr={[1, 1.75]}
      style={{ pointerEvents: "none" }}
    >
      <Rig />
      <BarrelRings />
      {ELEMENTS.map((_, i) => (
        <LensElement key={i} index={i} />
      ))}
    </Canvas>
  );
}
