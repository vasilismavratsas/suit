"""hexsuit: design optimizer for hinged hexagonal-tile space suit shells.

The package sizes hexagonal armor tiles (width across flats, thickness,
edge-bevel angle) and their piano-hinge / bellows-seal joints so that a
pressurized hard-shell suit stays structurally sound, holds pressure with
negligible leakage, and still lets a human move through the full range of
motion of every major joint.
"""

__version__ = "0.1.0"

from .materials import MATERIALS, SEAL_MATERIALS, Material, SealMaterial
from .body import BodyRegion, default_body
from .geometry import TileDesign
from .evaluate import DesignEvaluation, evaluate_design
from .optimize import OptimizationResult, optimize_region, optimize_suit
from .hinge_spec import HingeSpec, build_hinge_spec

__all__ = [
    "MATERIALS",
    "SEAL_MATERIALS",
    "Material",
    "SealMaterial",
    "BodyRegion",
    "default_body",
    "TileDesign",
    "DesignEvaluation",
    "evaluate_design",
    "OptimizationResult",
    "optimize_region",
    "optimize_suit",
    "HingeSpec",
    "build_hinge_spec",
]
