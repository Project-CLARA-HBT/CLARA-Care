from .smallbank_adjudicate import serial_witness


def event(kind, reads, status="committed", start=1, end=4):
    return dict(kind=kind, reads=reads, account=0, start=start, end=end, status=status, failures=[])


def witness(events, before, after):
    return serial_witness([[0, *before]], dict(events=events, after=[[0, *after]]))


def test_joint_branch_and_checking_state():
    events = [event("withdraw", [20.2]), event("check", [0.0, 0.0])]
    assert witness(events, (20.2, 0.0), (0.0, -4.0)) == (0, 1)
    assert witness(events, (20.2, 0.0), (0.0, -6.0)) is None
    events[1]["reads"] = [20.2, 0.0]
    assert witness(events, (20.2, 0.0), (0.0, -4.0)) is None


def test_real_time_precedence_rules_out_otherwise_valid_reordering():
    events = [event("deposit", [], start=1, end=2), event("check", [0.0, 0.0], start=3)]
    assert witness(events, (0.0, 0.0), (0.0, -4.0 + 1.3)) is None


def test_insufficient_savings_and_exact_thresholds():
    assert witness([event("withdraw", [20.2], "insufficient")], (20.2, 0), (20.2, 0)) is None
    assert witness([event("withdraw", [0], "insufficient")], (0, 0), (0, 0)) == (0,)
    assert witness([event("check", [0, 5])], (0, 5), (0, 0)) == (0,)
