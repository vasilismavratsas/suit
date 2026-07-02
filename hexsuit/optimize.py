"""Constrained optimization of tile designs, per body region.

Decision vector per region (5 variables):
    x = [width_af, aspect, thickness, bevel_deg, seal_free_length]

Objective: minimize region shell mass, with a small penalty on operator
torque so the optimizer prefers easier joints when mass is tied.
Constraints: every margin in ``DesignEvaluation.margins`` must be >= 0.

Strategy: differential evolution (global, handles the integer row-count
discontinuity) with an exact penalty, followed by a Nelder-Mead polish,
run for every structural material and the best seal, keeping the winner.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import differential_evolution, minimize

from .body import BodyRegion, default_body
from .evaluate import DesignEvaluation, evaluate_design
from .geometry import TileDesign
from .materials import MATERIALS
from . import mechanics as mech

BOUNDS = [
    (0.015, 0.120),           # width_af (m)
    (0.60, 1.80),             # aspect
    (0.0006, 0.008),          # thickness (m)
    (2.0, 35.0),              # bevel (deg)
    (0.0015, 0.020),          # seal free length (m)
]

TORQUE_WEIGHT = 0.02          # kg-equivalent per N*m of joint torque
PENALTY = 50.0                # exact-penalty weight per unit violation


def _make_design(x: np.ndarray, material: str, seal: str) -> TileDesign:
    return TileDesign(
        width_af=float(x[0]),
        aspect=float(x[1]),
        thickness=float(x[2]),
        bevel_deg=float(x[3]),
        seal_free_length=float(x[4]),
        material=material,
        seal=seal,
    )


def _objective(x: np.ndarray, region: BodyRegion, material: str, seal: str,
               pressure: float) -> float:
    design = _make_design(x, material, seal)
    ev = evaluate_design(design, region, pressure)
    cost = ev.region_mass + TORQUE_WEIGHT * ev.joint_torque
    violation = sum(max(0.0, -m) for m in ev.margins.values())
    return cost + PENALTY * violation


@dataclass
class OptimizationResult:
    region: BodyRegion
    evaluation: DesignEvaluation
    tried: dict[str, float] = field(default_factory=dict)  # material -> cost

    @property
    def design(self) -> TileDesign:
        return self.evaluation.design


def optimize_region(region: BodyRegion,
                    pressure: float = mech.NOMINAL_PRESSURE,
                    materials: list[str] | None = None,
                    seal: str = "butyl",
                    seed: int = 7,
                    maxiter: int = 220) -> OptimizationResult:
    """Find the lightest feasible tile design for one body region."""
    materials = materials or list(MATERIALS)
    best: DesignEvaluation | None = None
    best_cost = math.inf
    tried: dict[str, float] = {}

    for material in materials:
        res = differential_evolution(
            _objective, BOUNDS,
            args=(region, material, seal, pressure),
            seed=seed, maxiter=maxiter, popsize=24, tol=1e-8,
            mutation=(0.4, 1.0), recombination=0.8, polish=False,
        )
        # Local polish from the DE optimum.
        local = minimize(
            _objective, res.x, args=(region, material, seal, pressure),
            method="Nelder-Mead",
            options={"xatol": 1e-6, "fatol": 1e-9, "maxiter": 3000},
        )
        x = local.x if local.fun < res.fun else res.x
        x = np.clip(x, [b[0] for b in BOUNDS], [b[1] for b in BOUNDS])

        design = _make_design(x, material, seal)
        ev = evaluate_design(design, region, pressure)
        cost = ev.region_mass + TORQUE_WEIGHT * ev.joint_torque
        tried[material] = cost if ev.feasible else math.inf

        if ev.feasible and cost < best_cost:
            best, best_cost = ev, cost

    if best is None:
        # Return the least-infeasible design so the report can explain why.
        material = materials[0]
        res = differential_evolution(
            _objective, BOUNDS, args=(region, material, seal, pressure),
            seed=seed, maxiter=maxiter, popsize=24, polish=True)
        design = _make_design(res.x, material, seal)
        best = evaluate_design(design, region, pressure)

    return OptimizationResult(region=region, evaluation=best, tried=tried)


def optimize_suit(regions: list[BodyRegion] | None = None,
                  pressure: float = mech.NOMINAL_PRESSURE,
                  materials: list[str] | None = None,
                  seal: str = "butyl",
                  verbose: bool = True) -> list[OptimizationResult]:
    """Optimize every body region independently."""
    regions = regions or default_body()
    results = []
    for region in regions:
        if verbose:
            print(f"[hexsuit] optimizing {region.name} ...", flush=True)
        result = optimize_region(region, pressure, materials, seal)
        results.append(result)
        if verbose:
            ev = result.evaluation
            print(f"    -> {ev.design.material}, "
                  f"AF {ev.design.width_af*1e3:.1f} mm, "
                  f"t {ev.design.thickness*1e3:.2f} mm, "
                  f"bevel {ev.design.bevel_deg:.1f} deg, "
                  f"mass {ev.region_mass:.2f} kg, "
                  f"feasible={ev.feasible}", flush=True)
    return results
