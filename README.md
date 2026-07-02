# hexsuit

Design-optimization software for a space suit shell built from repeated
**hexagonal tiles** that hinge together: it sizes the tiles (width, shape,
thickness), verifies that a human can move inside the pressurized shell, and
generates an exact, fully-dimensioned specification for the hinge-and-seal
mechanism that joins the tiles while holding suit pressure with negligible
leakage.

## What it does

For each body region (torso, shoulder, elbow, wrist, hip, knee, ankle) the
optimizer searches over five design variables per tile pattern:

| Variable | Meaning | Bounds |
| --- | --- | --- |
| `width_af` | hexagon width across flats, along the limb | 15–120 mm |
| `aspect` | circumferential stretch of the hexagon (1 = regular) | 0.6–1.8 |
| `thickness` | structural shell thickness | 0.6–8 mm |
| `bevel_deg` | edge chamfer that sets the articulation hard-stop | 2–35° |
| `seal_free_length` | slack length of the bellows seal web | 1.5–20 mm |

subject to 14 constraints covering **structure** (plate bending stress and
deflection under 1.5× proof pressure, hinge-pin shear, knuckle bearing),
**mobility** (per-hinge articulation capacity ≥ demand for the region's
required range of motion, ≤ 25° kink per hinge line, faceting must not pinch
the body), **sealing** (elastomer fatigue strain, whole-suit leak budget of
100 sccm from permeation + interface seepage), and **ergonomics** (≤ 12 N·m
joint torque, standoff bulk, manufacturability floors). The objective is
minimum shell mass with a small torque penalty, solved by differential
evolution plus a Nelder–Mead polish for each candidate material
(Al 7075-T6, Ti-6Al-4V, quasi-isotropic CFRP, PEEK-CF30).

## The hinge/seal mechanism it dimensions

An **outer-pivot interleaved piano hinge with a dual self-energizing seal**:

1. **Piano hinge, pin on the outer mold line** — each hexagon edge carries 5
   interleaved knuckles joined by a ground pin. Putting the pivot at the
   outer surface makes articulation nearly volume-neutral, so pressure does
   not fight the wearer (the classic hard-suit "constant-volume joint" trick).
2. **Beveled edge faces** — the inner half of each mating face is chamfered
   by the optimized bevel; the joint articulates until the chamfer lands
   touch, giving a hard kinematic stop of 2×bevel (+ gap term) per hinge line.
3. **Primary seal: molded elastomer bellows web** (butyl by default) running
   continuously along every hinge line on the pressure side, dovetail-keyed
   and bonded into each tile. Internal pressure presses the web into its
   seats — the seal gets *tighter* with pressure. Slack in the web is a
   design variable, so flexing never over-strains it.
4. **Secondary seal: compressed cord** in a half-round gland on the bevel
   land, redundant coverage while the joint is near straight.
5. **Vertex boots** — tri-lobe molded boots cover the triple points where
   three hinge lines meet; pins stop one knuckle-pitch short of each vertex.

The generated report resolves every dimension (pin Ø, knuckle pitch/width/OD,
bore fit, chamfer angle, web thickness/free length, dovetail groove, cord Ø,
gland size and squeeze), predicts leak rate and pin stresses per region, and
lists assembly/verification steps including the 1.5× proof-pressure decay
test.

## Install & run

```bash
pip install -r requirements.txt
python -m hexsuit -o output --json          # full suit, all materials
python -m hexsuit -r elbow knee -m Ti6Al4V  # subset, one material
python -m hexsuit -p 57.2                   # 8.3 psi exploration-suit pressure
```

Outputs in `output/`:

- `design_report.md` — full design report: optimized tile table, constraint
  margins, per-region hinge & seal specifications, figures.
- `figures/` — hinge cross-section drawings (straight + articulated), 3D
  tiled-limb renders (straight + flexed), tile-width trade studies, and a
  suit-level overview chart.
- `results.json` — machine-readable designs, margins and hinge specs.

## Testing

```bash
python -m pytest tests/ -q
```

22 tests cover geometry identities against hand calculations, Roark plate
formulas, load/leak scaling laws, constraint activation, optimizer
feasibility, and hinge-spec consistency.

## Model fidelity notes

Closed-form engineering models (Roark plate bending, thin-shell membrane
loads, membrane seal mechanics) keep each optimizer evaluation ~1 ms, so the
global search over 4 materials × 7 regions runs in ~30 s. The report lists
the modeling limitations (thermal derating, MMOD layers, vertex-boot molding
details are out of scope of this sizing pass).
