"""G3 Solver Spike —— 分层求解可行性验证原型。

目的：验证「K-Means 聚类分天 → 天内贪心 TSP-TW → 约束校验 → 回溯」这条分层路线
在真实规模数据上是否可行，并暴露已知弱点（聚类不均衡、贪心局部最优）。

注意：本原型用贪心启发式替代 OR-Tools（零依赖、可直接运行）。生产路径用
OR-Tools Routing Solver 替换 solve_day_tsp_tw，映射见技术选型文档 4.5。

运行：python solver.py
测试：python test_solver.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class Attraction:
    id: int
    name: str
    category: str
    lat: float
    lng: float
    energy: int          # 1-5 体力消耗
    duration: int        # 建议游览分钟
    open_min: int        # 当天0点起分钟
    close_min: int
    close_day: int = 0   # 0=无,1-7=周一..周日
    is_indoor: bool = False


@dataclass
class DayPlan:
    day: int                                   # 1-indexed
    weekday: int                               # 1-7
    visits: List[Tuple[Attraction, int]]       # (attraction, arrival_min)
    infeasible: List[Attraction]               # 因约束/容量被排除
    total_energy: int


MODE_BUDGET = {"speed": 8, "normal": 5, "leisure": 3}
STATION_TO_CITY_MIN = 90   # 机场/高铁站到市区耗时
STATION_EARLY_MIN = 90     # 离开前提前到站
ORIGIN_TRANSIT_MIN = 30    # 出发点到第一个景点耗时
DAY_START_MIN = 9 * 60     # 非首日出发时间
DAY_END_MIN = 21 * 60      # 非末日结束时间


def haversine_km(a: Attraction, b: Attraction) -> float:
    R = 6371.0
    lat1, lng1 = math.radians(a.lat), math.radians(a.lng)
    lat2, lng2 = math.radians(b.lat), math.radians(b.lng)
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def build_od(atts, speed_kmh=30.0, detour=1.3):
    """景点对交通耗时矩阵（分钟）。直线距离 × 绕行系数 / 速度。"""
    od = {}
    for a in atts:
        for b in atts:
            if a.id == b.id:
                od[(a.id, b.id)] = 0.0
            else:
                od[(a.id, b.id)] = haversine_km(a, b) / speed_kmh * 60 * detour
    return od


def kmeans_cluster(atts, k, seed=42):
    """按经纬度 K-Means 聚成 k 天（降维）。"""
    if k >= len(atts):
        return [[a] for a in atts]
    rng = np.random.default_rng(seed)
    pts = np.array([[a.lat, a.lng] for a in atts], dtype=float)
    pts_norm = (pts - pts.mean(axis=0)) / (pts.std(axis=0) + 1e-9)
    centers = pts_norm[rng.choice(len(atts), size=k, replace=False)]
    labels = np.zeros(len(atts), dtype=int)
    for _ in range(50):
        dists = np.linalg.norm(pts_norm[:, None, :] - centers[None, :, :], axis=2)
        labels = dists.argmin(axis=1)
        new_centers = centers.copy()
        for c in range(k):
            members = pts_norm[labels == c]
            if len(members):
                new_centers[c] = members.mean(axis=0)
        if np.allclose(centers, new_centers):
            break
        centers = new_centers
    clusters = [[] for _ in range(k)]
    for a, lb in zip(atts, labels):
        clusters[lb].append(a)
    return clusters


def filter_day(atts, weekday, weather):
    """硬约束过滤：闭馆日 + 极端天气排除室外。返回 (feasible, excluded)。"""
    extreme = weather == "extreme"
    feasible, excluded = [], []
    for a in atts:
        if a.close_day == weekday or (extreme and not a.is_indoor):
            excluded.append(a)
        else:
            feasible.append(a)
    return feasible, excluded


def solve_day_tsp_tw(atts, start_min, end_min, od, transit_min):
    """贪心最近可行 TSP-TW。返回 (visits, remaining, last_time)。
    每次选交通耗时最小的可行下一个景点；不可行则提前结束。"""
    remaining = list(atts)
    current = start_min
    last_id = None
    visits = []
    while remaining:
        best = None
        for a in remaining:
            travel = od[(last_id, a.id)] if last_id is not None else transit_min
            arr = current + travel
            if arr < a.open_min:
                arr = a.open_min  # 等开门
            leave = arr + a.duration
            if leave <= a.close_min and leave <= end_min:
                if best is None or (travel, a.id) < (best[0], best[1].id):
                    best = (travel, a, arr)
        if best is None:
            break
        _, a, arr = best
        visits.append((a, arr))
        remaining = [x for x in remaining if x.id != a.id]
        current = arr + a.duration
        last_id = a.id
    return visits, remaining, current


def rebalance(clusters, budget, max_iter=50):
    """简单再平衡（回溯）：把超预算天的高体力景点移到能量最低的天。"""
    for _ in range(max_iter):
        energies = [sum(a.energy for a in c) for c in clusters]
        over = [i for i in range(len(clusters)) if energies[i] > budget]
        if not over:
            break
        i = over[0]
        j = min(range(len(clusters)), key=lambda x: energies[x])
        if j == i:
            break
        moved = max(clusters[i], key=lambda a: a.energy)
        clusters[i].remove(moved)
        clusters[j].append(moved)
    return clusters


def check_constraints(plan, budget):
    """返回违反清单。close_day/时间窗在构造时已保证，这里主要暴露体力超载。"""
    v = []
    if plan.total_energy > budget:
        v.append(f"Day{plan.day} 体力超载 {plan.total_energy} > {budget}")
    for a, arr in plan.visits:
        if a.close_day == plan.weekday:
            v.append(f"Day{plan.day} {a.name} 排在闭馆日")
        leave = arr + a.duration
        if arr < a.open_min or leave > a.close_min:
            v.append(f"Day{plan.day} {a.name} 超出开放时间窗")
    return v


def layered_solve(atts, days, start_weekday, travel_mode, arrival_min, departure_min,
                  weather="clear", seed=42):
    """分层求解主流程：聚类 → 再平衡 → 逐天过滤 → 贪心排序 → 校验。"""
    budget = MODE_BUDGET[travel_mode]
    od = build_od(atts)
    clusters = kmeans_cluster(atts, days, seed=seed)
    clusters = rebalance(clusters, budget)
    plans = []
    for d in range(days):
        weekday = ((start_weekday - 1 + d) % 7) + 1
        feasible, excluded = filter_day(clusters[d], weekday, weather)
        start_min = (arrival_min + STATION_TO_CITY_MIN) if d == 0 else DAY_START_MIN
        end_min = (departure_min - STATION_EARLY_MIN) if d == days - 1 else DAY_END_MIN
        visits, infeasible, _ = solve_day_tsp_tw(feasible, start_min, end_min, od, ORIGIN_TRANSIT_MIN)
        total_energy = sum(a.energy for a, _ in visits)
        plans.append(DayPlan(d + 1, weekday, visits, excluded + infeasible, total_energy))
    return plans


def fmt(m):
    h, mm = divmod(int(round(m)), 60)
    return f"{h:02d}:{mm:02d}"


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from sample_data import SAMPLE_ATTRACTIONS
    mode = "normal"
    plans = layered_solve(
        SAMPLE_ATTRACTIONS, days=3, start_weekday=1, travel_mode=mode,
        arrival_min=14 * 60, departure_min=16 * 60, weather="light_rain", seed=42,
    )
    print("=" * 62)
    print("分层求解 Spike 输出（3天 / 正常模式 / 周一14:00到达 / 小雨）")
    print("=" * 62)
    for p in plans:
        wd = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"][p.weekday]
        print(f"\nDay {p.day}（{wd}）  体力 {p.total_energy}/{MODE_BUDGET[mode]}")
        for a, arr in p.visits:
            print(f"  {fmt(arr)}  {a.name}  [{a.category}]  体力{a.energy}  玩{a.duration}min")
        if p.infeasible:
            names = ", ".join(a.name for a in p.infeasible)
            print(f"  [!] 未排入（约束/容量）: {names}")
    print("\n" + "=" * 62)
    print("约束检查（应为空或仅体力超载）:")
    for p in plans:
        print(" ", check_constraints(p, MODE_BUDGET[mode]) or f"Day{p.day} OK")


if __name__ == "__main__":
    main()
