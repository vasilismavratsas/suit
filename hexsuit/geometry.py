"""Hexagonal tile geometry and tiling-on-a-cylinder relations.

Convention
----------
Tiles are *flat-top* hexagons laid in circumferential rows around a limb.
``width_af`` is the across-flats dimension measured **axially** (along the
limb), so consecutive rows repeat with axial pitch ``width_af + gap`` and
every axial step crosses exactly one zig-zag hinge line.  ``aspect``
stretches the hexagon circumferentially: ``hoop_width = aspect * width_af``.
A regular hexagon has ``aspect == 1``.

The zig-zag hinge lines between rows are made of edges inclined +/-30 deg
from the hoop direction, so bending the band about the joint axis demands
``1/cos(30 deg)`` more rotation from each hinge than the row-level bend
angle (the ``ZIGZAG_FACTOR``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .materials import MATERIALS, SEAL_MATERIALS, Material, SealMaterial

SQRT3 = math.sqrt(3.0)
ZIGZAG_FACTOR = 1.0 / math.cos(math.radians(30.0))  # ~1.1547


@dataclass
class TileDesign:
    """One uniform tile + hinge + seal design for a body region.

    Attributes:
        width_af: hexagon width across flats, axial direction (m).
        aspect: hoop-to-axial stretch ratio of the hexagon (1 = regular).
        thickness: structural shell thickness of the tile (m).
        bevel_deg: chamfer angle machined on each mating edge face (deg).
            Adjacent bevels sum, so kinematic articulation limit = 2*bevel.
        seal_free_length: unstretched free web length of the bellows seal
            spanning each hinge line (m).
        gap: nominal inter-tile gap at the hinge line (m).
        material: tile/hinge structural material key into MATERIALS.
        seal: elastomer key into SEAL_MATERIALS.
    """

    width_af: float
    aspect: float
    thickness: float
    bevel_deg: float
    seal_free_length: float
    gap: float = 1.5e-3
    material: str = "Ti6Al4V"
    seal: str = "butyl"

    # --- resolved objects -------------------------------------------------
    @property
    def mat(self) -> Material:
        return MATERIALS[self.material]

    @property
    def seal_mat(self) -> SealMaterial:
        return SEAL_MATERIALS[self.seal]

    # --- single-tile geometry --------------------------------------------
    @property
    def hoop_width(self) -> float:
        """Across-flats dimension in the circumferential direction (m)."""
        return self.aspect * self.width_af

    @property
    def side_length(self) -> float:
        """Edge length of the (possibly stretched) hexagon (m)."""
        # Regular-hex side scaled by mean stretch; adequate for aspect 0.6-1.8.
        return (self.width_af / SQRT3) * (1.0 + self.aspect) / 2.0

    @property
    def face_area(self) -> float:
        """Plan area of one tile face (m^2)."""
        return (SQRT3 / 2.0) * self.width_af**2 * self.aspect

    @property
    def perimeter(self) -> float:
        return 6.0 * self.side_length

    @property
    def equivalent_radius(self) -> float:
        """Radius of the equal-area circular plate (for Roark formulas)."""
        return math.sqrt(self.face_area / math.pi)

    # --- tiling relations --------------------------------------------------
    @property
    def axial_pitch(self) -> float:
        """Axial distance between successive hinge rows (m)."""
        return self.width_af + self.gap

    def hinge_rows_in(self, flex_zone_length: float) -> int:
        """Number of zig-zag hinge lines inside a joint's flex band."""
        return max(1, int(math.floor(flex_zone_length / self.axial_pitch)))

    def standoff(self, limb_radius: float) -> float:
        """Chord standoff of a flat tile face over the body cylinder (m).

        h = R * (1 - cos(c / 2R)) with c the hoop chord of one tile.
        """
        half_angle = self.hoop_width / (2.0 * limb_radius)
        half_angle = min(half_angle, math.pi / 2.0)
        return limb_radius * (1.0 - math.cos(half_angle))

    def shell_radius(self, limb_radius: float) -> float:
        """Effective pressure-shell radius: body + comfort liner + standoff."""
        liner = 6.0e-3  # thermal/comfort liner between skin and shell
        return limb_radius + liner + self.standoff(limb_radius) + self.thickness / 2.0

    def edge_length_per_area(self) -> float:
        """Shared hinge-line length per unit shell area (1/m).

        Hex grid: each tile owns half of its perimeter -> 3*s / A.
        """
        return 3.0 * self.side_length / self.face_area

    def tiles_per_area(self) -> float:
        return 1.0 / self.face_area

    def as_dict(self) -> dict:
        return {
            "width_across_flats_mm": self.width_af * 1e3,
            "hoop_width_mm": self.hoop_width * 1e3,
            "aspect": self.aspect,
            "thickness_mm": self.thickness * 1e3,
            "bevel_deg": self.bevel_deg,
            "seal_free_length_mm": self.seal_free_length * 1e3,
            "gap_mm": self.gap * 1e3,
            "material": self.material,
            "seal": self.seal,
        }
