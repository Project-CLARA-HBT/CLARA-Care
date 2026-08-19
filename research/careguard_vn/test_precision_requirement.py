from research.careguard_vn.precision_requirement import half_width_at, required_n

Z_95 = 1.959963984540054


def test_required_n_p005():
    n = required_n(0.05, 0.03)
    assert n == 203
    assert half_width_at(n, 0.05) <= 0.03 + 1e-9
    assert half_width_at(n - 1, 0.05) > 0.03 - 1e-9


def test_required_n_p010():
    n = required_n(0.10, 0.03)
    assert n == 385
    assert half_width_at(n, 0.10) <= 0.03 + 1e-9


def test_planning_target_is_max():
    assert required_n(0.10, 0.03) >= required_n(0.05, 0.03)


def test_boundary_rejects():
    for bad in (0.0, 1.0, -0.1):
        try:
            required_n(bad, 0.03)
        except ValueError:
            pass
        else:
            raise AssertionError(f"p={bad} should be rejected")
