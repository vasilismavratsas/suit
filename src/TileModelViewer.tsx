import { useEffect, useRef } from "react";
import * as THREE from "three";

type ModelTile = {
  id: string;
  x: number;
  y: number;
  radius: number;
  rotation: number;
  shape: "hex" | "pent";
  zone: string;
  thickness: number;
  material: string;
};

type TileModelViewerProps = {
  tiles: ModelTile[];
  selectedTileId: string | null;
  width: number;
  height: number;
  onSelectTile: (tileId: string) => void;
};

const MODEL_SCALE = 0.045;

function tileColor(tile: ModelTile, isSelected: boolean): THREE.ColorRepresentation {
  if (isSelected) {
    return "#8ce7ff";
  }

  if (tile.shape === "pent") {
    return "#d59042";
  }

  if (tile.zone.includes("flexion")) {
    return "#9fb4c6";
  }

  if (tile.material === "Ti-beta") {
    return "#b7c9d9";
  }

  return "#dbe6ee";
}

function createTileGeometry(tile: ModelTile): THREE.ExtrudeGeometry {
  const sides = tile.shape === "hex" ? 6 : 5;
  const startAngle = tile.shape === "hex" ? Math.PI / 6 : -Math.PI / 2;
  const shape = new THREE.Shape();
  const radius = tile.radius * MODEL_SCALE;

  for (let index = 0; index < sides; index += 1) {
    const angle = startAngle + tile.rotation + (index * Math.PI * 2) / sides;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;

    if (index === 0) {
      shape.moveTo(x, y);
    } else {
      shape.lineTo(x, y);
    }
  }

  shape.closePath();

  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: tile.thickness * 0.085,
    bevelEnabled: true,
    bevelSegments: 1,
    bevelSize: 0.018,
    bevelThickness: 0.018,
  });
  geometry.center();

  return geometry;
}

function createConnectorGeometry(tile: ModelTile): THREE.BufferGeometry {
  const sides = tile.shape === "hex" ? 6 : 5;
  const startAngle = tile.shape === "hex" ? Math.PI / 6 : -Math.PI / 2;
  const radius = tile.radius * MODEL_SCALE * 1.04;
  const points: THREE.Vector3[] = [];

  for (let index = 0; index <= sides; index += 1) {
    const angle = startAngle + tile.rotation + (index * Math.PI * 2) / sides;
    points.push(new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, tile.thickness * 0.05));
  }

  return new THREE.BufferGeometry().setFromPoints(points);
}

function positionTileOnCurvedSuit(
  mesh: THREE.Object3D,
  tile: ModelTile,
  width: number,
  height: number,
) {
  const x = (tile.x - width / 2) * MODEL_SCALE;
  const y = (height / 2 - tile.y) * MODEL_SCALE;
  const normalizedX = (tile.x - width / 2) / (width * 0.34);
  const normalizedY = (tile.y - height / 2) / (height * 0.5);
  const z = 2.15 - Math.pow(normalizedX, 2) * 1.55 - Math.abs(normalizedY) * 0.18;

  mesh.position.set(x, y, z);
  mesh.rotation.y = -normalizedX * 0.34;
  mesh.rotation.x = normalizedY * 0.12;
}

function fitCameraToModel(camera: THREE.PerspectiveCamera, tiles: ModelTile[], width: number, height: number) {
  if (tiles.length === 0) {
    camera.position.set(0, 0, 24);
    return;
  }

  const minX = Math.min(...tiles.map((tile) => tile.x));
  const maxX = Math.max(...tiles.map((tile) => tile.x));
  const minY = Math.min(...tiles.map((tile) => tile.y));
  const maxY = Math.max(...tiles.map((tile) => tile.y));
  const span = Math.max((maxX - minX) * MODEL_SCALE, (maxY - minY) * MODEL_SCALE, 8);
  const aspectBoost = width > height ? 0.82 : 1.05;

  camera.position.set(0, 0, span * aspectBoost + 10);
}

export function TileModelViewer({
  tiles,
  selectedTileId,
  width,
  height,
  onSelectTile,
}: TileModelViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const frameRef = useRef<number | null>(null);
  const dragRef = useRef({ active: false, moved: false, x: 0, y: 0 });
  const onSelectRef = useRef(onSelectTile);

  useEffect(() => {
    onSelectRef.current = onSelectTile;
  }, [onSelectTile]);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return undefined;
    }

    const host = container;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 1000);
    const modelGroup = new THREE.Group();
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.appendChild(renderer.domElement);

    scene.add(modelGroup);
    scene.add(new THREE.AmbientLight("#7892a7", 1.25));

    const keyLight = new THREE.DirectionalLight("#ffffff", 3);
    keyLight.position.set(5, 8, 12);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight("#8ce7ff", 2.2);
    rimLight.position.set(-7, 4, 6);
    scene.add(rimLight);

    const grid = new THREE.GridHelper(18, 18, "#275c72", "#173142");
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -1.8;
    scene.add(grid);

    rendererRef.current = renderer;
    cameraRef.current = camera;
    sceneRef.current = scene;
    modelGroupRef.current = modelGroup;

    function resize() {
      const bounds = host.getBoundingClientRect();
      const nextWidth = Math.max(320, bounds.width);
      const nextHeight = Math.max(320, bounds.height);

      renderer.setSize(nextWidth, nextHeight, false);
      camera.aspect = nextWidth / nextHeight;
      camera.updateProjectionMatrix();
    }

    function animate() {
      renderer.render(scene, camera);
      frameRef.current = window.requestAnimationFrame(animate);
    }

    function handlePointerDown(event: PointerEvent) {
      dragRef.current = {
        active: true,
        moved: false,
        x: event.clientX,
        y: event.clientY,
      };
      renderer.domElement.setPointerCapture(event.pointerId);
    }

    function handlePointerMove(event: PointerEvent) {
      const drag = dragRef.current;

      if (!drag.active) {
        return;
      }

      const deltaX = event.clientX - drag.x;
      const deltaY = event.clientY - drag.y;

      if (Math.abs(deltaX) + Math.abs(deltaY) > 3) {
        drag.moved = true;
      }

      modelGroup.rotation.y += deltaX * 0.009;
      modelGroup.rotation.x = THREE.MathUtils.clamp(modelGroup.rotation.x + deltaY * 0.007, -1.15, 1.15);
      drag.x = event.clientX;
      drag.y = event.clientY;
    }

    function handlePointerUp(event: PointerEvent) {
      const drag = dragRef.current;
      drag.active = false;
      renderer.domElement.releasePointerCapture(event.pointerId);

      if (drag.moved) {
        return;
      }

      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);

      const intersections = raycaster.intersectObjects(modelGroup.children, true);
      const tileHit = intersections.find((hit) => hit.object.userData.tileId);

      if (tileHit?.object.userData.tileId) {
        onSelectRef.current(tileHit.object.userData.tileId);
      }
    }

    function handleWheel(event: WheelEvent) {
      event.preventDefault();
      camera.position.z = THREE.MathUtils.clamp(camera.position.z + event.deltaY * 0.018, 8, 60);
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(host);
    resize();
    animate();

    renderer.domElement.addEventListener("pointerdown", handlePointerDown);
    renderer.domElement.addEventListener("pointermove", handlePointerMove);
    renderer.domElement.addEventListener("pointerup", handlePointerUp);
    renderer.domElement.addEventListener("wheel", handleWheel, { passive: false });

    return () => {
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener("pointerdown", handlePointerDown);
      renderer.domElement.removeEventListener("pointermove", handlePointerMove);
      renderer.domElement.removeEventListener("pointerup", handlePointerUp);
      renderer.domElement.removeEventListener("wheel", handleWheel);

      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }

      modelGroup.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose();

        if (Array.isArray(mesh.material)) {
          mesh.material.forEach((material) => material.dispose());
        } else {
          mesh.material?.dispose();
        }
      });

      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  useEffect(() => {
    const modelGroup = modelGroupRef.current;
    const camera = cameraRef.current;

    if (!modelGroup || !camera) {
      return;
    }

    modelGroup.clear();
    fitCameraToModel(camera, tiles, width, height);

    const plateMaterialCache = new Map<string, THREE.MeshStandardMaterial>();
    const lineMaterial = new THREE.LineBasicMaterial({ color: "#06111d", transparent: true, opacity: 0.58 });

    tiles.forEach((tile) => {
      const isSelected = tile.id === selectedTileId;
      const materialKey = `${tileColor(tile, isSelected)}-${isSelected}`;
      let material = plateMaterialCache.get(materialKey);

      if (!material) {
        material = new THREE.MeshStandardMaterial({
          color: tileColor(tile, isSelected),
          metalness: 0.88,
          roughness: isSelected ? 0.18 : 0.32,
          emissive: isSelected ? "#123d4a" : "#000000",
          emissiveIntensity: isSelected ? 0.5 : 0,
        });
        plateMaterialCache.set(materialKey, material);
      }

      const mesh = new THREE.Mesh(createTileGeometry(tile), material);
      mesh.userData.tileId = tile.id;
      positionTileOnCurvedSuit(mesh, tile, width, height);
      modelGroup.add(mesh);

      const connectorLine = new THREE.Line(createConnectorGeometry(tile), lineMaterial);
      connectorLine.userData.tileId = tile.id;
      positionTileOnCurvedSuit(connectorLine, tile, width, height);
      modelGroup.add(connectorLine);
    });

    return () => {
      modelGroup.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose();
      });
      plateMaterialCache.forEach((material) => material.dispose());
      lineMaterial.dispose();
    };
  }, [height, selectedTileId, tiles, width]);

  return (
    <div className="model-viewer-shell">
      <div className="model-viewer" ref={containerRef} />
      <div className="model-controls">
        <span>Drag to rotate</span>
        <span>Scroll to zoom</span>
        <span>Click a tile to inspect</span>
      </div>
    </div>
  );
}
