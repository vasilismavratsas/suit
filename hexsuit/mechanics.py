"""Structural, sealing and human-effort mechanics for the tiled shell.

All formulas are closed-form engineering models (Roark's Formulas for
Stress and Strain; thin-shell membrane theory), which keeps every
optimizer evaluation cheap and lets constraints stay smooth.

Load environment
----------------
The shell is an internally pressurized quilt: each tile is a small plate
carrying pressure ``p`` to its edges, the hinge lines carry the membrane
loads of the equivalent cylinder of radius ``R``:

* hoop line load      N_hoop  = p * R          (N/m)
* axial line load     N_axial = p * R / 2      (N/m)

Hinge lines between circumferential rows react the axial load; the
zig-zag geometry raises the resolved edge load by ``ZIGZAG_FACTOR``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import ZIGZAG_FACTOR, TileDesign

# Operating pressure: 29.6 kPa (4.3 psi) pure-O2, EMU-class, with the
# structural case at 1.5x max relief-valve pressure.
NOMINAL_PRESSURE = 29.6e3        # Pa
PROOF_FACTOR = 1.5
STRUCT_SF = 2.0                  # additional structural safety factor
KINEMATIC_MARGIN = 1.15          # articulation capacity over demand
FATIGUE_STRAIN_FACTOR = 3.0      # elastomer cyclic derating
GRAVITY = 9.81

# Empirical interface leak for a properly compressed elastomer face seal,
# per meter of seal line at 30 kPa differential (standard cm^3/min per m).
# Conservative value for ground-test-quality gasket joints.
INTERFACE_LEAK_SCCM_PER_M = 0.8
ALLOWABLE_LEAK_SCCM = 100.0      # whole-suit budget (make-up O2 budget)

PIN_FRICTION_MU = 0.12           # dry-film-lubed Ti pin in PEEK knuckle

# Hinge pins are always Ti-6Al-4V ground wire regardless of tile material
# (composites cannot be drawn into pins).
PIN_MATERIAL = "Ti6Al4V"


# ----------------------------------------------------------------------
# Tile plate structural response
# ----------------------------------------------------------------------

def plate_bending_stress(design: TileDesign, pressure: float) -> float:
    """Peak bending stress (Pa) in a tile under uniform pressure.

    Equivalent simply-supported circular plate (hinged edges cannot carry
    moment):  sigma = 3(3+nu)/8 * p * (a/t)^2   [Roark, Table 11.2 case 10a].
    """
    a = design.equivalent_radius
    nu = design.mat.poisson
    return 3.0 * (3.0 + nu) / 8.0 * pressure * (a / design.thickness) ** 2


def plate_deflection(design: TileDesign, pressure: float) -> float:
    """Center deflection (m) of the simply-supported equivalent plate."""
    a = design.equivalent_radius
    e, nu, t = design.mat.youngs_modulus, design.mat.poisson, design.thickness
    d_stiff = e * t**3 / (12.0 * (1.0 - nu**2))
    return (5.0 + nu) / (1.0 + nu) * pressure * a**4 / (64.0 * d_stiff)


# ----------------------------------------------------------------------
# Hinge line loads and pin / knuckle sizing
# ----------------------------------------------------------------------

def hinge_line_load(pressure: float, shell_radius: float) -> float:
    """Design tensile load per unit hinge length (N/m).

    Axial membrane load of the pressure cylinder, resolved onto the
    +/-30 deg zig-zag edges.
    """
    return pressure * shell_radius / 2.0 * ZIGZAG_FACTOR


@dataclass
class PinSizing:
    """Sized hinge-pin and knuckle results (SI units)."""

    pin_diameter: float
    knuckle_pitch: float
    knuckle_width: float
    knuckle_wall: float
    pin_shear_stress: float
    bearing_stress: float
    load_per_knuckle: float


def size_hinge_pin(design: TileDesign, pressure: float, shell_radius: float,
                   n_knuckles: int = 5) -> PinSizing:
    """Size the piano-hinge pin and knuckles on one tile edge.

    The edge of length ``s`` carries ``w = hinge_line_load`` (N/m). With
    ``n`` interleaved knuckles the pin sees the edge load in multi-shear;
    worst single shear plane carries ``F = w*s / (n-1)``.
    """
    from .materials import MATERIALS

    s = design.side_length
    w = hinge_line_load(pressure, shell_radius) * PROOF_FACTOR
    f_edge = w * s
    f_plane = f_edge / max(1, n_knuckles - 1)

    tau_allow = MATERIALS[PIN_MATERIAL].shear_strength / STRUCT_SF
    d_req = math.sqrt(4.0 * f_plane / (math.pi * tau_allow))
    pin_d = max(d_req, 1.0e-3, design.thickness * 0.45)
    pin_d = min(pin_d, design.thickness * 0.8)   # must hide inside edge

    tau = 4.0 * (f_edge / max(1, n_knuckles - 1)) / (math.pi * pin_d**2)

    knuckle_pitch = s / n_knuckles
    knuckle_width = 0.85 * knuckle_pitch          # 15% clearance
    bearing = f_edge / n_knuckles / (pin_d * knuckle_width)
    knuckle_wall = max(0.7 * pin_d, 0.8e-3)

    return PinSizing(
        pin_diameter=pin_d,
        knuckle_pitch=knuckle_pitch,
        knuckle_width=knuckle_width,
        knuckle_wall=knuckle_wall,
        pin_shear_stress=tau,
        bearing_stress=bearing,
        load_per_knuckle=f_edge / n_knuckles,
    )


# ----------------------------------------------------------------------
# Kinematics: articulation demand vs. capacity
# ----------------------------------------------------------------------

def required_hinge_angle_deg(design: TileDesign, flex_zone_length: float,
                             required_rom_deg: float) -> float:
    """Rotation each hinge line must deliver (deg), incl. zig-zag penalty."""
    rows = design.hinge_rows_in(flex_zone_length)
    return required_rom_deg / rows * ZIGZAG_FACTOR


MAX_HINGE_ANGLE_DEG = 25.0   # anti-pinch / smoothness design rule per line


def hinge_angle_capacity_deg(design: TileDesign) -> float:
    """Kinematic articulation limit of one hinge line (deg).

    Pivot on the outer surface; both mating edge faces carry a
    ``bevel_deg`` chamfer. The joint closes until the chamfered inner
    corners meet: each face rotates ``bevel + atan(g/2 / t)`` before
    contact, so the stop is at twice that.
    """
    gap_term = math.degrees(math.atan2(design.gap / 2.0, design.thickness))
    return 2.0 * design.bevel_deg + 2.0 * gap_term


def flex_protrusion(design: TileDesign, hinge_angle_deg: float) -> float:
    """Extra radial excursion of a tile mid-span when the quilt is bent (m).

    When each hinge line kinks by theta, the flat facets chord across the
    bent surface; the facet midpoint stands proud of the smooth bend by
    ~ (axial_pitch / 2) * tan(theta / 2). This drives clearance from the
    body on the concave side and bulk on the convex side.
    """
    theta = math.radians(min(abs(hinge_angle_deg), 175.0))
    return (design.axial_pitch / 2.0) * math.tan(theta / 2.0)


# ----------------------------------------------------------------------
# Seal mechanics
# ----------------------------------------------------------------------

SEAL_E_EFF = 3.0e6   # Pa, effective elastomer membrane modulus


def seal_chord(design: TileDesign, hinge_angle_deg: float) -> float:
    """Inner-face gap the seal web must span at a given articulation (m).

    The pin pivot is at the OUTER surface, so rotating by theta opens the
    inner faces by ~ t * theta on top of the nominal gap.
    """
    theta = math.radians(abs(hinge_angle_deg))
    return design.gap + design.thickness * theta


def seal_peak_strain(design: TileDesign, hinge_angle_deg: float,
                     pressure: float) -> float:
    """Peak membrane strain in the bellows web over one flex cycle.

    Two regimes for a web of free length ``L`` spanning chord ``c``:

    * **Taut** (c >= L): the web is stretched geometrically by (c-L)/L
      and pressure tension adds on top.
    * **Slack** (c < L): pressure inflates the web into a circular arc of
      radius r; membrane stress p*r/t_w gives strain sigma/E. More slack
      -> deeper bulge -> smaller r -> LOWER strain, so the optimizer is
      rewarded for leaving slack in the seal, exactly as a real bellows.

    Evaluated at the worst (fully articulated) chord.
    """
    c = seal_chord(design, hinge_angle_deg)
    length = max(design.seal_free_length, 1e-6)
    tw = design.seal_mat.min_web_thickness

    if c >= length:
        geometric = (c - length) / length
        pressure_term = pressure * (c / 2.0) / (tw * SEAL_E_EFF)
        return geometric + pressure_term

    # Slack: arc length L over chord c -> sagitta h, arc radius r.
    slack = length - c
    h = max(math.sqrt(3.0 * c * slack / 8.0), tw)
    r = c**2 / (8.0 * h) + h / 2.0
    return pressure * r / (tw * SEAL_E_EFF)


def permeation_leak_sccm(design: TileDesign, total_edge_length: float,
                         pressure: float) -> float:
    """Gas permeation through all seal webs (standard cm^3/min)."""
    k = design.seal_mat.permeability_coeff
    web_t = design.seal_mat.min_web_thickness
    area = total_edge_length * design.gap  # exposed web area
    q_m3s = k * area * pressure / web_t
    return q_m3s * 1e6 * 60.0


def interface_leak_sccm(total_edge_length: float) -> float:
    """Empirical seepage along bonded seal-to-tile interfaces (sccm)."""
    return INTERFACE_LEAK_SCCM_PER_M * total_edge_length


# ----------------------------------------------------------------------
# Human effort: torque to articulate a pressurized hinge row
# ----------------------------------------------------------------------

def hinge_row_torque(design: TileDesign, pressure: float,
                     shell_radius: float) -> float:
    """Torque (N*m) a person must apply to rotate one full hinge row by
    its working angle, per meter of hinge line, times the row length.

    Three contributions:
      1. Pin friction: mu * N_line * r_pin  (per meter), N_line is the
         axial membrane load clamping the knuckles.
      2. Pressure-volume work: the pivot sits at the *outer* surface, so
         closing the joint compresses gas in the wedge between bevel
         faces; effective moment arm ~ t/2 over the gap area.
      3. Seal elastic stiffness: strain energy in the stretched web,
         linearized (small vs. the other two for thin webs).
    Returned as torque per hinge row around the full circumference.
    """
    row_length = 2.0 * math.pi * shell_radius * ZIGZAG_FACTOR
    n_line = hinge_line_load(pressure, shell_radius)
    pin = size_hinge_pin(design, pressure, shell_radius)

    t_friction = PIN_FRICTION_MU * n_line * (pin.pin_diameter / 2.0)
    t_pressure = pressure * design.gap * (design.thickness / 2.0)
    # Seal web ~ linear spring: k = E_eff * tw / L, E_eff ~ 3 MPa elastomer.
    e_eff = 3.0e6
    tw = design.seal_mat.min_web_thickness
    k_seal = e_eff * tw / max(design.seal_free_length, 1e-6)
    t_seal = k_seal * design.thickness**2 / 2.0

    return (t_friction + t_pressure + t_seal) * row_length


def joint_torque(design: TileDesign, pressure: float, shell_radius: float,
                 flex_zone_length: float) -> float:
    """Peak operator torque (N*m) to flex the whole joint.

    Rows articulate sequentially in a well-designed quilt, but
    conservatively assume 40% of rows move simultaneously.
    """
    rows = design.hinge_rows_in(flex_zone_length)
    simultaneous = max(1.0, 0.4 * rows)
    return hinge_row_torque(design, pressure, shell_radius) * simultaneous


# ----------------------------------------------------------------------
# Mass accounting
# ----------------------------------------------------------------------

def areal_mass(design: TileDesign, pressure: float, shell_radius: float) -> float:
    """Shell mass per unit area (kg/m^2): tile + hinge hardware + seal."""
    from .materials import MATERIALS

    tile = design.mat.density * design.thickness
    pin = size_hinge_pin(design, pressure, shell_radius)
    edge_per_area = design.edge_length_per_area()

    pin_lin = MATERIALS[PIN_MATERIAL].density * math.pi * (
        pin.pin_diameter / 2.0) ** 2
    # Knuckle barrels: annulus around the pin, ~85% edge coverage.
    r_out = pin.pin_diameter / 2.0 + pin.knuckle_wall
    knuckle_lin = design.mat.density * 0.85 * math.pi * (
        r_out**2 - (pin.pin_diameter / 2.0) ** 2)
    seal_lin = design.seal_mat.density * design.seal_mat.min_web_thickness * (
        design.seal_free_length + 8.0e-3)  # web + two bonded flanges

    return tile + (pin_lin + knuckle_lin + seal_lin) * edge_per_area
