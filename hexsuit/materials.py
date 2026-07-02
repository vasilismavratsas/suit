"""Material property database for tile shells, hinge pins and seals.

Values are room-temperature handbook numbers (SI units). A space-rated
design would derate for the -120 C .. +120 C thermal environment; the
optimizer applies a global safety factor on top of these to cover that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    """Structural material for tiles and hinge hardware."""

    name: str
    density: float          # kg/m^3
    youngs_modulus: float   # Pa
    yield_strength: float   # Pa
    shear_strength: float   # Pa (ultimate shear, ~0.6 * yield for metals)
    poisson: float
    min_thickness: float    # m, manufacturable floor (machining / molding)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.name


@dataclass(frozen=True)
class SealMaterial:
    """Elastomer used for the inter-tile bellows seal and face gaskets."""

    name: str
    density: float                 # kg/m^3
    permeability_coeff: float      # m^2/s/Pa  (gas permeation coefficient K)
    max_service_strain: float      # allowable cyclic strain (fraction)
    shore_a: int
    min_web_thickness: float       # m, thinnest moldable seal web

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.name


MATERIALS: dict[str, Material] = {
    # Aerospace aluminium: cheap baseline, good stiffness/weight.
    "Al7075-T6": Material(
        name="Al7075-T6",
        density=2810.0,
        youngs_modulus=71.7e9,
        yield_strength=503e6,
        shear_strength=331e6,
        poisson=0.33,
        min_thickness=0.8e-3,
    ),
    # Ti-6Al-4V: best strength at temperature, used on hard-suit joints (AX-5).
    "Ti6Al4V": Material(
        name="Ti6Al4V",
        density=4430.0,
        youngs_modulus=113.8e9,
        yield_strength=880e6,
        shear_strength=550e6,
        poisson=0.342,
        min_thickness=0.6e-3,
    ),
    # Quasi-isotropic carbon-fiber laminate (T300/epoxy class).
    "CFRP-quasi": Material(
        name="CFRP-quasi",
        density=1600.0,
        youngs_modulus=60.0e9,
        yield_strength=450e6,   # first-ply-failure allowable
        shear_strength=90e6,    # interlaminar-limited
        poisson=0.30,
        min_thickness=1.0e-3,   # 8-ply floor
    ),
    # PEEK 30% carbon filled: injection-moldable, self-lubricating hinge knuckles.
    "PEEK-CF30": Material(
        name="PEEK-CF30",
        density=1400.0,
        youngs_modulus=7.7e9,
        yield_strength=190e6,
        shear_strength=97e6,
        poisson=0.40,
        min_thickness=1.5e-3,
    ),
}


SEAL_MATERIALS: dict[str, SealMaterial] = {
    # Butyl rubber: the classic low-permeation suit bladder material.
    "butyl": SealMaterial(
        name="butyl",
        density=920.0,
        permeability_coeff=2.0e-17,   # O2/N2 mix through butyl, very low
        max_service_strain=1.5,
        shore_a=55,
        min_web_thickness=0.4e-3,
    ),
    # Silicone: wider temperature range, ~30x more permeable than butyl.
    "silicone": SealMaterial(
        name="silicone",
        density=1150.0,
        permeability_coeff=6.0e-16,
        max_service_strain=2.0,
        shore_a=45,
        min_web_thickness=0.3e-3,
    ),
    # FKM (Viton): chemical/thermal robustness, stiffer, less stretch.
    "FKM": SealMaterial(
        name="FKM",
        density=1800.0,
        permeability_coeff=5.0e-17,
        max_service_strain=1.0,
        shore_a=70,
        min_web_thickness=0.5e-3,
    ),
}
