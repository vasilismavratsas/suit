import { useEffect, useRef } from "react";
import * as THREE from "three";

type ModelTile = {
  id: string;
  row: number;
  col: number;
  x: number;
  y: number;
  radius: number;
  rotation: number;
  shape: "hex" | "pent";
  zone: string;
  thickness: number;
  material: string;
};

type SurfaceMode = "flat-panel" | "arm-tube" | "torso-shell" | "helmet-dome";

type TileModelViewerProps = {
  tiles: ModelTile[];
  selectedTileId: string | null;
  surfaceMode: SurfaceMode;
  wrapAngle: number;
  width: number;
  height: number;
  onSelectTile: (tileId: string) => void;
};

const MODEL_SCALE = 0.045;
const UP_VECTOR = new THREE.Vector3(0, 1, 0);
const LOCAL_NORMAL = new THREE.Vector3(0, 0, 1);

type TileBounds = {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  spanX: number;
  spanY: number;
  centerX: number;
  centerY: number;
};

type SurfacePlacement = {
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
};

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

function getTileBounds(tiles: ModelTile[], width: number, height: number): TileBounds {
  if (tiles.length === 0) {
    return {
      minX: 0,
      maxX: width,
      minY: 0,
      maxY: height,
      spanX: width,
      spanY: height,
      centerX: width / 2,
      centerY: height / 2,
    };
  }

  const minX = Math.min(...tiles.map((tile) => tile.x));
  const maxX = Math.max(...tiles.map((tile) => tile.x));
  const minY = Math.min(...tiles.map((tile) => tile.y));
  const maxY = Math.max(...tiles.map((tile) => tile.y));
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);

  return {
    minX,
    maxX,
    minY,
    maxY,
    spanX,
    spanY,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
  };
}

function buildPlacementFromBasis(
  position: THREE.Vector3,
  tangentU: THREE.Vector3,
  tangentV: THREE.Vector3,
): SurfacePlacement {
  const normal = new THREE.Vector3().crossVectors(tangentU, tangentV).normalize();
  const matrix = new THREE.Matrix4().makeBasis(tangentU.normalize(), tangentV.normalize(), normal);

  return {
    position,
    quaternion: new THREE.Quaternion().setFromRotationMatrix(matrix),
  };
}

function getSurfacePlacement(
  tile: ModelTile,
  bounds: TileBounds,
  surfaceMode: SurfaceMode,
  wrapAngle: number,
): SurfacePlacement {
  const xRatio = (tile.x - bounds.minX) / bounds.spanX;
  const yRatio = (tile.y - bounds.minY) / bounds.spanY;
  const centeredX = xRatio - 0.5;
  const vertical = (bounds.centerY - tile.y) * MODEL_SCALE;
  const angleSpan = THREE.MathUtils.degToRad(surfaceMode === "flat-panel" ? 0 : wrapAngle);
  const theta = centeredX * angleSpan;

  if (surfaceMode === "arm-tube") {
    const radius = Math.max(2.2, (bounds.spanX * MODEL_SCALE) / Math.max(angleSpan, Math.PI / 2));
    const position = new THREE.Vector3(Math.sin(theta) * radius, vertical, Math.cos(theta) * radius);
    const tangentU = new THREE.Vector3(Math.cos(theta), 0, -Math.sin(theta)).normalize();

    return buildPlacementFromBasis(position, tangentU, UP_VECTOR.clone());
  }

  if (surfaceMode === "torso-shell") {
    const radiusX = Math.max(3.2, (bounds.spanX * MODEL_SCALE) / Math.max(angleSpan, Math.PI / 2));
    const radiusZ = radiusX * 0.62;
    const taper = 0.72 + Math.sin(Math.PI * yRatio) * 0.28;
    const position = new THREE.Vector3(
      Math.sin(theta) * radiusX * taper,
      vertical,
      Math.cos(theta) * radiusZ * taper,
    );
    const tangentU = new THREE.Vector3(Math.cos(theta) * radiusX, 0, -Math.sin(theta) * radiusZ).normalize();

    return buildPlacementFromBasis(position, tangentU, UP_VECTOR.clone());
  }

  if (surfaceMode === "helmet-dome") {
    const radius = Math.max(3.6, (bounds.spanX * MODEL_SCALE) / Math.max(angleSpan, Math.PI / 2));
    const phi = 0.24 + yRatio * 1.2;
    const domeRadius = radius * (0.86 + Math.sin(Math.PI * yRatio) * 0.08);
    const position = new THREE.Vector3(
      Math.sin(theta) * Math.sin(phi) * domeRadius,
      Math.cos(phi) * domeRadius * 0.9,
      Math.cos(theta) * Math.sin(phi) * domeRadius,
    );
    const tangentU = new THREE.Vector3(Math.cos(theta), 0, -Math.sin(theta)).normalize();
    const tangentV = new THREE.Vector3(
      Math.sin(theta) * Math.cos(phi),
      -Math.sin(phi) * 0.9,
      Math.cos(theta) * Math.cos(phi),
    ).normalize();

    return buildPlacementFromBasis(position, tangentU, tangentV);
  }

  const x = (tile.x - bounds.centerX) * MODEL_SCALE;
  const y = vertical;
  const normalizedX = (tile.x - bounds.centerX) / Math.max(bounds.spanX * 0.5, 1);
  const normalizedY = (tile.y - bounds.centerY) / Math.max(bounds.spanY * 0.5, 1);
  const z = 1.2 - Math.pow(normalizedX, 2) * 0.32 - Math.abs(normalizedY) * 0.1;
  const normal = new THREE.Vector3(-normalizedX * 0.18, normalizedY * 0.06, 1).normalize();

  return {
    position: new THREE.Vector3(x, y, z),
    quaternion: new THREE.Quaternion().setFromUnitVectors(LOCAL_NORMAL, normal),
  };
}

function applySurfacePlacement(mesh: THREE.Object3D, placement: SurfacePlacement) {
  mesh.position.copy(placement.position);
  mesh.quaternion.copy(placement.quaternion);
}

function createLinkMesh(
  start: THREE.Vector3,
  end: THREE.Vector3,
  material: THREE.Material,
): THREE.Mesh | null {
  const direction = new THREE.Vector3().subVectors(end, start);
  const length = direction.length();

  if (length < 0.05) {
    return null;
  }

  const geometry = new THREE.CylinderGeometry(0.025, 0.025, length, 8);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(start).add(end).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(UP_VECTOR, direction.normalize());

  return mesh;
}

function fitCameraToModel(
  camera: THREE.PerspectiveCamera,
  tiles: ModelTile[],
  width: number,
  height: number,
  surfaceMode: SurfaceMode,
  wrapAngle: number,
) {
  if (tiles.length === 0) {
    camera.position.set(0, 0, 24);
    return;
  }

  const bounds = getTileBounds(tiles, width, height);
  const wrapBoost = surfaceMode === "flat-panel" ? 1 : 1 + Math.min(wrapAngle, 360) / 720;
  const span = Math.max(bounds.spanX * MODEL_SCALE, bounds.spanY * MODEL_SCALE, 8) * wrapBoost;
  const aspectBoost = width > height ? 0.82 : 1.05;

  camera.position.set(0, 0, span * aspectBoost + 10);
}

export function TileModelViewer({
  tiles,
  selectedTileId,
  surfaceMode,
  wrapAngle,
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
    fitCameraToModel(camera, tiles, width, height, surfaceMode, wrapAngle);

    const plateMaterialCache = new Map<string, THREE.MeshStandardMaterial>();
    const lineMaterial = new THREE.LineBasicMaterial({ color: "#06111d", transparent: true, opacity: 0.58 });
    const linkMaterial = new THREE.MeshStandardMaterial({
      color: "#8ce7ff",
      emissive: "#0b3a45",
      emissiveIntensity: 0.35,
      metalness: 0.72,
      roughness: 0.24,
      transparent: true,
      opacity: 0.82,
    });
    const bounds = getTileBounds(tiles, width, height);
    const placements = new Map(
      tiles.map((tile) => [tile.id, getSurfacePlacement(tile, bounds, surfaceMode, wrapAngle)]),
    );
    const tileByGrid = new Map(tiles.map((tile) => [`${tile.row}:${tile.col}`, tile]));

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
      applySurfacePlacement(mesh, placements.get(tile.id) as SurfacePlacement);
      modelGroup.add(mesh);

      const connectorLine = new THREE.Line(createConnectorGeometry(tile), lineMaterial);
      connectorLine.userData.tileId = tile.id;
      applySurfacePlacement(connectorLine, placements.get(tile.id) as SurfacePlacement);
      modelGroup.add(connectorLine);
    });

    tiles.forEach((tile) => {
      const placement = placements.get(tile.id);

      if (!placement) {
        return;
      }

      [
        `${tile.row}:${tile.col + 1}`,
        `${tile.row + 1}:${tile.col}`,
        `${tile.row + 1}:${tile.col - 1}`,
        `${tile.row + 1}:${tile.col + 1}`,
      ].forEach((neighborKey) => {
        const neighbor = tileByGrid.get(neighborKey);

        if (!neighbor) {
          return;
        }

        const neighborPlacement = placements.get(neighbor.id);

        if (!neighborPlacement) {
          return;
        }

        const maxLinkLength = tile.radius * MODEL_SCALE * 3.6;
        const linkLength = placement.position.distanceTo(neighborPlacement.position);

        if (linkLength > maxLinkLength) {
          return;
        }

        const linkMesh = createLinkMesh(placement.position, neighborPlacement.position, linkMaterial);

        if (linkMesh) {
          modelGroup.add(linkMesh);
        }
      });
    });

    return () => {
      modelGroup.traverse((object) => {
        const mesh = object as THREE.Mesh;
        mesh.geometry?.dispose();
      });
      plateMaterialCache.forEach((material) => material.dispose());
      lineMaterial.dispose();
      linkMaterial.dispose();
    };
  }, [height, selectedTileId, surfaceMode, tiles, width, wrapAngle]);

  return (
    <div className="model-viewer-shell">
      <div className="model-viewer" ref={containerRef} />
      <div className="model-controls">
        <span>{surfaceMode.replace("-", " ")}</span>
        <span>Drag to rotate</span>
        <span>Scroll to zoom</span>
        <span>Click a tile to inspect</span>
        {surfaceMode !== "flat-panel" && <span>{wrapAngle} deg linked wrap</span>}
      </div>
    </div>
  );
}
