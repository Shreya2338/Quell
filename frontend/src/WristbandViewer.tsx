import { useEffect, useRef } from "react";
import * as THREE from "three";

type Props = { className?: string; connected?: boolean };

function roundedRect(w: number, h: number, r: number) {
  const s = new THREE.Shape();
  const x = -w / 2, y = -h / 2;
  s.moveTo(x + r, y);
  s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + h - r); s.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  s.lineTo(x + r, y + h); s.quadraticCurveTo(x, y + h, x, y + h - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}

function screenTexture(connected: boolean) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 512;
  const g = cv.getContext("2d")!;
  const ORANGE = "#f5b068";
  g.fillStyle = "#19161a";
  g.fillRect(0, 0, 512, 512);
  g.fillStyle = ORANGE;
  g.textAlign = "center";
  g.textBaseline = "middle";
  if (connected) {
    g.lineWidth = 18;
    g.lineCap = "round";
    g.lineJoin = "round";
    g.beginPath();
    g.moveTo(130, 165);
    g.lineTo(185, 165);
    g.lineTo(220, 105);
    g.lineTo(265, 225);
    g.lineTo(305, 135);
    g.lineTo(340, 165);
    g.lineTo(390, 165);
    g.strokeStyle = ORANGE;
    g.stroke();
    g.font = '800 112px "Manrope", "Helvetica Neue", Arial, sans-serif';
    g.fillText("82", 260, 305);
    g.font = '700 30px "DM Sans", "Helvetica Neue", Arial, sans-serif';
    g.fillText("TODAY", 260, 390);
  } else {
    const bolt = (cx: number, cy: number) => {
      g.beginPath();
      g.moveTo(cx - 6, cy - 22); g.lineTo(cx + 20, cy - 22); g.lineTo(cx + 4, cy - 2);
      g.lineTo(cx + 24, cy - 2); g.lineTo(cx - 14, cy + 24); g.lineTo(cx - 2, cy + 4);
      g.lineTo(cx - 22, cy + 4); g.closePath(); g.fill();
    };
    bolt(206, 150);
    bolt(302, 150);
    g.fillRect(196, 250, 120, 16);
    g.font = '600 34px "DM Sans", "Helvetica Neue", Arial, sans-serif';
    g.fillText("PAIR", 260, 350);
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.anisotropy = 8;
  return tex;
}

export default function WristbandViewer({ className = "", connected = true }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current!;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    const BASE_Z = 15;
    let zoom = BASE_Z;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.style.display = "block";
    mount.appendChild(renderer.domElement);

    // Lights
    scene.add(new THREE.HemisphereLight(0xffffff, 0x4a3f52, 1.2));
    const key = new THREE.DirectionalLight(0xffffff, 1.4);
    key.position.set(4, 6, 8); scene.add(key);
    const rim = new THREE.DirectionalLight(0xf5b068, 0.6);
    rim.position.set(-6, -2, -4); scene.add(rim);

    const band = new THREE.Group();
    scene.add(band);

    // Strap: loop bent along an ellipse, lighter in the middle
    const A = 2.9, B = 2.1, W = 1.55, T = 0.2, SEG_Y = 96, SEG_X = 12, GAP = 0.34;
    const rowN = SEG_X + 1;
    const cEdge = new THREE.Color("#1c1324"), cMid = new THREE.Color("#573a6b");
    const theta = (i: number) => -Math.PI + GAP + (i / SEG_Y) * (2 * Math.PI - 2 * GAP);
    const pos: number[] = [], col: number[] = [], idx: number[] = [];
    for (let i = 0; i <= SEG_Y; i++) {
      const th = theta(i);
      const py = A * Math.sin(th), pz = -B + B * Math.cos(th);
      let ny = Math.sin(th) / A, nz = Math.cos(th) / B;
      const nl = Math.hypot(ny, nz); ny /= nl; nz /= nl;
      for (let j = 0; j <= SEG_X; j++) {
        const u = j / SEG_X;
        pos.push((u - 0.5) * W, py + (ny * T) / 2, pz + (nz * T) / 2);
        const m = 1 - Math.pow(Math.abs(u - 0.5) * 2, 2.2);
        const c = cEdge.clone().lerp(cMid, m);
        col.push(c.r, c.g, c.b);
      }
    }
    for (let i = 0; i < SEG_Y; i++)
      for (let j = 0; j < SEG_X; j++) {
        const a = i * rowN + j, b = a + 1, c = a + rowN, d = c + 1;
        idx.push(a, c, b, b, c, d);
      }
    const outer = new THREE.BufferGeometry();
    outer.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    outer.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    outer.setIndex(idx);
    outer.computeVertexNormals();
    band.add(new THREE.Mesh(outer, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.05, side: THREE.DoubleSide })));

    const inner = outer.clone();
    const ip = inner.attributes.position;
    for (let k = 0; k < ip.count; k++) {
      const tt = theta(Math.floor(k / rowN));
      const iy = Math.sin(tt) / A, iz = Math.cos(tt) / B, il = Math.hypot(iy, iz);
      ip.setY(k, ip.getY(k) - (iy / il) * T);
      ip.setZ(k, ip.getZ(k) - (iz / il) * T);
    }
    inner.computeVertexNormals();
    band.add(new THREE.Mesh(inner, new THREE.MeshStandardMaterial({ color: 0x120c18, roughness: 0.8, side: THREE.DoubleSide })));

    // Case, bezel, screen
    const caseMesh = new THREE.Mesh(
      new THREE.ExtrudeGeometry(roundedRect(2.5, 2.4, 0.62), { depth: 0.38, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelSegments: 5, curveSegments: 24 }),
      new THREE.MeshStandardMaterial({ color: 0x2b1f36, roughness: 0.4, metalness: 0.25 })
    );
    caseMesh.position.z = 0.02;
    band.add(caseMesh);

    const ringShape = roundedRect(2.2, 2.1, 0.5);
    ringShape.holes.push(new THREE.Path(roundedRect(2.08, 1.98, 0.44).getPoints(24).reverse()));
    const ring = new THREE.Mesh(new THREE.ShapeGeometry(ringShape, 24), new THREE.MeshStandardMaterial({ color: 0x6a4f80, roughness: 0.35, metalness: 0.3 }));
    ring.position.z = 0.52;
    band.add(ring);

    const tex = screenTexture(connected);
    const scrGeo = new THREE.ShapeGeometry(roundedRect(2.08, 1.98, 0.44), 24);
    const sp = scrGeo.attributes.position, uv = scrGeo.attributes.uv;
    for (let q = 0; q < sp.count; q++) uv.setXY(q, (sp.getX(q) + 1.04) / 2.08, (sp.getY(q) + 0.99) / 1.98);
    const screen = new THREE.Mesh(scrGeo, new THREE.MeshBasicMaterial({ map: tex }));
    screen.position.z = 0.521;
    band.add(screen);

    const sheen = new THREE.Mesh(scrGeo, new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.06, roughness: 0.05 }));
    sheen.position.z = 0.525;
    band.add(sheen);

    // Pivot about the middle of the wrist loop
    band.children.forEach((m) => { m.position.z += B; });

    // Interaction
    let rotX = 0.12, rotY = -0.45, velX = 0, velY = 0, idle = 0;
    let dragging = false, lastX = 0, lastY = 0;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const onDown = (e: PointerEvent) => {
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      mount.style.cursor = "grabbing"; mount.setPointerCapture(e.pointerId);
    };
    const onMove = (e: PointerEvent) => {
      if (!dragging) return;
      velY = (e.clientX - lastX) * 0.01; velX = (e.clientY - lastY) * 0.01;
      rotY += velY; rotX = Math.max(-1.2, Math.min(1.2, rotX + velX));
      lastX = e.clientX; lastY = e.clientY; idle = 0;
    };
    const onUp = () => { dragging = false; mount.style.cursor = "grab"; };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      zoom = Math.max(8, Math.min(26, zoom + e.deltaY * 0.01));
    };
    mount.addEventListener("pointerdown", onDown);
    mount.addEventListener("pointermove", onMove);
    mount.addEventListener("pointerup", onUp);
    mount.addEventListener("pointercancel", onUp);
    mount.addEventListener("wheel", onWheel, { passive: false });

    const resize = () => {
      const w = mount.clientWidth || 1, h = mount.clientHeight || 1;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = "100%";
      renderer.domElement.style.height = "100%";
      camera.aspect = w / h;
      camera.fov = w / h < 0.8 ? 42 : 32;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(mount);
    resize();

    let raf = 0, last = performance.now();
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      const dt = (now - last) / 1000; last = now;
      if (!dragging) {
        rotY += velY; rotX = Math.max(-1.2, Math.min(1.2, rotX + velX));
        velX *= 0.94; velY *= 0.94; idle += dt;
        if (!reduce && idle > 3) rotY += 0.004;
      }
      band.rotation.set(rotX, rotY, 0);
      camera.position.set(0, 0, zoom);
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      mount.removeEventListener("pointerdown", onDown);
      mount.removeEventListener("pointermove", onMove);
      mount.removeEventListener("pointerup", onUp);
      mount.removeEventListener("pointercancel", onUp);
      mount.removeEventListener("wheel", onWheel);
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose()); else mat?.dispose();
      });
      tex.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, [connected]);

  return (
    <div
      ref={mountRef}
      className={className}
      role="img"
      aria-label="Interactive 3D wristband. Drag to rotate, scroll to zoom."
    />
  );
}
