"""Build the versioned R0.2-04 Hangzhou candidate catalog from Gaode POI search."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.data_governance import (  # noqa: E402
    build_candidate_coverage,
    canonical_json_sha256,
    load_json_object,
    validate_candidate_catalog,
    validate_candidate_coverage,
)

GAODE_PLACE_TEXT_URL = "https://restapi.amap.com/v3/place/text"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class Seed:
    name: str
    region: str
    place_kind: str
    geometry_kind: str
    category: str
    query: str
    match_term: str
    night: bool
    rain: bool
    audiences: tuple[str, ...]
    periods: tuple[str, ...]


def _s(
    name: str,
    region: str,
    place_kind: str,
    geometry_kind: str,
    category: str,
    *,
    query: str | None = None,
    match: str | None = None,
    night: bool = False,
    rain: bool = False,
    audiences: tuple[str, ...] = ("首次来杭", "情侣/朋友"),
    periods: tuple[str, ...] = ("daytime",),
) -> Seed:
    return Seed(
        name=name,
        region=region,
        place_kind=place_kind,
        geometry_kind=geometry_kind,
        category=category,
        query=query or name,
        match_term=match or name,
        night=night,
        rain=rain,
        audiences=audiences,
        periods=periods,
    )


WEST_LAKE = "west_lake_lakeside_north_hill"
LINGYIN = "lingyin_tianzhu"
XIXI = "xixi_wetland"
OLD_TOWN = "southern_song_wushan"
CANAL = "grand_canal_gongchen_bridge"
WULIN = "wulin_lakeside_commercial"
QIANJIANG = "qianjiang_new_city"
LIANGZHU = "liangzhu"
XIANGHU = "xianghu"
ZHIJIANG = "zhijiang_songcheng"
TEA_COUNTRY = "longjing_meijiawu_jiuxi"

SEEDS: tuple[Seed, ...] = (
    _s("西湖", WEST_LAKE, "scenic_area", "area", "自然山水"),
    _s(
        "湖滨公园",
        WEST_LAKE,
        "neighborhood",
        "area",
        "城市观景",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s("断桥残雪", WEST_LAKE, "attraction", "point", "自然山水"),
    _s(
        "平湖秋月",
        WEST_LAKE,
        "attraction",
        "point",
        "自然山水",
        query="杭州西湖平湖秋月",
        match="平湖秋月",
    ),
    _s("曲院风荷", WEST_LAKE, "attraction", "point", "自然山水"),
    _s("苏堤春晓", WEST_LAKE, "walking_route", "route", "自然山水"),
    _s(
        "浙江省博物馆孤山馆区",
        WEST_LAKE,
        "attraction",
        "point",
        "博物馆",
        query="浙江省博物馆孤山馆区",
        match="孤山馆区",
        rain=True,
        audiences=("首次来杭", "亲子", "长辈"),
    ),
    _s(
        "西湖音乐喷泉表演",
        WEST_LAKE,
        "show",
        "point",
        "演出演艺",
        query="西湖音乐喷泉表演",
        match="音乐喷泉表演",
        night=True,
        periods=("evening",),
    ),
    _s("保俶塔", WEST_LAKE, "attraction", "point", "城市观景"),
    _s("雷峰塔", WEST_LAKE, "attraction", "point", "城市观景"),
    _s("花港观鱼", WEST_LAKE, "scenic_area", "area", "自然山水"),
    _s("三潭印月", WEST_LAKE, "attraction", "point", "自然山水"),
    _s("灵隐寺", LINGYIN, "attraction", "point", "寺庙祈福", rain=True),
    _s(
        "飞来峰景区",
        LINGYIN,
        "scenic_area",
        "area",
        "寺庙祈福",
        query="飞来峰",
        match="飞来峰",
    ),
    _s("永福寺", LINGYIN, "attraction", "point", "寺庙祈福", rain=True),
    _s("韬光寺", LINGYIN, "attraction", "point", "寺庙祈福", rain=True),
    _s(
        "上天竺法喜讲寺",
        LINGYIN,
        "attraction",
        "point",
        "寺庙祈福",
        query="法喜讲寺",
        match="法喜",
        rain=True,
    ),
    _s(
        "中天竺法净禅寺",
        LINGYIN,
        "attraction",
        "point",
        "寺庙祈福",
        query="法净禅寺",
        match="法净",
        rain=True,
    ),
    _s(
        "三天竺法镜讲寺",
        LINGYIN,
        "attraction",
        "point",
        "寺庙祈福",
        query="法镜讲寺",
        match="法镜",
        rain=True,
    ),
    _s("西溪国家湿地公园", XIXI, "scenic_area", "area", "自然山水"),
    _s(
        "西溪国家湿地公园洪园",
        XIXI,
        "scenic_area",
        "area",
        "自然山水",
        query="西溪湿地洪园",
        match="洪园",
    ),
    _s("高庄", XIXI, "attraction", "point", "古镇人文", query="西溪高庄"),
    _s(
        "西溪天堂",
        XIXI,
        "neighborhood",
        "area",
        "网红打卡",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "清河坊历史文化特色街区",
        OLD_TOWN,
        "neighborhood",
        "area",
        "古镇人文",
        query="清河坊历史文化街区",
        match="清河坊",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "南宋御街",
        OLD_TOWN,
        "neighborhood",
        "area",
        "古镇人文",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s("胡雪岩旧居", OLD_TOWN, "attraction", "point", "古镇人文", rain=True),
    _s(
        "杭州博物馆",
        OLD_TOWN,
        "attraction",
        "point",
        "博物馆",
        rain=True,
        audiences=("首次来杭", "亲子", "长辈"),
    ),
    _s("城隍阁", OLD_TOWN, "attraction", "point", "城市观景"),
    _s(
        "南宋德寿宫遗址博物馆",
        OLD_TOWN,
        "attraction",
        "point",
        "博物馆",
        query="德寿宫遗址博物馆",
        match="德寿宫",
        rain=True,
    ),
    _s(
        "南宋官窑博物馆",
        OLD_TOWN,
        "attraction",
        "point",
        "博物馆",
        rain=True,
    ),
    _s(
        "十五奎巷",
        OLD_TOWN,
        "neighborhood",
        "area",
        "古镇人文",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s("鼓楼", OLD_TOWN, "attraction", "point", "古镇人文"),
    _s(
        "吴山广场",
        OLD_TOWN,
        "attraction",
        "point",
        "城市观景",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "京杭大运河杭州景区",
        CANAL,
        "scenic_area",
        "area",
        "古镇人文",
        query="京杭大运河杭州景区",
        match="京杭大运河",
    ),
    _s("拱宸桥", CANAL, "attraction", "point", "古镇人文"),
    _s(
        "中国京杭大运河博物馆",
        CANAL,
        "attraction",
        "point",
        "博物馆",
        rain=True,
    ),
    _s("中国刀剪剑博物馆", CANAL, "attraction", "point", "博物馆", rain=True),
    _s("中国伞博物馆", CANAL, "attraction", "point", "博物馆", rain=True),
    _s("中国扇博物馆", CANAL, "attraction", "point", "博物馆", rain=True),
    _s(
        "桥西历史文化街区",
        CANAL,
        "neighborhood",
        "area",
        "古镇人文",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "小河历史文化街区",
        CANAL,
        "neighborhood",
        "area",
        "古镇人文",
        query="小河历史文化街区",
        match="小河历史文化街区",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "杭州运河游船",
        CANAL,
        "experience",
        "point",
        "城市观景",
        query="杭州运河游船",
        match="杭州运河游船",
        night=True,
        periods=("evening",),
    ),
    _s(
        "浙江自然博物院杭州馆",
        WULIN,
        "attraction",
        "point",
        "博物馆",
        query="浙江自然博物院杭州馆",
        match="浙江自然博物院",
        rain=True,
        audiences=("首次来杭", "亲子"),
    ),
    _s(
        "浙江省科技馆",
        WULIN,
        "attraction",
        "point",
        "亲子乐园",
        rain=True,
        audiences=("亲子", "雨天"),
    ),
    _s(
        "武林夜市",
        WULIN,
        "market",
        "area",
        "美食街区",
        night=True,
        periods=("evening",),
    ),
    _s(
        "武林广场",
        WULIN,
        "attraction",
        "point",
        "城市观景",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "城市阳台",
        QIANJIANG,
        "scenic_area",
        "area",
        "城市观景",
        query="杭州城市阳台",
        match="城市阳台",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "钱江新城灯光秀",
        QIANJIANG,
        "show",
        "point",
        "演出演艺",
        query="钱江新城灯光秀",
        match="灯光秀",
        night=True,
        periods=("evening",),
    ),
    _s("杭州大剧院", QIANJIANG, "attraction", "point", "演出演艺", rain=True),
    _s(
        "中国杭州低碳科技馆",
        QIANJIANG,
        "attraction",
        "point",
        "亲子乐园",
        query="杭州低碳科技馆",
        match="低碳科技馆",
        rain=True,
        audiences=("亲子", "雨天"),
    ),
    _s(
        "杭州奥林匹克体育中心体育场",
        QIANJIANG,
        "attraction",
        "point",
        "网红打卡",
        query="杭州奥林匹克体育中心体育场",
        match="奥林匹克体育中心体育场",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "良渚博物院",
        LIANGZHU,
        "attraction",
        "point",
        "博物馆",
        rain=True,
        audiences=("首次来杭", "亲子", "长辈"),
    ),
    _s("良渚古城遗址公园", LIANGZHU, "scenic_area", "area", "古镇人文"),
    _s(
        "良渚文化艺术中心",
        LIANGZHU,
        "attraction",
        "point",
        "网红打卡",
        rain=True,
    ),
    _s(
        "玉鸟集",
        LIANGZHU,
        "market",
        "area",
        "美食街区",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s("良渚文化村", LIANGZHU, "neighborhood", "area", "古镇人文"),
    _s("湘湖国家旅游度假区", XIANGHU, "scenic_area", "area", "自然山水"),
    _s("跨湖桥遗址博物馆", XIANGHU, "attraction", "point", "博物馆", rain=True),
    _s(
        "杭州乐园",
        XIANGHU,
        "attraction",
        "point",
        "亲子乐园",
        audiences=("亲子", "情侣/朋友"),
    ),
    _s(
        "杭州长乔极地海洋公园",
        XIANGHU,
        "attraction",
        "point",
        "亲子乐园",
        query="长乔极地海洋公园",
        match="极地海洋公园",
        rain=True,
        audiences=("亲子", "雨天"),
    ),
    _s(
        "湘湖游船",
        XIANGHU,
        "experience",
        "point",
        "城市观景",
        query="湘湖游船",
        match="湘湖游船",
        periods=("daytime",),
    ),
    _s(
        "杭州宋城",
        ZHIJIANG,
        "scenic_area",
        "area",
        "古镇人文",
        query="杭州宋城",
        match="宋城",
        night=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "宋城千古情",
        ZHIJIANG,
        "show",
        "point",
        "演出演艺",
        night=True,
        rain=True,
        periods=("daytime", "evening"),
    ),
    _s(
        "浙江省博物馆之江馆区",
        ZHIJIANG,
        "attraction",
        "point",
        "博物馆",
        query="浙江省博物馆之江馆区",
        match="之江馆区",
        rain=True,
    ),
    _s(
        "浙江省非遗馆",
        ZHIJIANG,
        "attraction",
        "point",
        "博物馆",
        rain=True,
    ),
    _s(
        "龙井村",
        TEA_COUNTRY,
        "neighborhood",
        "area",
        "古镇人文",
        query="龙井村牌坊",
        match="龙井村牌坊",
        audiences=("首次来杭", "情侣/朋友", "长辈"),
    ),
    _s(
        "梅家坞茶文化村",
        TEA_COUNTRY,
        "neighborhood",
        "area",
        "古镇人文",
        query="梅家坞",
        match="梅家坞",
        audiences=("首次来杭", "情侣/朋友", "长辈"),
    ),
    _s("九溪烟树", TEA_COUNTRY, "attraction", "point", "自然山水"),
    _s(
        "九溪十八涧",
        TEA_COUNTRY,
        "walking_route",
        "route",
        "自然山水",
        audiences=("情侣/朋友", "徒步"),
    ),
    _s(
        "中国茶叶博物馆双峰馆区",
        TEA_COUNTRY,
        "attraction",
        "point",
        "博物馆",
        query="中国茶叶博物馆双峰馆区",
        match="双峰馆区",
        rain=True,
    ),
    _s(
        "中国茶叶博物馆龙井馆区",
        TEA_COUNTRY,
        "attraction",
        "point",
        "博物馆",
        query="中国茶叶博物馆龙井馆区",
        match="龙井馆区",
        rain=True,
    ),
    _s("云栖竹径", TEA_COUNTRY, "attraction", "point", "自然山水"),
)

RELATIONS: tuple[tuple[str, int, int, str, str], ...] = (
    ("hz-rel-001", 1, 2, "overlaps", "WEST_LAKE_LAKESIDE_BOUNDARY_OVERLAP"),
    ("hz-rel-002", 1, 6, "contains", "WEST_LAKE_CONTAINS_CAUSEWAY_EXPERIENCE"),
    ("hz-rel-003", 13, 14, "overlaps", "LINGYIN_FEILAI_EXPERIENCE_OVERLAP"),
    ("hz-rel-004", 20, 21, "contains", "XIXI_HONGYUAN_PARENT_CHILD"),
    ("hz-rel-005", 24, 25, "overlaps", "QINGHEFANG_SOUTHERN_SONG_STREET_OVERLAP"),
    ("hz-rel-006", 34, 40, "contains", "GRAND_CANAL_QIAOXI_PARENT_CHILD"),
    ("hz-rel-007", 47, 48, "same_experience", "CITY_BALCONY_LIGHT_SHOW_SHARED_VISIT"),
    ("hz-rel-008", 55, 56, "overlaps", "YUNNIAO_LIANGZHU_VILLAGE_OVERLAP"),
    ("hz-rel-009", 57, 61, "same_experience", "XIANGHU_DAY_AND_NIGHT_SHARED_AREA"),
    ("hz-rel-010", 62, 63, "contains", "SONGCHENG_SHOW_INSIDE_SCENIC_AREA"),
    ("hz-rel-011", 68, 69, "overlaps", "JIUXI_SPOT_AND_ROUTE_OVERLAP"),
)

PROVIDER_OVERRIDES: dict[str, dict[str, Any]] = {
    "西湖音乐喷泉表演": {
        "source_id": "gaode-web-service",
        "collection_mode": "api",
        "poi_id": "B023B08WZ7",
        "name": "西湖音乐喷泉表演",
        "address": "湖滨路与平海路交汇处",
        "admin_area": "上城区",
        "location": {"lng": 120.160970, "lat": 30.253778},
        "typecode": "",
        "evidence_ref": (
            "docs/test/reports/"
            "a6-8-1-gaode-browser-coordinate-review-2026-08-27.md"
        ),
    }
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/governance/hangzhou-candidate-catalog-v1.json"),
    )
    parser.add_argument(
        "--coverage-output",
        type=Path,
        default=Path("data/governance/hangzhou-candidate-coverage-v1.json"),
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("var/audit/hangzhou-candidate-gaode-selected-v1.json"),
    )
    parser.add_argument("--throttle-seconds", type=float, default=1.05)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("TRAVEL_AGENT_GAODE_API_KEY")
    if not api_key:
        parser.error("TRAVEL_AGENT_GAODE_API_KEY is required in the environment or .env")

    output = _rooted(args.output)
    coverage_output = _rooted(args.coverage_output)
    if not args.overwrite and (output.exists() or coverage_output.exists()):
        parser.error("candidate version already exists; create a new version or pass --overwrite")

    registry = load_json_object(
        PROJECT_ROOT / "data/governance/hangzhou-source-registry-v1.json"
    )
    dictionary = load_json_object(
        PROJECT_ROOT / "data/governance/place-collection-field-dictionary-v1.json"
    )
    cache_path = _rooted(args.cache)
    cache = {} if args.refresh else _load_cache(cache_path)
    generated_at = datetime.now(SHANGHAI_TZ).replace(microsecond=0).isoformat()

    selected: list[dict[str, Any]] = []
    with httpx.Client(timeout=15.0, headers={"User-Agent": "travel-agent-r0.2-04/1.0"}) as client:
        for index, seed in enumerate(SEEDS, start=1):
            cache_key = f"{seed.query}|{seed.match_term}"
            override = PROVIDER_OVERRIDES.get(seed.name)
            provider = (
                {**override, "observed_at": generated_at} if override is not None else None
            )
            if provider is None:
                cached = cache.get(cache_key)
                provider = cached if _cached_provider_is_acceptable(seed, cached) else None
            if provider is None:
                provider = _fetch_provider_candidate(
                    client,
                    api_key=api_key,
                    seed=seed,
                    observed_at=generated_at,
                )
                cache[cache_key] = provider
                _write_json(cache_path, cache)
                time.sleep(max(args.throttle_seconds, 0.0))
            selected.append(_candidate_payload(index, seed, provider))
            print(
                f"[{index:02d}/{len(SEEDS)}] {seed.name} -> "
                f"{provider['name']} ({provider['poi_id']})"
            )

    catalog = {
        "schema_version": "hangzhou-candidate-catalog-v1",
        "catalog_id": "hangzhou-m1-candidate-catalog-v1",
        "city_id": "hangzhou",
        "status": "candidate",
        "generated_at": generated_at,
        "source_registry": {
            "registry_id": registry["registry_id"],
            "registry_sha256": canonical_json_sha256(registry),
        },
        "field_dictionary": {
            "dictionary_id": dictionary["dictionary_id"],
            "dictionary_sha256": canonical_json_sha256(dictionary),
        },
        "collection_policy": {
            "source_id": "gaode-web-service",
            "collection_mode": "api",
            "target_stage": "staging",
            "provider_endpoint": "gaode-place-text-v3",
            "city_adcode": "330100",
            "raw_retention": "selected_candidate_fields_only",
        },
        "limitations": [
            "本目录只用于R0.2-04候选发现，不是正式地点事实或用户可选目录。",
            "canonical_name、类型、几何和分类均为待人工审核候选。",
            "高德location仅用于重复和覆盖初筛，不是到达或离开访问点。",
            "开放时间、最晚入园、例外日期、建议时长和真实入口尚未采集。",
            "relation_clues均未裁决，进入求解器前必须在OM1工作台形成决定。",
        ],
        "candidates": selected,
        "relation_clues": _relation_payloads(),
    }
    validate_candidate_catalog(catalog, registry, dictionary)
    coverage = build_candidate_coverage(catalog)
    validate_candidate_coverage(coverage, catalog)
    _write_json(output, catalog)
    _write_json(coverage_output, coverage)
    print(json.dumps(coverage["actuals"], ensure_ascii=False, sort_keys=True))
    print(f"exit_evaluation={coverage['exit_evaluation']['status']}")
    return 0


def _fetch_provider_candidate(
    client: httpx.Client,
    *,
    api_key: str,
    seed: Seed,
    observed_at: str,
) -> dict[str, Any]:
    payload: dict[str, Any] | None = None
    for attempt in range(4):
        response = client.get(
            GAODE_PLACE_TEXT_URL,
            params={
                "key": api_key,
                "keywords": seed.query,
                "city": "330100",
                "citylimit": "true",
                "offset": "20",
                "page": "1",
                "extensions": "base",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "1":
            break
        if payload.get("info") != "CUQPS_HAS_EXCEEDED_THE_LIMIT":
            raise RuntimeError(f"Gaode place search failed: {payload.get('info')}")
        time.sleep(1.5 * (attempt + 1))
    if payload is None or payload.get("status") != "1":
        raise RuntimeError(f"Gaode place search exhausted retries for {seed.name}")

    pois = payload.get("pois")
    if not isinstance(pois, list) or not pois:
        raise RuntimeError(f"Gaode place search returned no candidates for {seed.name}")
    selected = max(pois, key=lambda poi: _poi_score(seed, poi))
    score = _poi_score(seed, selected)
    if score <= 0:
        names = [poi.get("name") for poi in pois[:5]]
        raise RuntimeError(f"No acceptable Gaode candidate for {seed.name}; got {names}")

    location = selected.get("location")
    if not isinstance(location, str) or "," not in location:
        raise RuntimeError(f"Gaode candidate lacks location for {seed.name}")
    lng_text, lat_text = location.split(",", 1)
    return {
        "source_id": "gaode-web-service",
        "collection_mode": "api",
        "poi_id": str(selected.get("id", "")),
        "name": str(selected.get("name", "")),
        "address": _string_value(selected.get("address")),
        "admin_area": _string_value(selected.get("adname")),
        "location": {"lng": float(lng_text), "lat": float(lat_text)},
        "typecode": _string_value(selected.get("typecode")),
        "observed_at": observed_at,
    }


def _poi_score(seed: Seed, poi: dict[str, Any]) -> int:
    name = _string_value(poi.get("name"))
    normalized_name = _normalize(name)
    normalized_expected = _normalize(seed.name)
    normalized_match = _normalize(seed.match_term)
    forbidden = (
        "停车",
        "出入口",
        "售票",
        "卫生间",
        "地铁站",
        "公交站",
        "便利店",
        "公寓",
        "酒店",
        "客栈",
        "餐厅",
        "管委会",
        "村委会",
        "鸳鸯厅",
    )
    if any(term in name for term in forbidden) or name.endswith("店"):
        return -100
    score = 0
    if normalized_name == normalized_expected:
        score += 120
    if normalized_name == normalized_match:
        score += 110
    if normalized_match and normalized_match in normalized_name:
        score += 80
    if normalized_expected and (
        normalized_expected in normalized_name or normalized_name in normalized_expected
    ):
        score += 50
    if _string_value(poi.get("adcode")).startswith("3301"):
        score += 10
    return score


def _cached_provider_is_acceptable(seed: Seed, provider: Any) -> bool:
    if not isinstance(provider, dict):
        return False
    name = _string_value(provider.get("name"))
    pseudo_poi = {
        "name": name,
        "adcode": "330100",
    }
    return bool(provider.get("poi_id")) and _poi_score(seed, pseudo_poi) > 0


def _candidate_payload(index: int, seed: Seed, provider: dict[str, Any]) -> dict[str, Any]:
    flags = [
        "NAME_REQUIRES_HUMAN_VERIFICATION",
        "CATEGORY_REQUIRES_HUMAN_VERIFICATION",
        "GEOMETRY_UNVERIFIED",
        "ACCESS_POINT_UNVERIFIED",
        "TIME_RULES_NOT_COLLECTED",
        "DURATION_NOT_COLLECTED",
    ]
    if seed.geometry_kind != "point":
        flags.append("PROVIDER_POINT_IS_NOT_PLACE_GEOMETRY")
    if seed.place_kind in {"show", "market", "experience"}:
        flags.append("FIXED_TIME_OR_OPERATING_RULE_REQUIRED")
    if _normalize(seed.name) != _normalize(_string_value(provider.get("name"))):
        flags.append("PROVIDER_NAME_DIFFERS_FROM_CANDIDATE")
    if any(term in _string_value(provider.get("name")) for term in ("暂停", "关闭")):
        flags.append("PROVIDER_NAME_SIGNALS_STATUS_RISK")
    return {
        "candidate_id": f"hz-cand-{index:03d}",
        "canonical_name_candidate": seed.name,
        "place_kind_candidate": seed.place_kind,
        "geometry_kind_candidate": seed.geometry_kind,
        "primary_category": seed.category,
        "travel_region_id": seed.region,
        "coverage": {
            "night_or_fixed_time": seed.night,
            "indoor_or_rain": seed.rain,
            "audiences": list(seed.audiences),
            "suitable_periods": list(seed.periods),
        },
        "provider_candidate": provider,
        "review_state": "candidate",
        "review_flags": flags,
    }


def _relation_payloads() -> list[dict[str, str]]:
    return [
        {
            "clue_id": clue_id,
            "left_candidate_id": f"hz-cand-{left:03d}",
            "right_candidate_id": f"hz-cand-{right:03d}",
            "relation_candidate": relation,
            "reason_code": reason_code,
            "review_status": "unresolved",
        }
        for clue_id, left, right, relation, reason_code in RELATIONS
    ]


def _load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("candidate discovery cache must be an object")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalize(value: str) -> str:
    return re.sub(r"[\s()（）·—_\-]+", "", value).lower()


def _string_value(value: Any) -> str:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return "" if value is None else str(value)


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
