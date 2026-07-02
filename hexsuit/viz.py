"""Drawings and plots: hinge cross-section, tiled-limb 3D view, trades."""

from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Polygon
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from . import mechanics as mech
from .body import BodyRegion
from .evaluate import DesignEvaluation
from .geometry import SQRT3, TileDesign
from .optimize import OptimizationResult

TILE_COLOR = "#8a97a8"
TILE_EDGE = "#39424e"
SEAL_COLOR = "#c8543c"
PIN_COLOR = "#2e6f9e"
CORD_COLOR = "#d9a441"


# ----------------------------------------------------------------------
# Hinge cross-section (the "exact mechanism" drawing)
# ----------------------------------------------------------------------

def _tile_edge_profile(t: float, bevel_deg: float, length: float,
                       sign: float) -> np.ndarray:
    """2D cross-section polygon of one tile near the hinge (x: axial, y: radial).

    Outer surface at y = 0, inner (pressure) surface at y = -t. The mating
    edge face is at x = 0 (times ``sign``), with the inner half chamfered
    back by ``bevel_deg``.
    """
    b = math.radians(bevel_deg)
    setback = (t / 2.0) * math.tan(b)
    pts = np.array([
        [0.0, 0.0],
        [length, 0.0],
        [length, -t],
        [setback, -t],
        [0.0, -t / 2.0],
    ])
    pts[:, 0] *= sign
    return pts


def draw_hinge_section(ev: DesignEvaluation, region: BodyRegion,
                       path: str, articulated_deg: float | None = None) -> None:
    """Two-panel drawing: hinge straight and at working articulation."""
    d = ev.design
    r_shell = d.shell_radius(region.limb_radius)
    pin = mech.size_hinge_pin(d, mech.NOMINAL_PRESSURE, r_shell)
    t, g = d.thickness, d.gap
    ln = max(3.5 * d.thickness, 0.35 * d.side_length)
    theta = articulated_deg if articulated_deg is not None else min(
        ev.required_hinge_deg, ev.capacity_hinge_deg)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))
    mm = 1e3

    for ax, ang, title in (
            (axes[0], 0.0, "straight (0\N{DEGREE SIGN})"),
            (axes[1], theta,
             f"articulated ({theta:.0f}\N{DEGREE SIGN} working angle)")):
        a = math.radians(ang)
        # Left tile: fixed, edge face at x = -g/2.
        left = _tile_edge_profile(t, d.bevel_deg, ln, -1.0)
        left[:, 0] -= g / 2.0
        # Right tile: rotated about the pin center (outer surface, x=0).
        right = _tile_edge_profile(t, d.bevel_deg, ln, +1.0)
        right[:, 0] += g / 2.0
        rot = np.array([[math.cos(a), math.sin(a)],
                        [-math.sin(a), math.cos(a)]])
        right = right @ rot.T

        for poly in (left, right):
            ax.add_patch(Polygon(poly * mm, closed=True, facecolor=TILE_COLOR,
                                 edgecolor=TILE_EDGE, lw=1.4, zorder=2))

        # Pin at the outer mold line.
        pin_r = pin.pin_diameter / 2.0
        circ = plt.Circle((0.0, 0.0), pin_r * mm, facecolor=PIN_COLOR,
                          edgecolor="k", lw=1.0, zorder=5)
        ax.add_patch(circ)
        knuckle = plt.Circle((0.0, 0.0), (pin_r + pin.knuckle_wall) * mm,
                             facecolor="none", edgecolor=PIN_COLOR,
                             lw=2.2, ls="-", zorder=4)
        ax.add_patch(knuckle)

        # Bellows web: arc between the two inner-face attachment points.
        pa = np.array([-g / 2.0 - 0.8 * t * math.tan(math.radians(d.bevel_deg)), -t])
        pb_local = np.array([g / 2.0 + 0.8 * t * math.tan(math.radians(d.bevel_deg)), -t])
        pb = pb_local @ rot.T
        chord = np.linalg.norm(pb - pa)
        slack = max(d.seal_free_length - chord, 0.0)
        sag = math.sqrt(3.0 * chord * slack / 8.0) if slack > 0 else 0.001 * t
        s = np.linspace(0, 1, 60)
        mid = (pa + pb) / 2.0
        tang = (pb - pa) / max(chord, 1e-9)
        norm = np.array([tang[1], -tang[0]])
        if norm[1] > 0:
            norm = -norm  # bulge toward pressure side (inward)
        web = (pa[None, :] + np.outer(s, pb - pa)
               + np.outer(np.sin(np.pi * s) * sag, norm))
        ax.plot(web[:, 0] * mm, web[:, 1] * mm, color=SEAL_COLOR, lw=3.0,
                solid_capstyle="round", zorder=3)

        # Secondary cord seal on the left bevel land.
        cord_r = max(0.5e-3, 0.25 * t)
        cland = np.array([-g / 2.0 - (t / 4.0) * math.tan(math.radians(d.bevel_deg)),
                          -0.72 * t])
        ax.add_patch(plt.Circle(cland * mm, cord_r * mm, facecolor=CORD_COLOR,
                                edgecolor="k", lw=0.8, zorder=3))

        span = (ln + g) * mm
        ax.set_xlim(-span, span)
        ax.set_ylim(-(t * mm) * 3.2, t * mm * 2.0)
        ax.set_aspect("equal")
        ax.set_title(f"{region.name} hinge, {title}", fontsize=11)
        ax.set_xlabel("axial (mm)")
        ax.set_ylabel("radial (mm)")
        ax.axhline(0, color="0.75", lw=0.6, ls=":", zorder=1)
        ax.annotate("VACUUM", (0, t * mm * 1.45), ha="center", fontsize=8,
                    color="0.4")
        ax.annotate(f"PRESSURE {mech.NOMINAL_PRESSURE/1e3:.1f} kPa",
                    (0, -t * mm * 2.9), ha="center", fontsize=8, color="0.4")

    handles = [
        plt.Line2D([], [], color=TILE_COLOR, lw=8, label=f"tile ({d.material})"),
        plt.Line2D([], [], color=PIN_COLOR, lw=4,
                   label=f"pin \N{GREEK CAPITAL LETTER PHI}{pin.pin_diameter*1e3:.1f} mm + knuckle"),
        plt.Line2D([], [], color=SEAL_COLOR, lw=4,
                   label=f"bellows web ({d.seal}, self-energizing)"),
        plt.Line2D([], [], color=CORD_COLOR, lw=4, label="secondary cord seal"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=9,
               frameon=False)
    fig.suptitle(
        f"Outer-pivot piano hinge, {region.name}: bevel {d.bevel_deg:.1f}\N{DEGREE SIGN}, "
        f"stop {ev.capacity_hinge_deg:.0f}\N{DEGREE SIGN}/line, "
        f"t = {t*1e3:.2f} mm", fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=160)
    plt.close(fig)


# ----------------------------------------------------------------------
# 3D tiled limb segment, straight and flexed
# ----------------------------------------------------------------------

def _hex_vertices(cx: float, cz: float, d: TileDesign) -> np.ndarray:
    """Flat-top hexagon vertices in (hoop, axial) developed coordinates."""
    w, h = d.hoop_width, d.width_af
    s_ax = h / SQRT3  # axial half-diagonal step
    return np.array([
        [cx - w / 2.0, cz - s_ax / 2.0],
        [cx - w / 2.0, cz + s_ax / 2.0],
        [cx, cz + s_ax],
        [cx + w / 2.0, cz + s_ax / 2.0],
        [cx + w / 2.0, cz - s_ax / 2.0],
        [cx, cz - s_ax],
    ])


def draw_tiled_limb(ev: DesignEvaluation, region: BodyRegion, path: str) -> None:
    """3D render of the tiled flex band around the limb, straight vs flexed."""
    d = ev.design
    r = d.shell_radius(region.limb_radius)
    n_hoop = max(3, int(round(2.0 * math.pi * r / (d.hoop_width + d.gap))))
    hoop_pitch = 2.0 * math.pi * r / n_hoop
    rows = d.hinge_rows_in(region.flex_zone_length) + 1
    bend_total = math.radians(region.required_rom_deg)

    fig = plt.figure(figsize=(13, 6))
    shrink = 0.92  # visual gap between tiles

    for idx, (bend, title) in enumerate((
            (0.0, "straight"),
            (bend_total, f"flexed {region.required_rom_deg:.0f}\N{DEGREE SIGN}"))):
        ax = fig.add_subplot(1, 2, idx + 1, projection="3d")
        per_row = bend / max(rows - 1, 1)

        # Accumulated row frames: each row's origin advances by axial_pitch
        # along a direction that kinks by per_row at every hinge line.
        # The band bends in the y-z plane about x-parallel hinge axes.
        origins, angles = [np.array([0.0, 0.0])], [0.0]
        for j in range(1, rows):
            ang = angles[-1] + per_row
            step = d.axial_pitch * np.array([-math.sin(ang), math.cos(ang)])
            origins.append(origins[-1] + step)
            angles.append(ang)

        polys = []
        for j in range(rows):
            offset = 0.5 * hoop_pitch if j % 2 else 0.0
            oy, oz = origins[j]
            ca, sa = math.cos(angles[j]), math.sin(angles[j])
            for i in range(n_hoop):
                th0 = (i * hoop_pitch + offset) / r
                pts3 = []
                for hx, hz in _hex_vertices(0.0, 0.0, d) * shrink:
                    a = th0 + hx / r
                    x, yl, zl = r * math.cos(a), r * math.sin(a), hz
                    y = yl * ca - zl * sa + oy
                    z = yl * sa + zl * ca + oz
                    pts3.append((x, y, z))
                polys.append(pts3)
        coll = Poly3DCollection(polys, facecolors=TILE_COLOR,
                                edgecolors=TILE_EDGE, linewidths=0.7)
        ax.add_collection3d(coll)
        lim = max(r * 2.2, rows * d.axial_pitch * 0.75)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_zlim(-lim * 0.35, lim * 1.65)
        ax.set_box_aspect((1, 1, 1))
        ax.set_title(f"{region.name} flex band, {title}", fontsize=11)
        ax.set_axis_off()
        ax.view_init(elev=12, azim=-64)

    fig.suptitle(
        f"{region.name}: {ev.n_tiles} tiles, AF {d.width_af*1e3:.1f} mm, "
        f"{ev.n_rows} hinge rows, "
        f"{ev.required_hinge_deg:.1f}\N{DEGREE SIGN}/hinge required",
        fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------------------------------------------------
# Trade study and margins overview
# ----------------------------------------------------------------------

def draw_trade_study(region: BodyRegion, ev_opt: DesignEvaluation,
                     path: str) -> None:
    """Mass and worst-margin vs tile width at the optimal t/bevel/seal."""
    from .evaluate import evaluate_design

    d0 = ev_opt.design
    widths = np.linspace(0.012, 0.09, 90)
    masses, margins = [], []
    for w in widths:
        d = TileDesign(width_af=w, aspect=d0.aspect, thickness=d0.thickness,
                       bevel_deg=d0.bevel_deg,
                       seal_free_length=d0.seal_free_length, gap=d0.gap,
                       material=d0.material, seal=d0.seal)
        ev = evaluate_design(d, region)
        masses.append(ev.region_mass)
        margins.append(ev.worst_margin)
    masses, margins = np.array(masses), np.array(margins)

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()
    feas = margins >= 0
    ax1.plot(widths * 1e3, masses, color="#2e6f9e", lw=2, label="region mass")
    ax2.plot(widths * 1e3, margins, color="#c8543c", lw=2,
             label="worst constraint margin")
    ax2.axhline(0, color="#c8543c", lw=0.8, ls="--")
    if feas.any():
        ax1.axvspan(widths[feas].min() * 1e3, widths[feas].max() * 1e3,
                    color="#79b473", alpha=0.15, label="feasible band")
    ax1.axvline(d0.width_af * 1e3, color="k", lw=1.2, ls=":",
                label=f"optimum {d0.width_af*1e3:.1f} mm")
    ax1.set_xlabel("tile width across flats (mm)")
    ax1.set_ylabel("region shell mass (kg)", color="#2e6f9e")
    ax2.set_ylabel("worst normalized margin (\N{GREATER-THAN OR EQUAL TO}0 feasible)",
                   color="#c8543c")
    ax1.set_title(f"{region.name}: tile-width trade at optimal thickness/bevel")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def draw_suit_overview(results: list[OptimizationResult], path: str) -> None:
    """Bar summary: tile size, thickness, per-hinge angle, mass, torque, leak."""
    names = [r.region.name for r in results]
    evs = [r.evaluation for r in results]
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.5))
    panels = [
        ("tile width AF (mm)", [e.design.width_af * 1e3 for e in evs], "#2e6f9e"),
        ("thickness (mm)", [e.design.thickness * 1e3 for e in evs], "#39424e"),
        ("required deg / hinge", [e.required_hinge_deg for e in evs], "#79b473"),
        ("region mass (kg)", [e.region_mass for e in evs], "#8a97a8"),
        ("joint torque (N m)", [e.joint_torque for e in evs], "#c8543c"),
        ("leak (sccm)", [e.leak_sccm for e in evs], "#d9a441"),
    ]
    for ax, (label, vals, color) in zip(axes.flat, panels):
        ax.bar(names, vals, color=color)
        ax.set_title(label, fontsize=10)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.grid(axis="y", alpha=0.3)
    if any(e.joint_torque for e in evs):
        axes.flat[4].axhline(12.0, color="k", ls="--", lw=1,
                             label="12 N m crew limit")
        axes.flat[4].legend(fontsize=8)
    total = sum(e.region_mass for e in evs)
    leak = sum(e.leak_sccm for e in evs)
    fig.suptitle(f"Optimized hex-tile suit shell: {total:.2f} kg total, "
                 f"{leak:.1f} sccm total leak (budget "
                 f"{mech.ALLOWABLE_LEAK_SCCM:.0f} sccm)", fontsize=13)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
