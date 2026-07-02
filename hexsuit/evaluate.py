"""Full design evaluation: every constraint and objective for one region."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import mechanics as mech
from .body import BodyRegion
from .geometry import TileDesign
from .materials import MATERIALS

MAX_JOINT_TORQUE = 12.0        # N*m sustained one-hand effort (NASA-STD-3001)
MAX_DEFLECTION_RATIO = 0.02    # tile center deflection / width
MAX_BEVEL_DEG = 35.0           # deeper chamfers knife-edge the seal land


@dataclass
class DesignEvaluation:
    """All computed responses and constraint margins for one design.

    Constraint margins are normalized: ``margin >= 0`` means satisfied,
    magnitude is fractional headroom.
    """

    region: str
    design: TileDesign

    # responses
    tile_stress: float = 0.0
    tile_deflection: float = 0.0
    pin_shear: float = 0.0
    bearing: float = 0.0
    required_hinge_deg: float = 0.0
    capacity_hinge_deg: float = 0.0
    flex_protrusion: float = 0.0
    seal_strain: float = 0.0
    standoff: float = 0.0
    leak_sccm: float = 0.0
    joint_torque: float = 0.0
    areal_mass: float = 0.0
    region_mass: float = 0.0
    n_rows: int = 0
    n_tiles: int = 0
    edge_length: float = 0.0

    margins: dict[str, float] = field(default_factory=dict)

    @property
    def feasible(self) -> bool:
        return all(m >= 0.0 for m in self.margins.values())

    @property
    def worst_margin(self) -> float:
        return min(self.margins.values())


def evaluate_design(design: TileDesign, region: BodyRegion,
                    pressure: float = mech.NOMINAL_PRESSURE) -> DesignEvaluation:
    """Compute all responses and constraint margins for one region design."""
    p_struct = pressure * mech.PROOF_FACTOR
    r_shell = design.shell_radius(region.limb_radius)
    mat = design.mat

    ev = DesignEvaluation(region=region.name, design=design)

    # --- structure ---------------------------------------------------------
    ev.tile_stress = mech.plate_bending_stress(design, p_struct)
    ev.tile_deflection = mech.plate_deflection(design, pressure)
    pin = mech.size_hinge_pin(design, pressure, r_shell)
    ev.pin_shear = pin.pin_shear_stress
    ev.bearing = pin.bearing_stress

    # --- kinematics ----------------------------------------------------------
    ev.n_rows = design.hinge_rows_in(region.flex_zone_length)
    ev.required_hinge_deg = mech.required_hinge_angle_deg(
        design, region.flex_zone_length, region.required_rom_deg)
    ev.capacity_hinge_deg = mech.hinge_angle_capacity_deg(design)
    ev.flex_protrusion = mech.flex_protrusion(design, ev.required_hinge_deg)

    # --- sealing -------------------------------------------------------------
    working_angle = min(ev.required_hinge_deg, ev.capacity_hinge_deg)
    ev.seal_strain = mech.seal_peak_strain(design, working_angle, pressure)
    ev.edge_length = design.edge_length_per_area() * region.area
    ev.leak_sccm = (mech.permeation_leak_sccm(design, ev.edge_length, pressure)
                    + mech.interface_leak_sccm(ev.edge_length))

    # --- ergonomics ------------------------------------------------------------
    ev.standoff = design.standoff(region.limb_radius)
    ev.joint_torque = mech.joint_torque(design, pressure, r_shell,
                                        region.flex_zone_length)

    # --- mass ------------------------------------------------------------------
    ev.areal_mass = mech.areal_mass(design, pressure, r_shell)
    ev.region_mass = ev.areal_mass * region.area
    ev.n_tiles = round(design.tiles_per_area() * region.area)

    # --- normalized constraint margins (>= 0 is pass) ---------------------------
    allow = mat.yield_strength / mech.STRUCT_SF
    seal_allow = design.seal_mat.max_service_strain / mech.FATIGUE_STRAIN_FACTOR
    # Whole-suit leak budget apportioned by region area (7 regions, ~1.2 m^2).
    leak_allow = mech.ALLOWABLE_LEAK_SCCM * (region.area / 1.20)

    ev.margins = {
        "tile_stress": 1.0 - ev.tile_stress / allow,
        "tile_deflection": 1.0 - ev.tile_deflection / (
            MAX_DEFLECTION_RATIO * design.width_af),
        "pin_shear": 1.0 - ev.pin_shear / (
            MATERIALS[mech.PIN_MATERIAL].shear_strength / mech.STRUCT_SF),
        "bearing": 1.0 - ev.bearing / (1.5 * allow),
        "articulation": ev.capacity_hinge_deg / (
            ev.required_hinge_deg * mech.KINEMATIC_MARGIN) - 1.0,
        "seal_strain": 1.0 - ev.seal_strain / seal_allow,
        "standoff": 1.0 - ev.standoff / region.standoff_budget,
        "leak": 1.0 - ev.leak_sccm / leak_allow,
        "torque": 1.0 - ev.joint_torque / MAX_JOINT_TORQUE,
        "bevel": 1.0 - design.bevel_deg / MAX_BEVEL_DEG,
        # Smoothness rule: no single hinge line may kink more than the
        # anti-pinch limit even if the bevel would kinematically allow it.
        "hinge_kink": 1.0 - ev.required_hinge_deg / mech.MAX_HINGE_ANGLE_DEG,
        # Bent-quilt faceting must not eat the body-clearance budget.
        "flex_pinch": 1.0 - ev.flex_protrusion / region.standoff_budget,
        "min_thickness": design.thickness / mat.min_thickness - 1.0,
        # Tile must be wide enough to host >= 3 knuckles of >= 3 mm each.
        "manufacturable_edge": design.side_length / 9.0e-3 - 1.0,
    }
    return ev
