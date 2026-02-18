
import numpy as np
from src.calculations.basic_scaling import basic_scaling_3d, _validate_records, design_spectrum_g

def _dummy_records(n=11, dt=0.01):
    t = np.arange(0, 10.0, dt)
    ax = np.sin(2*np.pi*1.0*t) * 0.1
    ay = np.sin(2*np.pi*1.2*t) * 0.1
    records = []
    for i in range(n):
        meta = {'event_id': f'E{i//3}'}  # en fazla 3 her event
        records.append((ax, ay, dt, meta))
    return records

def test_validate_min_records():
    try:
        _validate_records(_dummy_records(10))
        assert False, "10 kayıt ile geçmemeli"
    except ValueError:
        assert True

def test_validate_event_cap():
    recs = _dummy_records(12)
    # event 0 sayısını 4 yap
    recs[0] = (recs[0][0], recs[0][1], recs[0][2], {'event_id': 'E0'})
    recs[1] = (recs[1][0], recs[1][1], recs[1][2], {'event_id': 'E0'})
    recs[2] = (recs[2][0], recs[2][1], recs[2][2], {'event_id': 'E0'})
    recs[3] = (recs[3][0], recs[3][1], recs[3][2], {'event_id': 'E0'})  # 4. kayıt
    try:
        _validate_records(recs)
        assert False, "Aynı deprem >3 ile geçmemeli"
    except ValueError:
        assert True

def test_basic_scaling_runs():
    recs = _dummy_records(11)
    Tp, SDS, SD1 = 0.8, 0.6, 0.3
    res = basic_scaling_3d(recs, Tp, SDS, SD1, accel_unit='g', damping_percent=5.0)
    assert res.f_min > 0.0
    assert len(res.T) > 0


def test_peer_no_scaling():
    recs = _dummy_records(11)
    Tp, SDS, SD1 = 0.8, 0.6, 0.3
    res = basic_scaling_3d(
        recs,
        Tp,
        SDS,
        SD1,
        accel_unit='g',
        damping_percent=5.0,
        scale_mode="peer",
        peer_method="no_scaling",
    )
    assert all(abs(f - 1.0) < 1e-6 for f in res.per_record_factors)


def test_peer_min_mse_custom_weights():
    recs = _dummy_records(11)
    Tp, SDS, SD1 = 0.8, 0.6, 0.3
    res = basic_scaling_3d(
        recs,
        Tp,
        SDS,
        SD1,
        accel_unit='g',
        damping_percent=5.0,
        scale_mode="peer",
        peer_method="min_mse",
        peer_period_knots=[0.01, 0.1, 1.0, 10.0],
        peer_weight_knots=[1.0, 2.0, 2.0, 1.0],
    )
    assert len(res.per_record_factors) == len(recs)


def test_peer_single_period():
    recs = _dummy_records(11)
    Tp, SDS, SD1 = 0.8, 0.6, 0.3
    Ts = 0.75
    res = basic_scaling_3d(
        recs,
        Tp,
        SDS,
        SD1,
        accel_unit='g',
        damping_percent=5.0,
        scale_mode="peer",
        peer_method="single_period",
        peer_single_period=Ts,
    )
    assert len(res.per_record_factors) == len(recs)
