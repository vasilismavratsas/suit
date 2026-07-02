"""Command-line interface: ``python -m hexsuit [options]``."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import mechanics as mech
from .body import default_body
from .hinge_spec import build_hinge_spec
from .materials import MATERIALS, SEAL_MATERIALS
from .optimize import optimize_suit
from .report import write_report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="hexsuit",
        description="Optimize hexagonal-tile space suit shell: tile size, "
                    "shape, thickness, and the hinge/seal mechanism.")
    ap.add_argument("-o", "--out", default="output",
                    help="output directory (default: ./output)")
    ap.add_argument("-p", "--pressure", type=float,
                    default=mech.NOMINAL_PRESSURE / 1e3,
                    help="operating pressure in kPa (default: 29.6)")
    ap.add_argument("-m", "--materials", nargs="+",
                    choices=sorted(MATERIALS), default=None,
                    help="candidate tile materials (default: all)")
    ap.add_argument("-s", "--seal", choices=sorted(SEAL_MATERIALS),
                    default="butyl", help="seal elastomer (default: butyl)")
    ap.add_argument("-r", "--regions", nargs="+", default=None,
                    help="restrict to these body regions (default: all)")
    ap.add_argument("--no-figures", action="store_true",
                    help="skip figure generation (faster)")
    ap.add_argument("--json", action="store_true",
                    help="also dump machine-readable results.json")
    args = ap.parse_args(argv)

    regions = default_body()
    if args.regions:
        known = {r.name for r in regions}
        unknown = set(args.regions) - known
        if unknown:
            ap.error(f"unknown regions: {sorted(unknown)}; "
                     f"choose from {sorted(known)}")
        regions = [r for r in regions if r.name in args.regions]

    pressure = args.pressure * 1e3
    print(f"[hexsuit] pressure {args.pressure:.1f} kPa, seal {args.seal}, "
          f"materials {args.materials or list(MATERIALS)}")
    results = optimize_suit(regions, pressure=pressure,
                            materials=args.materials, seal=args.seal)

    report = write_report(results, args.out, pressure=pressure,
                          figures=not args.no_figures)
    print(f"[hexsuit] report written to {report}")

    if args.json:
        payload = []
        for r in results:
            ev = r.evaluation
            spec = build_hinge_spec(ev, r.region, pressure)
            payload.append({
                "region": r.region.name,
                "design": ev.design.as_dict(),
                "feasible": ev.feasible,
                "margins": {k: round(v, 4) for k, v in ev.margins.items()},
                "responses": {
                    "n_tiles": ev.n_tiles,
                    "n_hinge_rows": ev.n_rows,
                    "required_deg_per_hinge": round(ev.required_hinge_deg, 2),
                    "capacity_deg_per_hinge": round(ev.capacity_hinge_deg, 2),
                    "region_mass_kg": round(ev.region_mass, 3),
                    "joint_torque_nm": round(ev.joint_torque, 3),
                    "leak_sccm": round(ev.leak_sccm, 3),
                    "tile_stress_mpa": round(ev.tile_stress / 1e6, 1),
                    "seal_strain_pct": round(ev.seal_strain * 100, 1),
                },
                "hinge_spec": {k: v for k, v in vars(spec).items()},
            })
        json_path = os.path.join(args.out, "results.json")
        with open(json_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[hexsuit] machine-readable results in {json_path}")

    infeasible = [r.region.name for r in results if not r.evaluation.feasible]
    if infeasible:
        print(f"[hexsuit] WARNING: infeasible regions: {infeasible}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
