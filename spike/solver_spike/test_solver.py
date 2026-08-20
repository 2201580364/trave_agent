"""Spike 约束单测：验证分层求解的硬约束不变量。

运行：python test_solver.py（或 pytest test_solver.py）
"""
from solver import (
    Attraction, DayPlan, filter_day, check_constraints, layered_solve,
    MODE_BUDGET, STATION_TO_CITY_MIN, STATION_EARLY_MIN,
)
from sample_data import SAMPLE_ATTRACTIONS


def _run(mode="normal"):
    return layered_solve(SAMPLE_ATTRACTIONS, days=3, start_weekday=1,
                         travel_mode=mode, arrival_min=14 * 60,
                         departure_min=16 * 60, weather="light_rain", seed=42)


def test_no_close_day_violation():
    """硬约束：闭馆日绝不出现在当天。"""
    for p in _run():
        for a, _ in p.visits:
            assert a.close_day != p.weekday, f"{a.name} 排在闭馆日"


def test_no_time_window_violation():
    """硬约束：到达 ≥ 开放，离开 ≤ 关闭。"""
    for p in _run():
        for a, arr in p.visits:
            leave = arr + a.duration
            assert arr >= a.open_min, f"{a.name} 早于开放"
            assert leave <= a.close_min, f"{a.name} 晚于关闭"


def test_anchor_day1_start():
    """硬约束：Day1 有效起始 = 到达 + 场站耗时。"""
    day1 = _run()[0]
    for _, arr in day1.visits:
        assert arr >= 14 * 60 + STATION_TO_CITY_MIN


def test_anchor_last_day_end():
    """硬约束：DayN 结束 = 离开 - 场站提前量。"""
    last = _run()[-1]
    for a, arr in last.visits:
        assert arr + a.duration <= 16 * 60 - STATION_EARLY_MIN


def test_close_day_filter_direct():
    """过滤函数直接测试：闭馆日景点被排除。"""
    m = [a for a in SAMPLE_ATTRACTIONS if a.name == "浙江省博物馆"][0]
    feasible, excluded = filter_day([m], weekday=1, weather="clear")
    assert m in excluded and m not in feasible


def test_extreme_weather_excludes_outdoor():
    """天气硬约束：极端天气排除室外景点。"""
    outdoor = [a for a in SAMPLE_ATTRACTIONS if not a.is_indoor]
    feasible, excluded = filter_day(outdoor, weekday=2, weather="extreme")
    assert all(not a.is_indoor for a in feasible)
    assert {a.id for a in excluded} == {a.id for a in outdoor}


def test_energy_overflow_detected():
    """体力约束检测：总能量超预算时被 check_constraints 命中。"""
    a = SAMPLE_ATTRACTIONS[0]
    plan = DayPlan(1, 2, [(a, 360)], [], 8)  # total_energy=8 > 5
    assert any("体力超载" in v for v in check_constraints(plan, MODE_BUDGET["normal"]))


def _all_tests():
    tests = sorted(
        (k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)
    )
    for name, fn in tests:
        fn()
        print(f"PASS {name}")
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    _all_tests()
