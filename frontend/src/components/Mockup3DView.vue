<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

/** The assembled knife in 3D: drag to turn, wheel to zoom, "explode" to pull the plates apart. */
export interface PreviewMesh {
  name: string;
  role: string;
  colour: string;
  z0: number;
  z1: number;
  positions: number[];
  indices: number[];
}

const props = defineProps<{ meshes: PreviewMesh[]; explode: number }>();
const host = ref<HTMLDivElement | null>(null);

let renderer: THREE.WebGLRenderer | null = null;
let camera: THREE.PerspectiveCamera;
let controls: OrbitControls;
let scene: THREE.Scene;
let group = new THREE.Group();
let frame = 0;
let resize: ResizeObserver | null = null;
let fitted = false;

function build() {
  scene.remove(group);
  group.traverse((o) => {
    if (o instanceof THREE.Mesh) {
      o.geometry.dispose();
      (o.material as THREE.Material).dispose();
    }
  });
  group = new THREE.Group();
  for (const m of props.meshes) {
    const geo = new THREE.BufferGeometry();
    // drawing coordinates are y down: flip y so the knife reads as drawn
    const pos = new Float32Array(m.positions.length);
    for (let i = 0; i < m.positions.length; i += 3) {
      pos[i] = m.positions[i];
      pos[i + 1] = -m.positions[i + 1];
      pos[i + 2] = m.positions[i + 2];
    }
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setIndex(m.indices);
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ color: m.colour, metalness: m.role === "blade" ? 0.55 : 0.1, roughness: m.role === "blade" ? 0.35 : 0.7, side: THREE.DoubleSide, flatShading: true });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { centre: (m.z0 + m.z1) / 2 };
    group.add(mesh);
  }
  scene.add(group);
  applyExplode();
  if (!fitted && props.meshes.length) {
    fit();
    fitted = true;
  }
}

function applyExplode() {
  for (const child of group.children) child.position.z = (child.userData.centre as number) * props.explode;
}

function fit() {
  const box = new THREE.Box3().setFromObject(group);
  const size = box.getSize(new THREE.Vector3());
  const centre = box.getCenter(new THREE.Vector3());
  const dist = Math.max(size.x, size.y, size.z) * 1.4;
  camera.position.set(centre.x + dist * 0.35, centre.y - dist * 0.55, centre.z + dist * 0.75);
  camera.near = dist / 100;
  camera.far = dist * 20;
  camera.updateProjectionMatrix();
  controls.target.copy(centre);
  controls.update();
}

onMounted(() => {
  const el = host.value!;
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(35, 1, 1, 10000);
  camera.up.set(0, 0, 1);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
  el.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8170, 1.6));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(200, -300, 400);
  scene.add(sun);
  resize = new ResizeObserver(() => {
    const { clientWidth: w, clientHeight: h } = el;
    renderer!.setSize(w, h, false);
    renderer!.domElement.style.width = "100%";
    renderer!.domElement.style.height = "100%";
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
  });
  resize.observe(el);
  build();
  const loop = () => {
    controls.update();
    renderer!.render(scene, camera);
    frame = requestAnimationFrame(loop);
  };
  loop();
});

watch(() => props.meshes, build);
watch(() => props.explode, applyExplode);

onBeforeUnmount(() => {
  cancelAnimationFrame(frame);
  resize?.disconnect();
  controls?.dispose();
  renderer?.dispose();
});

defineExpose({ fit });
</script>

<template>
  <div ref="host" class="w-full h-full min-h-[280px] rounded-lg bg-[#f2efe8] dark:bg-[#26241f] overflow-hidden"></div>
</template>
