import { useMemo, useState } from "react";
import { TileModelViewer } from "./TileModelViewer";

type SuitSection = "torso" | "arm" | "leg" | "helmet";
type TileShape = "hex" | "pent";
type MaterialGrade = "Ti-6Al-4V" | "Ti-6242" | "Ti-beta";
type SurfaceMode = "flat-panel" | "arm-tube" | "torso-shell" | "helmet-dome";

type Tile = {
  id: string;
  row: number;
  col: number;
  x: number;
  y: number;
  radius: number;
  rotation: number;
  shape: TileShape;
  zone: string;
  thickness: number;
  material: MaterialGrade;
  edgeLoad: number;
};

type TileOverride = Partial<Pick<Tile, "shape" | "rotation" | "thickness" | "material">>;

const SVG_WIDTH = 900;
const SVG_HEIGHT = 940;
const TITANIUM_DENSITY_G_PER_MM3 = 0.00443;

const sectionDetails: Record<
  SuitSection,
  { label: string; subtitle: string; widthScale: number; heightScale: number }
> = {
  torso: {
    label: "Torso shell",
    subtitle: "Pressure garment chest, abdomen, and shoulder yoke",
    widthScale: 1,
    heightScale: 1,
  },
  arm: {
    label: "Arm segment",
    subtitle: "Upper/lower arm tube with elbow articulation bands",
    widthScale: 0.48,
    heightScale: 0.95,
  },
  leg: {
    label: "Leg segment",
    subtitle: "Thigh-to-boot exoskeleton rail with knee flexion tile belts",
    widthScale: 0.58,
    heightScale: 1.05,
  },
  helmet: {
    label: "Helmet crown",
    subtitle: "Curved cranial armor with pentagonal stress-relief seams",
    widthScale: 0.72,
    heightScale: 0.62,
  },
};

const surfaceModes: Record<SurfaceMode, { label: string; description: string }> = {
  "flat-panel": {
    label: "Flat development panel",
    description: "A buildable sheet view for laying out tiles before bending.",
  },
  "arm-tube": {
    label: "Arm / leg tube",
    description: "Wraps tiles around a cylindrical limb section.",
  },
  "torso-shell": {
    label: "Torso shell",
    description: "Wraps tiles around an elliptical chest and back shell.",
  },
  "helmet-dome": {
    label: "Helmet dome",
    description: "Projects tiles over a rounded crown surface.",
  },
};

function getDefaultSurfaceMode(section: SuitSection): SurfaceMode {
  if (section === "arm" || section === "leg") {
    return "arm-tube";
  }

  if (section === "helmet") {
    return "helmet-dome";
  }

  return "torso-shell";
}

function getHalfWidth(section: SuitSection, normalizedY: number): number {
  const y = Math.max(0, Math.min(1, normalizedY));

  if (section === "helmet") {
    return Math.sin(Math.PI * y) * 0.34 + 0.08;
  }

  if (section === "arm") {
    const elbowPinch = 0.06 * Math.exp(-Math.pow((y - 0.55) / 0.09, 2));
    return 0.17 - elbowPinch + 0.03 * Math.sin(Math.PI * y);
  }

  if (section === "leg") {
    const kneePinch = 0.07 * Math.exp(-Math.pow((y - 0.54) / 0.1, 2));
    return 0.22 - 0.04 * y - kneePinch + 0.04 * Math.sin(Math.PI * y);
  }

  if (y < 0.12) {
    return 0.12 + y * 1.6;
  }

  if (y < 0.38) {
    return 0.34 - (y - 0.12) * 0.08;
  }

  if (y < 0.68) {
    return 0.31 - (y - 0.38) * 0.22;
  }

  return 0.24 + (y - 0.68) * 0.14;
}

function isInsideSection(section: SuitSection, x: number, y: number, curvature: number): boolean {
  const detail = sectionDetails[section];
  const centerX = SVG_WIDTH / 2;
  const top = section === "helmet" ? 120 : 70;
  const sectionHeight = 760 * detail.heightScale;
  const sectionWidth = 760 * detail.widthScale;
  const normalizedY = (y - top) / sectionHeight;

  if (normalizedY < 0 || normalizedY > 1) {
    return false;
  }

  const curveShift =
    section === "torso"
      ? Math.sin((normalizedY - 0.15) * Math.PI) * curvature * 18
      : Math.sin((normalizedY - 0.5) * Math.PI) * curvature * 10;
  const normalizedX = (x - centerX - curveShift) / sectionWidth;
  const halfWidth = getHalfWidth(section, normalizedY);

  return Math.abs(normalizedX) <= halfWidth;
}

function getZone(section: SuitSection, x: number, y: number): string {
  const normalizedY = (y - 70) / (760 * sectionDetails[section].heightScale);
  const centerDistance = Math.abs(x - SVG_WIDTH / 2) / SVG_WIDTH;

  if (section === "helmet") {
    return normalizedY < 0.35 ? "visor crown" : "neck ring";
  }

  if (section === "arm" && normalizedY > 0.45 && normalizedY < 0.63) {
    return "elbow flexion";
  }

  if (section === "leg" && normalizedY > 0.45 && normalizedY < 0.63) {
    return "knee flexion";
  }

  if (section === "torso" && normalizedY < 0.2) {
    return "shoulder yoke";
  }

  if (centerDistance < 0.08) {
    return "spine rail";
  }

  return normalizedY > 0.7 ? "mobility skirt" : "load shell";
}

function polygonPoints(tile: Tile): string {
  const sides = tile.shape === "hex" ? 6 : 5;
  const startAngle = tile.shape === "hex" ? Math.PI / 6 : -Math.PI / 2;

  return Array.from({ length: sides }, (_, index) => {
    const angle = startAngle + tile.rotation + (index * Math.PI * 2) / sides;
    const x = tile.x + Math.cos(angle) * tile.radius;
    const y = tile.y + Math.sin(angle) * tile.radius;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function connectorPoints(tile: Tile): Array<{ x: number; y: number }> {
  return polygonPoints(tile)
    .split(" ")
    .map((point) => {
      const [x, y] = point.split(",").map(Number);
      return { x, y };
    });
}

function getTileAreaMm2(tile: Tile): number {
  const radiusMm = tile.radius * 2.8;
  const sides = tile.shape === "hex" ? 6 : 5;
  return (sides * radiusMm * radiusMm * Math.sin((2 * Math.PI) / sides)) / 2;
}

function getTileMassGrams(tile: Tile): number {
  return getTileAreaMm2(tile) * tile.thickness * TITANIUM_DENSITY_G_PER_MM3;
}

function generateTiles(
  section: SuitSection,
  tileRadius: number,
  connectorGap: number,
  curvature: number,
  overrides: Record<string, TileOverride>,
): Tile[] {
  const detail = sectionDetails[section];
  const tiles: Tile[] = [];
  const verticalStep = tileRadius * 1.48 + connectorGap;
  const horizontalStep = tileRadius * 1.72 + connectorGap;
  const startY = section === "helmet" ? 130 : 78;
  const endY = startY + 760 * detail.heightScale;
  let row = 0;

  for (let y = startY; y <= endY; y += verticalStep) {
    const rowOffset = row % 2 === 0 ? 0 : horizontalStep / 2;
    let col = 0;

    for (let x = 70 + rowOffset; x <= SVG_WIDTH - 70; x += horizontalStep) {
      if (!isInsideSection(section, x, y, curvature)) {
        col += 1;
        continue;
      }

      const normalizedY = (y - startY) / (endY - startY);
      const centerOffset = Math.abs(x - SVG_WIDTH / 2) / SVG_WIDTH;
      const nearFlexionBand =
        (section === "arm" || section === "leg") && normalizedY > 0.43 && normalizedY < 0.65;
      const nearHelmetCrown = section === "helmet" && normalizedY < 0.25;
      const nearTorsoSeam = section === "torso" && (centerOffset < 0.055 || normalizedY < 0.14);
      const shape: TileShape =
        nearFlexionBand || nearHelmetCrown || nearTorsoSeam || (row + col) % 11 === 0 ? "pent" : "hex";
      const id = `${section}-${row}-${col}`;
      const override = overrides[id];
      const zone = getZone(section, x, y);
      const defaultThickness = zone.includes("flexion") ? 1.8 : zone === "spine rail" ? 2.6 : 2.2;

      tiles.push({
        id,
        row,
        col,
        x,
        y,
        radius: tileRadius,
        rotation: override?.rotation ?? ((row % 3) * Math.PI) / 18,
        shape: override?.shape ?? shape,
        zone,
        thickness: override?.thickness ?? defaultThickness,
        material: override?.material ?? (zone.includes("flexion") ? "Ti-beta" : "Ti-6Al-4V"),
        edgeLoad: Math.round(34 + centerOffset * 130 + normalizedY * 42),
      });

      col += 1;
    }

    row += 1;
  }

  return tiles;
}

function getSectionOutline(section: SuitSection): string {
  const detail = sectionDetails[section];
  const top = section === "helmet" ? 120 : 70;
  const height = 760 * detail.heightScale;
  const width = 760 * detail.widthScale;
  const centerX = SVG_WIDTH / 2;
  const right: string[] = [];
  const left: string[] = [];

  for (let i = 0; i <= 32; i += 1) {
    const yNorm = i / 32;
    const y = top + yNorm * height;
    const half = getHalfWidth(section, yNorm) * width;
    right.push(`${(centerX + half).toFixed(1)},${y.toFixed(1)}`);
    left.unshift(`${(centerX - half).toFixed(1)},${y.toFixed(1)}`);
  }

  return `M ${right.join(" L ")} L ${left.join(" L ")} Z`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value);
}

function App() {
  const [section, setSection] = useState<SuitSection>("torso");
  const [surfaceMode, setSurfaceMode] = useState<SurfaceMode>("torso-shell");
  const [wrapAngle, setWrapAngle] = useState(240);
  const [tileRadius, setTileRadius] = useState(27);
  const [connectorGap, setConnectorGap] = useState(5);
  const [curvature, setCurvature] = useState(0.45);
  const [selectedTileId, setSelectedTileId] = useState<string | null>(null);
  const [overrides, setOverrides] = useState<Record<string, TileOverride>>({});
  const [copied, setCopied] = useState(false);

  const tiles = useMemo(
    () => generateTiles(section, tileRadius, connectorGap, curvature, overrides),
    [section, tileRadius, connectorGap, curvature, overrides],
  );
  const selectedTile =
    tiles.find((tile) => tile.id === selectedTileId) ?? tiles[Math.floor(tiles.length / 2)];
  const outlinePath = useMemo(() => getSectionOutline(section), [section]);
  const totalMass = useMemo(
    () => tiles.reduce((sum, tile) => sum + getTileMassGrams(tile), 0),
    [tiles],
  );
  const pentagonCount = tiles.filter((tile) => tile.shape === "pent").length;
  const connectorCount = tiles.reduce((sum, tile) => sum + (tile.shape === "hex" ? 6 : 5), 0);
  const surfacePlaneCount = surfaceMode === "flat-panel" ? 1 : Math.max(2, Math.ceil(wrapAngle / 45));
  const designExport = useMemo(
    () => ({
      project: "next-generation-spacesuit-exoskeleton",
      section,
      generatedAt: new Date().toISOString(),
      parameters: {
        tileRadiusMm: tileRadius * 2.8,
        connectorGapMm: connectorGap * 2.8,
        curvature,
        surfaceMode,
        wrapAngleDegrees: surfaceMode === "flat-panel" ? 0 : wrapAngle,
      },
      billOfMaterials: {
        tiles: tiles.length,
        hexagons: tiles.length - pentagonCount,
        pentagons: pentagonCount,
        titaniumMassGrams: Number(totalMass.toFixed(2)),
        connectors: connectorCount,
      },
      model3d: {
        projection: surfaceModes[surfaceMode].label,
        plateGeometry: "extruded regular polygon tiles",
        linkedSurfacePlanes: surfacePlaneCount,
        interaction: "drag-to-rotate, wheel-to-zoom, click-to-select",
      },
      selectedTile,
      tiles: tiles.map((tile) => ({
        id: tile.id,
        shape: tile.shape,
        positionMm: {
          x: Number((tile.x * 2.8).toFixed(1)),
          y: Number((tile.y * 2.8).toFixed(1)),
        },
        radiusMm: Number((tile.radius * 2.8).toFixed(1)),
        thicknessMm: tile.thickness,
        material: tile.material,
        zone: tile.zone,
        rotationDeg: Number(((tile.rotation * 180) / Math.PI).toFixed(1)),
      })),
    }),
    [
      connectorCount,
      curvature,
      pentagonCount,
      section,
      selectedTile,
      surfaceMode,
      surfacePlaneCount,
      tileRadius,
      connectorGap,
      tiles,
      totalMass,
      wrapAngle,
    ],
  );

  function updateSelectedTile(patch: TileOverride) {
    if (!selectedTile) {
      return;
    }

    setSelectedTileId(selectedTile.id);
    setOverrides((current) => ({
      ...current,
      [selectedTile.id]: {
        ...current[selectedTile.id],
        ...patch,
      },
    }));
  }

  async function copyExport() {
    await navigator.clipboard.writeText(JSON.stringify(designExport, null, 2));
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  function downloadExport() {
    const blob = new Blob([JSON.stringify(designExport, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${section}-titanium-tile-exoskeleton.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Parametric CAD concept</p>
          <h1>Next-generation space suit exoskeleton designer</h1>
          <p>
            Layout repeated titanium hexagonal and pentagonal armor tiles, tune connector
            spacing, inspect stress zones, and export manufacturing metadata for each suit section.
          </p>
        </div>
        <div className="hero-card">
          <span>{tiles.length}</span>
          <small>interlocking plates</small>
        </div>
      </section>

      <section className="dashboard">
        <aside className="panel controls-panel">
          <div className="panel-heading">
            <p className="eyebrow">Controls</p>
            <h2>Tile generator</h2>
          </div>

          <label>
            Suit section
            <select
              value={section}
              onChange={(event) => {
                const nextSection = event.target.value as SuitSection;
                setSection(nextSection);
                setSurfaceMode(getDefaultSurfaceMode(nextSection));
              }}
            >
              {Object.entries(sectionDetails).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            3D surface
            <select value={surfaceMode} onChange={(event) => setSurfaceMode(event.target.value as SurfaceMode)}>
              {Object.entries(surfaceModes).map(([key, value]) => (
                <option key={key} value={key}>
                  {value.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            Wrap coverage <span>{surfaceMode === "flat-panel" ? "flat" : `${wrapAngle} deg`}</span>
            <input
              disabled={surfaceMode === "flat-panel"}
              min="90"
              max="360"
              step="15"
              type="range"
              value={wrapAngle}
              onChange={(event) => setWrapAngle(Number(event.target.value))}
            />
          </label>

          <label>
            Tile radius <span>{Math.round(tileRadius * 2.8)} mm</span>
            <input
              min="18"
              max="36"
              type="range"
              value={tileRadius}
              onChange={(event) => setTileRadius(Number(event.target.value))}
            />
          </label>

          <label>
            Connector gap <span>{Math.round(connectorGap * 2.8)} mm</span>
            <input
              min="2"
              max="14"
              type="range"
              value={connectorGap}
              onChange={(event) => setConnectorGap(Number(event.target.value))}
            />
          </label>

          <label>
            Curvature compensation <span>{Math.round(curvature * 100)}%</span>
            <input
              min="0"
              max="1"
              step="0.05"
              type="range"
              value={curvature}
              onChange={(event) => setCurvature(Number(event.target.value))}
            />
          </label>

          <div className="metric-grid">
            <div>
              <strong>{tiles.length - pentagonCount}</strong>
              <span>hex tiles</span>
            </div>
            <div>
              <strong>{pentagonCount}</strong>
              <span>pent tiles</span>
            </div>
            <div>
              <strong>{connectorCount}</strong>
              <span>edge locks</span>
            </div>
            <div>
              <strong>{formatNumber(totalMass / 1000)} kg</strong>
              <span>Ti mass</span>
            </div>
            <div>
              <strong>{surfacePlaneCount}</strong>
              <span>3D planes</span>
            </div>
          </div>

          <div className="export-actions">
            <button onClick={copyExport}>{copied ? "Copied JSON" : "Copy CAD JSON"}</button>
            <button className="secondary" onClick={downloadExport}>
              Download model
            </button>
          </div>
        </aside>

        <section className="panel canvas-panel">
          <div className="panel-heading canvas-heading">
            <div>
              <p className="eyebrow">{sectionDetails[section].label}</p>
              <h2>{sectionDetails[section].subtitle}</h2>
            </div>
            <span className="status-pill">Live topology</span>
          </div>

          <svg className="cad-canvas" viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`} role="img">
            <title>Titanium hexagonal and pentagonal exoskeleton tile layout</title>
            <defs>
              <linearGradient id="tileGradient" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0%" stopColor="#d7e4ef" />
                <stop offset="52%" stopColor="#8ca3b3" />
                <stop offset="100%" stopColor="#405466" />
              </linearGradient>
              <linearGradient id="pentGradient" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0%" stopColor="#f7dfb3" />
                <stop offset="55%" stopColor="#d59042" />
                <stop offset="100%" stopColor="#785126" />
              </linearGradient>
              <filter id="tileShadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="6" stdDeviation="5" floodColor="#06101b" floodOpacity="0.42" />
              </filter>
            </defs>
            <path className="section-outline" d={outlinePath} />
            <path className="section-core" d={outlinePath} />

            {tiles.map((tile) => {
              const isSelected = selectedTile?.id === tile.id;
              return (
                <g
                  key={tile.id}
                  className={`tile-group ${isSelected ? "selected" : ""}`}
                  onClick={() => setSelectedTileId(tile.id)}
                >
                  <polygon
                    points={polygonPoints(tile)}
                    className={`tile ${tile.shape}`}
                    fill={tile.shape === "hex" ? "url(#tileGradient)" : "url(#pentGradient)"}
                    filter={isSelected ? "url(#tileShadow)" : undefined}
                  />
                  {connectorPoints(tile).map((point, index) => (
                    <circle
                      key={`${tile.id}-${index}`}
                      className="connector"
                      cx={point.x}
                      cy={point.y}
                      r={isSelected ? 3.9 : 2.4}
                    />
                  ))}
                  {isSelected && (
                    <text className="tile-label" x={tile.x} y={tile.y + 4}>
                      {tile.shape.toUpperCase()}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </section>

        <aside className="panel inspector-panel">
          <div className="panel-heading">
            <p className="eyebrow">Inspector</p>
            <h2>Selected plate</h2>
          </div>

          {selectedTile ? (
            <>
              <div className="selected-card">
                <div>
                  <span className={`shape-badge ${selectedTile.shape}`}>{selectedTile.shape}</span>
                  <h3>{selectedTile.id}</h3>
                  <p>{selectedTile.zone}</p>
                </div>
                <strong>{selectedTile.edgeLoad} kN</strong>
              </div>

              <div className="property-list">
                <p>
                  <span>Material</span>
                  <strong>{selectedTile.material}</strong>
                </p>
                <p>
                  <span>Thickness</span>
                  <strong>{selectedTile.thickness.toFixed(1)} mm</strong>
                </p>
                <p>
                  <span>Plate mass</span>
                  <strong>{formatNumber(getTileMassGrams(selectedTile))} g</strong>
                </p>
                <p>
                  <span>Connectors</span>
                  <strong>{selectedTile.shape === "hex" ? 6 : 5}</strong>
                </p>
              </div>

              <div className="edit-stack">
                <button
                  onClick={() =>
                    updateSelectedTile({ shape: selectedTile.shape === "hex" ? "pent" : "hex" })
                  }
                >
                  Convert to {selectedTile.shape === "hex" ? "pentagon" : "hexagon"}
                </button>
                <button
                  className="secondary"
                  onClick={() => updateSelectedTile({ rotation: selectedTile.rotation + Math.PI / 12 })}
                >
                  Rotate 15 degrees
                </button>
                <label>
                  Titanium grade
                  <select
                    value={selectedTile.material}
                    onChange={(event) =>
                      updateSelectedTile({ material: event.target.value as MaterialGrade })
                    }
                  >
                    <option>Ti-6Al-4V</option>
                    <option>Ti-6242</option>
                    <option>Ti-beta</option>
                  </select>
                </label>
                <label>
                  Thickness <span>{selectedTile.thickness.toFixed(1)} mm</span>
                  <input
                    min="1.2"
                    max="3.6"
                    step="0.1"
                    type="range"
                    value={selectedTile.thickness}
                    onChange={(event) => updateSelectedTile({ thickness: Number(event.target.value) })}
                  />
                </label>
              </div>

              <div className="manufacturing-note">
                <strong>Connector strategy</strong>
                <p>
                  Micro dovetail tabs are centered on every edge. Pentagons are reserved for crown,
                  flexion, and seam-relief zones where curvature changes faster than the hex lattice.
                </p>
              </div>
            </>
          ) : (
            <p>No tile is selected.</p>
          )}
        </aside>
      </section>

      <section className="panel preview-panel">
        <div>
          <p className="eyebrow">Interactive 3D model</p>
          <h2>Rotate the generated exoskeleton shell</h2>
          <p>
            The CAD generator now builds an extruded 3D model from the same hexagonal and
            pentagonal titanium tiles. Choose a 3D surface to wrap linked tiles around an arm,
            leg, torso, or helmet form, then drag to rotate, scroll to zoom, and click a plate
            to inspect or edit it.
          </p>
          <p className="surface-summary">{surfaceModes[surfaceMode].description}</p>
        </div>
        <TileModelViewer
          tiles={tiles}
          selectedTileId={selectedTile?.id ?? null}
          surfaceMode={surfaceMode}
          wrapAngle={wrapAngle}
          width={SVG_WIDTH}
          height={SVG_HEIGHT}
          onSelectTile={setSelectedTileId}
        />
      </section>
    </main>
  );
}

export default App;
