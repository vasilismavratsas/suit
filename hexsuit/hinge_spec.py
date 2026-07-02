"""Exact hinge + seal mechanism specification generator.

Mechanism: **outer-pivot interleaved piano hinge with a self-energizing
dual seal** ("clamshell knuckle joint"). One spec is generated per body
region from its optimized tile design, with every dimension resolved.

How it works
------------
1.  Each of the six edges of every tile carries machined/molded hinge
    knuckles; adjacent tiles interleave and are joined by a straight pin
    per edge. The pin axis sits at the OUTER surface of the shell, so
    when the joint articulates the outer skin length is preserved and the
    enclosed gas volume change is nearly zero -- the joint is close to
    volume-neutral and pressure does not fight the astronaut.
2.  The inner half of each mating edge face is chamfered by the optimized
    bevel angle. The joint articulates until the chamfer lands touch,
    giving a hard kinematic stop of 2 x bevel per hinge line.
3.  PRIMARY SEAL: a molded elastomer bellows web runs continuously along
    every hinge line on the pressure (inner) side. Its edges are dovetail
    keys that lock into grooves in each tile and are adhesive-bonded.
    Internal pressure presses the web into the groove seats, so the seal
    is self-energizing: higher pressure seals tighter.
4.  SECONDARY SEAL: an elastomer cord sits in a half-round gland along
    the bevel land; it is compressed whenever the joint is near straight,
    giving redundancy over most of the duty cycle.
5.  VERTICES: three hinge lines meet at each hexagon corner. A molded
    tri-lobe boot (same elastomer, co-molded with the three webs) covers
    the triple point; pins stop one knuckle-pitch short of the vertex so
    boots have a land to bond to.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import mechanics as mech
from .body import BodyRegion
from .evaluate import DesignEvaluation
from .geometry import TileDesign


@dataclass
class HingeSpec:
    """Fully-dimensioned hinge/seal mechanism for one region (mm unless noted)."""

    region: str
    mechanism: str = "outer-pivot interleaved piano hinge, dual self-energizing seal"

    # hinge hardware
    pin_diameter: float = 0.0
    pin_material: str = ""
    pin_coating: str = "sputtered MoS2 dry-film lubricant, 8-12 um"
    knuckles_per_edge: int = 0
    knuckle_pitch: float = 0.0
    knuckle_width: float = 0.0
    knuckle_od: float = 0.0
    knuckle_bore_fit: str = ""
    edge_length: float = 0.0
    bevel_deg: float = 0.0
    articulation_stop_deg: float = 0.0

    # primary bellows seal
    seal_material: str = ""
    web_thickness: float = 0.0
    web_free_length: float = 0.0
    dovetail_width: float = 0.0
    dovetail_depth: float = 0.0
    dovetail_angle_deg: float = 15.0
    bond: str = "EA9309NA epoxy, primed with Chemlok 250"

    # secondary cord seal
    cord_diameter: float = 0.0
    gland_width: float = 0.0
    gland_depth: float = 0.0
    cord_squeeze_pct: float = 0.0

    # loads / verification numbers
    line_load_n_per_m: float = 0.0
    pin_shear_mpa: float = 0.0
    bearing_mpa: float = 0.0
    seal_peak_strain_pct: float = 0.0
    predicted_leak_sccm: float = 0.0

    assembly_notes: list[str] = field(default_factory=list)


def build_hinge_spec(ev: DesignEvaluation, region: BodyRegion,
                     pressure: float = mech.NOMINAL_PRESSURE) -> HingeSpec:
    """Resolve every mechanism dimension from an evaluated design."""
    d: TileDesign = ev.design
    r_shell = d.shell_radius(region.limb_radius)
    pin = mech.size_hinge_pin(d, pressure, r_shell)
    mm = 1e3

    web_t = max(d.seal_mat.min_web_thickness, d.thickness * 0.25)
    dovetail_w = max(2.5 * web_t, 1.5e-3)
    dovetail_d = 1.2 * dovetail_w

    cord_d = max(1.0e-3, 0.5 * d.thickness)
    squeeze = 0.22
    gland_w = 1.35 * cord_d
    gland_d = cord_d * (1.0 - squeeze)

    spec = HingeSpec(
        region=region.name,
        pin_diameter=round(pin.pin_diameter * mm, 2),
        pin_material=f"{mech.PIN_MATERIAL} (drawn wire, centerless ground)",
        knuckles_per_edge=5,
        knuckle_pitch=round(pin.knuckle_pitch * mm, 2),
        knuckle_width=round(pin.knuckle_width * mm, 2),
        knuckle_od=round((pin.pin_diameter + 2 * pin.knuckle_wall) * mm, 2),
        knuckle_bore_fit="H7/g6 running fit, bore honed",
        edge_length=round(d.side_length * mm, 2),
        bevel_deg=round(d.bevel_deg, 1),
        articulation_stop_deg=round(ev.capacity_hinge_deg, 1),
        seal_material=(f"{d.seal} rubber, {d.seal_mat.shore_a} Shore A, "
                       f"molded continuous perimeter web"),
        web_thickness=round(web_t * mm, 2),
        web_free_length=round(d.seal_free_length * mm, 2),
        dovetail_width=round(dovetail_w * mm, 2),
        dovetail_depth=round(dovetail_d * mm, 2),
        cord_diameter=round(cord_d * mm, 2),
        gland_width=round(gland_w * mm, 2),
        gland_depth=round(gland_d * mm, 2),
        cord_squeeze_pct=round(squeeze * 100.0, 0),
        line_load_n_per_m=round(mech.hinge_line_load(pressure, r_shell), 1),
        pin_shear_mpa=round(ev.pin_shear / 1e6, 1),
        bearing_mpa=round(ev.bearing / 1e6, 1),
        seal_peak_strain_pct=round(ev.seal_strain * 100.0, 1),
        predicted_leak_sccm=round(ev.leak_sccm, 3),
    )
    spec.assembly_notes = [
        f"Pin axis on outer mold line, {round(d.thickness * mm, 2)} mm above "
        f"mid-plane: articulation is volume-neutral, pressure torque ~0.",
        f"Chamfer both inner edge faces at {spec.bevel_deg} deg; hard stop at "
        f"{spec.articulation_stop_deg} deg per hinge line "
        f"(requirement {round(ev.required_hinge_deg, 1)} deg incl. zig-zag).",
        "Pins stop one knuckle-pitch short of each hexagon vertex; bond the "
        "tri-lobe vertex boot over the triple point before pin insertion.",
        "Bellows web is molded as one continuous hexagonal perimeter ring per "
        "tile and dovetail-locked + bonded; pressure self-energizes the seat.",
        "Install secondary cord seal with silicone-free grease; verify "
        f"{spec.cord_squeeze_pct:.0f}% squeeze with feeler gauge at 3 points.",
        "Proof test each closed segment at 1.5x operating pressure; accept if "
        "decay < 0.5% over 30 min.",
    ]
    return spec


def spec_to_markdown(spec: HingeSpec) -> str:
    """Render one spec as a markdown block for the design report."""
    rows = [
        ("Mechanism", spec.mechanism),
        ("Hinge pin diameter", f"{spec.pin_diameter} mm, {spec.pin_material}"),
        ("Pin coating", spec.pin_coating),
        ("Knuckles per edge", f"{spec.knuckles_per_edge} interleaved (3+2), "
                              f"pitch {spec.knuckle_pitch} mm, "
                              f"width {spec.knuckle_width} mm, "
                              f"OD {spec.knuckle_od} mm"),
        ("Knuckle bore fit", spec.knuckle_bore_fit),
        ("Edge (hinge line) length", f"{spec.edge_length} mm"),
        ("Edge bevel", f"{spec.bevel_deg} deg per face -> hard stop at "
                       f"{spec.articulation_stop_deg} deg/hinge"),
        ("Primary seal", spec.seal_material),
        ("Seal web", f"{spec.web_thickness} mm thick x "
                     f"{spec.web_free_length} mm free length"),
        ("Dovetail groove", f"{spec.dovetail_width} mm wide x "
                            f"{spec.dovetail_depth} mm deep, "
                            f"{spec.dovetail_angle_deg} deg flank"),
        ("Seal bond", spec.bond),
        ("Secondary cord seal", f"{spec.cord_diameter} mm cord in "
                                f"{spec.gland_width} x {spec.gland_depth} mm "
                                f"gland, {spec.cord_squeeze_pct:.0f}% squeeze"),
        ("Hinge line load", f"{spec.line_load_n_per_m} N/m (proof)"),
        ("Pin shear stress", f"{spec.pin_shear_mpa} MPa"),
        ("Knuckle bearing stress", f"{spec.bearing_mpa} MPa"),
        ("Seal peak cyclic strain", f"{spec.seal_peak_strain_pct}%"),
        ("Predicted region leak", f"{spec.predicted_leak_sccm} sccm"),
    ]
    lines = [f"#### {spec.region.title()} hinge & seal specification", "",
             "| Item | Specification |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    lines += ["", "**Assembly / verification notes**", ""]
    lines += [f"{i}. {note}" for i, note in enumerate(spec.assembly_notes, 1)]
    return "\n".join(lines)
