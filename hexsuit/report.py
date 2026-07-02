"""Markdown design-report writer: tables, specs and figures per region."""

from __future__ import annotations

import os

from . import mechanics as mech
from .hinge_spec import build_hinge_spec, spec_to_markdown
from .optimize import OptimizationResult
from .viz import (draw_hinge_section, draw_suit_overview, draw_tiled_limb,
                  draw_trade_study)


def write_report(results: list[OptimizationResult], out_dir: str,
                 pressure: float = mech.NOMINAL_PRESSURE,
                 figures: bool = True) -> str:
    """Write the full design report + figures; return the report path."""
    os.makedirs(out_dir, exist_ok=True)
    fig_dir = os.path.join(out_dir, "figures")
    if figures:
        os.makedirs(fig_dir, exist_ok=True)

    lines: list[str] = []
    add = lines.append

    add("# Hex-Tile Space Suit Shell: Optimized Design Report")
    add("")
    add(f"Operating pressure: **{pressure/1e3:.1f} kPa** "
        f"({pressure/6894.76:.1f} psi) pure O2; structural proof case "
        f"{mech.PROOF_FACTOR}x with SF {mech.STRUCT_SF} on yield.")
    add("")

    total_mass = sum(r.evaluation.region_mass for r in results)
    total_leak = sum(r.evaluation.leak_sccm for r in results)
    total_tiles = sum(r.evaluation.n_tiles for r in results)
    add("## Suit-level summary")
    add("")
    add(f"- Total tiled-shell mass: **{total_mass:.2f} kg** "
        f"({total_tiles} tiles across {len(results)} regions)")
    add(f"- Total predicted leak: **{total_leak:.1f} sccm** vs budget "
        f"{mech.ALLOWABLE_LEAK_SCCM:.0f} sccm "
        f"({'PASS' if total_leak <= mech.ALLOWABLE_LEAK_SCCM else 'FAIL'})")
    worst_torque = max(r.evaluation.joint_torque for r in results)
    add(f"- Worst joint torque: **{worst_torque:.2f} N m** vs 12 N m crew "
        f"limit ({'PASS' if worst_torque <= 12.0 else 'FAIL'})")
    infeasible = [r.region.name for r in results if not r.evaluation.feasible]
    add(f"- Feasibility: "
        + ("all regions feasible" if not infeasible
           else f"INFEASIBLE regions: {', '.join(infeasible)}"))
    add("")
    if figures:
        overview_png = os.path.join(fig_dir, "suit_overview.png")
        draw_suit_overview(results, overview_png)
        add("![suit overview](figures/suit_overview.png)")
        add("")

    add("## Optimized tile designs per region")
    add("")
    add("| Region | Material | AF width (mm) | Hoop width (mm) | Aspect | "
        "Thickness (mm) | Bevel (deg) | Tiles | Hinge rows | deg/hinge "
        "req/cap | Mass (kg) | Torque (N m) | Leak (sccm) |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | "
        "--- | --- | --- |")
    for r in results:
        ev, d = r.evaluation, r.evaluation.design
        add(f"| {r.region.name} | {d.material} | {d.width_af*1e3:.1f} | "
            f"{d.hoop_width*1e3:.1f} | {d.aspect:.2f} | "
            f"{d.thickness*1e3:.2f} | {d.bevel_deg:.1f} | {ev.n_tiles} | "
            f"{ev.n_rows} | {ev.required_hinge_deg:.1f} / "
            f"{ev.capacity_hinge_deg:.1f} | {ev.region_mass:.2f} | "
            f"{ev.joint_torque:.2f} | {ev.leak_sccm:.1f} |")
    add("")

    add("## Constraint margins (normalized, >= 0 is pass)")
    add("")
    margin_keys = list(results[0].evaluation.margins)
    add("| Region | " + " | ".join(margin_keys) + " |")
    add("| --- |" + " --- |" * len(margin_keys))
    for r in results:
        vals = " | ".join(f"{r.evaluation.margins[k]:+.2f}"
                          for k in margin_keys)
        add(f"| {r.region.name} | {vals} |")
    add("")

    add("## Hinge and seal mechanism")
    add("")
    add("All regions share one mechanism, dimensioned per region: an "
        "**outer-pivot interleaved piano hinge with a dual self-energizing "
        "seal**. The pin sits on the outer mold line so articulation is "
        "volume-neutral (pressure exerts near-zero torque on the joint); "
        "chamfered inner edge faces give a hard kinematic stop; a molded "
        "elastomer bellows web on the pressure side is the primary seal "
        "(pressure pushes it into its dovetail seats, so leaks scale "
        "*down* with pressure), backed by a compressed cord seal on the "
        "bevel land.")
    add("")
    for r in results:
        spec = build_hinge_spec(r.evaluation, r.region, pressure)
        add(spec_to_markdown(spec))
        add("")
        if figures:
            hinge_png = os.path.join(fig_dir, f"hinge_{r.region.name}.png")
            limb_png = os.path.join(fig_dir, f"limb_{r.region.name}.png")
            trade_png = os.path.join(fig_dir, f"trade_{r.region.name}.png")
            draw_hinge_section(r.evaluation, r.region, hinge_png)
            draw_tiled_limb(r.evaluation, r.region, limb_png)
            draw_trade_study(r.region, r.evaluation, trade_png)
            add(f"![hinge section](figures/hinge_{r.region.name}.png)")
            add("")
            add(f"![tiled limb](figures/limb_{r.region.name}.png)")
            add("")
            add(f"![trade study](figures/trade_{r.region.name}.png)")
            add("")

    add("## Modeling notes and limitations")
    add("")
    add("- Tile plate bending uses the simply-supported equivalent circular "
        "plate (Roark case 10a); hinge lines cannot carry moment.")
    add("- Membrane loads assume a closed cylinder at each region's shell "
        "radius; zig-zag hinge geometry raises edge loads by 2/sqrt(3).")
    add("- Leakage = elastomer permeation (exact) + an empirical "
        f"{mech.INTERFACE_LEAK_SCCM_PER_M} sccm/m interface seepage along "
        "bonded seal joints.")
    add("- Seal fatigue is enforced by derating allowable strain by "
        f"{mech.FATIGUE_STRAIN_FACTOR}x for cyclic service.")
    add("- Thermal derating, micrometeoroid cover layers, and vertex-boot "
        "molding details are out of scope of this sizing pass.")
    add("")

    path = os.path.join(out_dir, "design_report.md")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path
