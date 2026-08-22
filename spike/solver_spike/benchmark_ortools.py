"""G3 Spike 收尾 —— OR-Tools TSP-TW 收敛时间实测（修正版）。

修正点（相对首版）：
1. slack_max 1440 → 240：巨大 slack 会撑爆搜索空间（首版 2 景点竟跑满 30s）。
2. 增加 AddDisjunction：单车辆 TSP-TW 必须访问所有节点，但 K-Means 可能把
   过多景点塞进一天导致不可行 → 用 disjunction 允许「丢弃放不下的景点」，
   这才是生产正确的建模（对应技术选型文档「推荐每日上限」的降级策略）。

运行：python benchmark_ortools.py [N] [D]
"""
from __future__ import annotations

import random
import sys
import time

from ortools.constraint_solver import routing_enums_pb2, pywrapcp

from solver import Attraction, build_od, kmeans_cluster, solve_day_tsp_tw
from sample_data import SAMPLE_ATTRACTIONS

ORIGIN_TRANSIT_MIN = 30
DAY_START_MIN = 9 * 60
DAY_END_MIN = 21 * 60
DROP_PENALTY = 1_000_000   # 丢弃惩罚：尽量排入，仅不可行时才丢弃


def gen_attractions(n, seed=0):
    rng = random.Random(seed)
    atts = []
    for i in range(n):
        lat = 30.25 + rng.uniform(-0.08, 0.08)
        lng = 120.15 + rng.uniform(-0.10, 0.10)
        duration = rng.choice([90, 120, 150, 180, 240])
        energy = rng.randint(1, 5)
        open_min = rng.randint(8 * 60, 10 * 60)
        close_min = open_min + duration + rng.randint(60, 240)
        atts.append(Attraction(i + 1, f"景点{i + 1}", "自然山水",
                               round(lat, 6), round(lng, 6), energy, duration,
                               open_min, close_min))
    return atts


def ortools_solve_day(atts, od, start_min, end_min, time_limit_sec=30):
    """单日单车辆 TSP-TW（可丢弃节点）。返回 (order, dropped_count, elapsed_sec)。"""
    n = len(atts)
    if n == 0:
        return [], 0, 0.0

    manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def transit_cb(from_idx, to_idx):
        f = manager.IndexToNode(from_idx)
        t = manager.IndexToNode(to_idx)
        svc = 0 if f == 0 else atts[f - 1].duration
        if t == 0:
            travel = 0.0
        elif f == 0:
            travel = float(ORIGIN_TRANSIT_MIN)
        else:
            travel = od[(atts[f - 1].id, atts[t - 1].id)]
        return int(round(svc + travel))

    transit_idx = routing.RegisterTransitCallback(transit_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)
    routing.AddDimension(transit_idx, 240, 1440 * 2, False, "Time")  # slack=240
    time_dim = routing.GetDimensionOrDie("Time")

    time_dim.CumulVar(routing.Start(0)).SetRange(start_min, start_min)
    time_dim.CumulVar(routing.End(0)).SetRange(0, end_min)

    for i, a in enumerate(atts):
        node = manager.NodeToIndex(i + 1)
        time_dim.CumulVar(node).SetRange(a.open_min, a.close_min - a.duration)
        routing.AddDisjunction([node], DROP_PENALTY)  # 允许丢弃放不下的景点

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    # 不挂 GLS：每天 3-5 个节点的规模，贪心初始解 + 默认局部搜索即可，
    # 且能快速收敛到局部最优。GLS 会在 tiny 问题上把整段时间预算跑满。
    params.time_limit.seconds = 5  # 安全上限，实际应毫秒级

    t0 = time.perf_counter()
    solution = routing.SolveWithParameters(params)
    elapsed = time.perf_counter() - t0
    if solution is None:
        return None, n, elapsed

    order, dropped = [], 0
    idx = routing.Start(0)
    while not routing.IsEnd(idx):
        node = manager.IndexToNode(idx)
        if node != 0:
            order.append(atts[node - 1])
        idx = solution.Value(routing.NextVar(idx))
    dropped = n - len(order)
    return order, dropped, elapsed


def route_travel(order, od):
    total = ORIGIN_TRANSIT_MIN
    prev_id = None
    for a in order:
        total += 0 if prev_id is None else od[(prev_id, a.id)]
        prev_id = a.id
    return total


def benchmark(n, days, seed=0):
    atts = gen_attractions(n, seed=seed)
    od = build_od(atts)
    clusters = kmeans_cluster(atts, days, seed=42)

    print(f"\n=== N={n}, D={days}  OR-Tools TSP-TW 实测（可丢弃节点）===")
    print(f"聚类分天：{[len(c) for c in clusters]} 个/天")
    day_times, scheduled = [], 0
    for d, cluster in enumerate(clusters):
        if not cluster:
            continue
        order, dropped, el = ortools_solve_day(cluster, od, DAY_START_MIN, DAY_END_MIN)
        day_times.append(el)
        scheduled += len(order) if order else 0
        mark = "" if dropped == 0 else f"，丢弃 {dropped} 个（放不下）"
        print(f"  Day{d + 1}: {len(cluster)} 个景点 → {el * 1000:7.1f} ms，"
              f"排出 {len(order) if order else 0} 个{mark}")
    print(f"单日求解：sum={sum(day_times) * 1000:.1f} ms，"
          f"max={max(day_times) * 1000:.1f} ms（并行以 max 计）")
    print(f"总排出：{scheduled}/{n}")
    return sum(day_times), max(day_times)


def compare_with_greedy():
    """用真实样例数据对比贪心 vs OR-Tools 的交通耗时（演示 OR-Tools 价值）。"""
    atts = SAMPLE_ATTRACTIONS
    od = build_od(atts)
    clusters = kmeans_cluster(atts, 3, seed=42)
    print("\n=== 贪心 vs OR-Tools（样例数据，按天对比交通耗时/分钟）===")
    for d, cluster in enumerate(clusters):
        if not cluster:
            continue
        # 贪心
        g_visits, _, _ = solve_day_tsp_tw(cluster, DAY_START_MIN, DAY_END_MIN, od,
                                          ORIGIN_TRANSIT_MIN)
        g_order = [a for a, _ in g_visits]
        # OR-Tools
        o_order, dropped, _ = ortools_solve_day(cluster, od, DAY_START_MIN, DAY_END_MIN)
        o_order = o_order or []
        print(f"  Day{d + 1}: 贪心排 {len(g_order)} 个/耗时 {route_travel(g_order, od):.0f}min  |  "
              f"OR-Tools 排 {len(o_order)} 个/耗时 {route_travel(o_order, od):.0f}min（丢弃 {dropped}）")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    d = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    _, max_t = benchmark(n, d)
    verdict = "✅ <30s" if max_t < 30 else "❌ 超时"
    print(f"\n结论：并行 max {max_t * 1000:.1f} ms  →  {verdict}")


if __name__ == "__main__":
    main()
