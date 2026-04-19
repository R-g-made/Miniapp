#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import logging
import argparse
from typing import Any, Dict, Optional, Tuple

import requests

API_URL = "https://stickers.tools/api/stats-new"
TIMEOUT = 20

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def fetch_payload() -> Dict[str, Any]:
    headers = {
        "User-Agent": "sticker-floor-bot/2.0",
        "Accept": "application/json",
        "Referer": "https://stickers.tools/",
        "Origin": "https://stickers.tools",
    }
    r = requests.get(API_URL, timeout=TIMEOUT, headers=headers)
    r.raise_for_status()
    return r.json()


def pick_path(obj: Any, path: list) -> Any:
    cur = obj
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def get_pack_floor(pack: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    # приоритет: current -> 24h -> 7d -> 30d
    prio_ton = [
        ["current", "price", "floor", "ton"],
        ["24h", "price", "floor", "ton"],
        ["7d", "price", "floor", "ton"],
        ["30d", "price", "floor", "ton"],
    ]
    prio_usd = [
        ["current", "price", "floor", "usd"],
        ["24h", "price", "floor", "usd"],
        ["7d", "price", "floor", "usd"],
        ["30d", "price", "floor", "usd"],
    ]

    ton = next((pick_path(pack, p) for p in prio_ton if pick_path(pack, p) is not None), None)
    usd = next((pick_path(pack, p) for p in prio_usd if pick_path(pack, p) is not None), None)

    try:
        ton = float(ton) if ton is not None else None
    except Exception:
        ton = None
    try:
        usd = float(usd) if usd is not None else None
    except Exception:
        usd = None

    return ton, usd


def build_output_all(payload: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "timestamp": int(time.time()),
        "packs": {},
        "stats": {
            "collections_total": 0,
            "packs_total": 0,
            "packs_with_floor": 0,
            "packs_missing_floor": 0,
        },
        "missing_floor": []
    }

    collections = payload.get("collections", {})
    if not isinstance(collections, dict):
        raise ValueError("payload['collections'] is not a dict")

    out["stats"]["collections_total"] = len(collections)

    for col in collections.values():
        if not isinstance(col, dict):
            continue

        cname = col.get("name")
        if not (isinstance(cname, str) and cname.strip()):
            continue

        stickers = col.get("stickers") or {}
        if not isinstance(stickers, dict):
            continue

        for pack in stickers.values():
            if not isinstance(pack, dict):
                continue

            pname = pack.get("name")
            if not (isinstance(pname, str) and pname.strip()):
                continue

            out["stats"]["packs_total"] += 1

            ton, usd = get_pack_floor(pack)

            # сохраняем даже если floor пустой (на твоё усмотрение)
            out.setdefault("packs", {}).setdefault(cname, {})[pname] = {
                "floor_ton": ton,
                "floor_usd": usd,
            }

            if ton is None and usd is None:
                out["stats"]["packs_missing_floor"] += 1
                out["missing_floor"].append({"collection": cname, "pack": pname})
            else:
                out["stats"]["packs_with_floor"] += 1

    return out


def parse_args():
    ap = argparse.ArgumentParser(description="Dump ALL collections/packs floors from stickers.tools API.")
    ap.add_argument("-o", "--output", default="floors_all_packs.json",
                    help="Output JSON path (default floors_all_packs.json)")
    ap.add_argument("--only-with-floor", action="store_true",
                    help="If set, remove packs where floor_ton and floor_usd are both null")
    return ap.parse_args()


def main():
    args = parse_args()
    payload = fetch_payload()
    out = build_output_all(payload)

    if args.only_with_floor:
        # подчистим пустые
        packs_clean = {}
        for cname, packs in out["packs"].items():
            keep = {pname: v for pname, v in packs.items()
                    if not (v.get("floor_ton") is None and v.get("floor_usd") is None)}
            if keep:
                packs_clean[cname] = keep
        out["packs"] = packs_clean

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    logging.info("Saved %s", args.output)
    logging.info("Collections: %d | Packs: %d | With floor: %d | Missing floor: %d",
                 out["stats"]["collections_total"],
                 out["stats"]["packs_total"],
                 out["stats"]["packs_with_floor"],
                 out["stats"]["packs_missing_floor"])


if __name__ == "__main__":
    main()