"""Anthropometric model: body regions the tiled shell must cover.

Each region carries the geometry (limb radius, coverage area, length of
the flexing zone) and the mobility requirement (range of motion that the
tiled surface must absorb) that drive tile sizing.

ROM numbers follow NASA-STD-3001 / Man-Systems Integration Standards
functional-mobility values for a pressurized EVA suit (which are lower
than nude-body ROM: the suit only needs to support the *working* range).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BodyRegion:
    """A patch of body surface tiled with one uniform tile design.

    Attributes:
        name: human-readable region label.
        limb_radius: local surface radius of curvature (m). The tiles must
            approximate this cylinder, which limits how wide a flat tile
            may be before it stands off the body too far.
        flex_zone_length: axial length of the band over which the joint's
            bending is distributed (m). More tile rows in this band means
            less bend demanded from each hinge line.
        required_rom_deg: total articulation (degrees) the tiled band must
            provide about the joint axis while suited and pressurized.
        cycles_per_eva: expected flex cycles in one 8 h EVA (fatigue driver).
        area: total shell surface area of the region (m^2), for mass and
            leak-length accounting.
        standoff_budget: max allowed gap between flat tile face and the
            body cylinder (m); a comfort/bulk constraint.
    """

    name: str
    limb_radius: float
    flex_zone_length: float
    required_rom_deg: float
    cycles_per_eva: int
    area: float
    standoff_budget: float = 0.012

    @property
    def circumference(self) -> float:
        import math

        return 2.0 * math.pi * self.limb_radius


def default_body() -> list[BodyRegion]:
    """50th-percentile male crew member, suited functional-mobility targets."""
    return [
        # Torso barely articulates in hard suits; big radius, small ROM.
        BodyRegion("torso", limb_radius=0.155, flex_zone_length=0.30,
                   required_rom_deg=30.0, cycles_per_eva=500, area=0.55,
                   standoff_budget=0.018),
        BodyRegion("shoulder", limb_radius=0.075, flex_zone_length=0.16,
                   required_rom_deg=120.0, cycles_per_eva=2000, area=0.14),
        BodyRegion("elbow", limb_radius=0.048, flex_zone_length=0.14,
                   required_rom_deg=120.0, cycles_per_eva=4000, area=0.09),
        BodyRegion("wrist", limb_radius=0.032, flex_zone_length=0.07,
                   required_rom_deg=70.0, cycles_per_eva=8000, area=0.035,
                   standoff_budget=0.008),
        BodyRegion("hip", limb_radius=0.090, flex_zone_length=0.18,
                   required_rom_deg=90.0, cycles_per_eva=1500, area=0.20),
        BodyRegion("knee", limb_radius=0.060, flex_zone_length=0.16,
                   required_rom_deg=110.0, cycles_per_eva=3000, area=0.12),
        BodyRegion("ankle", limb_radius=0.045, flex_zone_length=0.09,
                   required_rom_deg=45.0, cycles_per_eva=3000, area=0.05,
                   standoff_budget=0.010),
    ]
