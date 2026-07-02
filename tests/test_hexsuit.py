"""Unit and integration tests for the hexsuit sizing models."""

import math

import pytest

from hexsuit import mechanics as mech
from hexsuit.body import BodyRegion, default_body
from hexsuit.evaluate import evaluate_design
from hexsuit.geometry import ZIGZAG_FACTOR, TileDesign
from hexsuit.hinge_spec import build_hinge_spec
from hexsuit.optimize import optimize_region


def make_design(**overrides) -> TileDesign:
    base = dict(width_af=0.030, aspect=1.0, thickness=0.002,
                bevel_deg=15.0, seal_free_length=0.008)
    base.update(overrides)
    return TileDesign(**base)


ELBOW = next(r for r in default_body() if r.name == "elbow")


# ----------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------

def test_regular_hex_area_and_side():
    d = make_design(width_af=0.030, aspect=1.0)
    # Regular hexagon: A = sqrt(3)/2 * w^2, s = w / sqrt(3).
    assert d.face_area == pytest.approx(math.sqrt(3) / 2 * 0.030**2)
    assert d.side_length == pytest.approx(0.030 / math.sqrt(3))


def test_aspect_stretches_hoop_width_and_area():
    d = make_design(aspect=1.5)
    assert d.hoop_width == pytest.approx(1.5 * d.width_af)
    assert d.face_area == pytest.approx(
        1.5 * make_design(aspect=1.0).face_area)


def test_standoff_grows_with_tile_width_and_shrinks_with_radius():
    small = make_design(width_af=0.02).standoff(0.05)
    large = make_design(width_af=0.04).standoff(0.05)
    assert large > small
    tight = make_design(width_af=0.03).standoff(0.03)
    loose = make_design(width_af=0.03).standoff(0.10)
    assert tight > loose


def test_hinge_rows_floor():
    d = make_design(width_af=0.030, gap=0.0015)
    assert d.hinge_rows_in(0.14) == math.floor(0.14 / 0.0315)
    assert d.hinge_rows_in(0.001) == 1  # never zero


# ----------------------------------------------------------------------
# Structural mechanics
# ----------------------------------------------------------------------

def test_plate_stress_scales_with_pressure_and_inverse_t_squared():
    d1, d2 = make_design(thickness=0.002), make_design(thickness=0.004)
    s1 = mech.plate_bending_stress(d1, 30e3)
    s2 = mech.plate_bending_stress(d2, 30e3)
    assert s1 / s2 == pytest.approx(4.0)
    assert mech.plate_bending_stress(d1, 60e3) == pytest.approx(2 * s1)


def test_plate_stress_matches_roark_hand_calc():
    # a = 10 mm equivalent radius, t = 1 mm, p = 100 kPa, nu = 0.342 (Ti).
    d = make_design(thickness=0.001)
    a = d.equivalent_radius
    expected = 3 * (3 + 0.342) / 8 * 100e3 * (a / 0.001) ** 2
    assert mech.plate_bending_stress(d, 100e3) == pytest.approx(expected)


def test_hinge_line_load_is_axial_membrane_times_zigzag():
    load = mech.hinge_line_load(30e3, 0.06)
    assert load == pytest.approx(30e3 * 0.06 / 2 * ZIGZAG_FACTOR)


def test_pin_sizing_respects_shear_allowable():
    from hexsuit.materials import MATERIALS

    d = make_design()
    pin = mech.size_hinge_pin(d, mech.NOMINAL_PRESSURE, 0.06)
    tau_allow = MATERIALS[mech.PIN_MATERIAL].shear_strength / mech.STRUCT_SF
    assert pin.pin_shear_stress <= tau_allow * 1.001
    assert pin.pin_diameter <= 0.8 * d.thickness + 1e-12


# ----------------------------------------------------------------------
# Kinematics
# ----------------------------------------------------------------------

def test_required_hinge_angle_decreases_with_more_rows():
    small = make_design(width_af=0.018)
    large = make_design(width_af=0.045)
    req_small = mech.required_hinge_angle_deg(small, 0.14, 120.0)
    req_large = mech.required_hinge_angle_deg(large, 0.14, 120.0)
    assert req_small < req_large


def test_capacity_grows_with_bevel():
    lo = mech.hinge_angle_capacity_deg(make_design(bevel_deg=5.0))
    hi = mech.hinge_angle_capacity_deg(make_design(bevel_deg=25.0))
    assert hi - lo == pytest.approx(40.0)


def test_zigzag_factor_value():
    assert ZIGZAG_FACTOR == pytest.approx(2.0 / math.sqrt(3.0))


# ----------------------------------------------------------------------
# Seal mechanics
# ----------------------------------------------------------------------

def test_slack_seal_has_lower_strain_than_taut():
    taut = make_design(seal_free_length=0.002)
    slack = make_design(seal_free_length=0.010)
    angle = 20.0
    assert (mech.seal_peak_strain(slack, angle, 30e3)
            < mech.seal_peak_strain(taut, angle, 30e3))


def test_seal_chord_opens_with_articulation():
    d = make_design()
    assert mech.seal_chord(d, 30.0) > mech.seal_chord(d, 0.0)
    assert mech.seal_chord(d, 0.0) == pytest.approx(d.gap)


def test_permeation_leak_is_tiny_for_butyl():
    d = make_design(seal="butyl")
    q = mech.permeation_leak_sccm(d, 50.0, 30e3)  # 50 m of hinge line
    assert q < 1.0  # permeation must be negligible vs interface seepage


def test_leak_scales_with_edge_length():
    d = make_design()
    q1 = (mech.permeation_leak_sccm(d, 10.0, 30e3)
          + mech.interface_leak_sccm(10.0))
    q2 = (mech.permeation_leak_sccm(d, 20.0, 30e3)
          + mech.interface_leak_sccm(20.0))
    assert q2 == pytest.approx(2 * q1)


# ----------------------------------------------------------------------
# Evaluation and constraints
# ----------------------------------------------------------------------

def test_evaluation_flags_overstressed_thin_tile():
    d = make_design(thickness=0.0007, width_af=0.09, material="PEEK-CF30")
    ev = evaluate_design(d, ELBOW)
    assert ev.margins["tile_stress"] < 0
    assert not ev.feasible


def test_evaluation_flags_insufficient_articulation():
    # One giant tile row with tiny bevel cannot deliver 120 deg elbow ROM.
    d = make_design(width_af=0.12, bevel_deg=2.0, thickness=0.006)
    ev = evaluate_design(d, ELBOW)
    assert ev.margins["articulation"] < 0 or ev.margins["hinge_kink"] < 0


def test_feasible_reference_design():
    d = make_design(width_af=0.020, thickness=0.0015, bevel_deg=14.0,
                    seal_free_length=0.012, material="Ti6Al4V")
    ev = evaluate_design(d, ELBOW)
    bad = {k: v for k, v in ev.margins.items() if v < 0}
    assert ev.feasible, f"violated: {bad}"


def test_margins_all_present():
    ev = evaluate_design(make_design(), ELBOW)
    expected = {"tile_stress", "tile_deflection", "pin_shear", "bearing",
                "articulation", "seal_strain", "standoff", "leak", "torque",
                "bevel", "hinge_kink", "flex_pinch", "min_thickness",
                "manufacturable_edge"}
    assert expected == set(ev.margins)


# ----------------------------------------------------------------------
# Optimization (integration)
# ----------------------------------------------------------------------

def test_optimizer_finds_feasible_elbow():
    res = optimize_region(ELBOW, materials=["Ti6Al4V"], maxiter=120)
    ev = res.evaluation
    assert ev.feasible, f"margins: {ev.margins}"
    # Articulation must actually cover the requirement with margin.
    assert (ev.capacity_hinge_deg
            >= ev.required_hinge_deg * mech.KINEMATIC_MARGIN)
    # Elbow tiles must be small enough for a smooth 120 deg bend.
    assert ev.design.width_af < 0.05
    assert ev.joint_torque < 12.0


def test_optimizer_respects_pressure_scaling():
    lo = optimize_region(ELBOW, pressure=20e3, materials=["Al7075-T6"],
                         maxiter=100)
    hi = optimize_region(ELBOW, pressure=60e3, materials=["Al7075-T6"],
                         maxiter=100)
    assert lo.evaluation.feasible and hi.evaluation.feasible
    # Higher pressure cannot produce a lighter shell.
    assert (hi.evaluation.region_mass
            >= lo.evaluation.region_mass * 0.95)


# ----------------------------------------------------------------------
# Hinge spec generation
# ----------------------------------------------------------------------

def test_hinge_spec_dimensions_consistent():
    d = make_design(width_af=0.022, thickness=0.0015, bevel_deg=14.0,
                    seal_free_length=0.012)
    ev = evaluate_design(d, ELBOW)
    spec = build_hinge_spec(ev, ELBOW)
    assert spec.pin_diameter > 0
    assert spec.knuckles_per_edge == 5
    assert spec.knuckle_pitch == pytest.approx(
        d.side_length * 1e3 / 5, rel=0.01)
    assert spec.articulation_stop_deg == pytest.approx(
        ev.capacity_hinge_deg, abs=0.06)
    # Gland must squeeze the cord, not swallow it.
    assert spec.gland_depth < spec.cord_diameter
    assert spec.predicted_leak_sccm < mech.ALLOWABLE_LEAK_SCCM
    assert len(spec.assembly_notes) >= 5
