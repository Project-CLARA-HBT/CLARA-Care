from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import User, VnDrugMapping, VnDrugMappingAlias
from clara_api.db.session import SessionLocal

DAVIDRUG_ENDPOINT = (
    "https://dichvucong.dav.gov.vn/api/services/app/soDangKy/GetAllPublicServerPaging"
)
DEFAULT_PAGE_SIZE = 100
DEFAULT_COMMIT_EVERY = 500
DEFAULT_TIMEOUT_SECONDS = 45.0

_ACTIVE_INGREDIENT_SPLIT = re.compile(
    r"\s*(?:\+|/|;|,|\band\b|\bvà\b|\bva\b|\bwith\b)\s*",
    flags=re.IGNORECASE,
)


@dataclass
class DavFetchPage:
    total_count: int
    items: list[dict[str, Any]]


@dataclass
class SeedStats:
    fetched_rows: int = 0
    parsed_rows: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_empty_brand: int = 0
    skipped_alias_conflict: int = 0
    commit_count: int = 0
    page_count: int = 0


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _truncate(value: str, max_length: int) -> str:
    if max_length <= 0:
        return ""
    if len(value) <= max_length:
        return value
    return value[:max_length].strip()


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split()).strip()


def _safe_json_dumps(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


def _fetch_davidrug_page(skip_count: int, page_size: int, timeout_seconds: float) -> DavFetchPage:
    payload = {
        "filterText": "",
        "SoDangKyThuoc": {},
        "KichHoat": True,
        "skipCount": max(0, int(skip_count)),
        "maxResultCount": max(1, min(100, int(page_size))),
        "sorting": None,
    }
    request = urllib.request.Request(
        DAVIDRUG_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "clara-vn-dictionary-seeder/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"DAVIDrug HTTP {exc.code}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DAVIDrug network error: {exc}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DAVIDrug returned invalid JSON: {body[:400]}") from exc

    result_obj = parsed.get("result")
    result = result_obj if isinstance(result_obj, dict) else {}
    total_count = int(result.get("totalCount") or 0)
    items_obj = result.get("items")
    items = items_obj if isinstance(items_obj, list) else []
    normalized_items = [item for item in items if isinstance(item, dict)]
    return DavFetchPage(total_count=total_count, items=normalized_items)


def _split_active_ingredients(raw: str) -> list[str]:
    text = _normalize_text(raw)
    if not text:
        return []
    parts = _ACTIVE_INGREDIENT_SPLIT.split(text)
    seen: set[str] = set()
    normalized: list[str] = []
    for part in parts:
        candidate = _normalize_text(part)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _build_aliases(brand_name: str, ten_khong_dau: str, so_dang_ky: str) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()
    for candidate in [brand_name, ten_khong_dau, so_dang_ky]:
        cleaned = _clean_text(candidate)
        if not cleaned:
            continue
        normalized = _normalize_text(cleaned)
        if normalized in seen:
            continue
        seen.add(normalized)
        aliases.append(_truncate(cleaned, 255))
    return aliases


def _ensure_import_user(db: Session, email: str) -> User:
    normalized_email = _normalize_text(email)
    user = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
    if user is not None:
        return user

    raise RuntimeError(
        "Import user does not exist. "
        f"Please create it first and re-run with --import-user-email={normalized_email!r}.",
    )


def _load_existing_maps(
    db: Session,
) -> tuple[dict[str, VnDrugMapping], dict[str, int]]:
    mappings = db.execute(select(VnDrugMapping)).scalars().all()
    by_brand = {
        mapping.normalized_brand: mapping
        for mapping in mappings
        if mapping.normalized_brand
    }

    aliases = db.execute(select(VnDrugMappingAlias)).scalars().all()
    alias_owner = {
        alias.normalized_alias: alias.mapping_id
        for alias in aliases
        if alias.normalized_alias and alias.mapping_id
    }
    return by_brand, alias_owner


def _upsert_row(
    db: Session,
    row: dict[str, Any],
    *,
    by_brand: dict[str, VnDrugMapping],
    alias_owner: dict[str, int],
    import_user_id: int,
    stats: SeedStats,
    dry_run: bool,
) -> None:
    brand_name = _clean_text(row.get("tenThuoc"))
    if not brand_name:
        stats.skipped_empty_brand += 1
        return
    brand_name = _truncate(brand_name, 255)
    normalized_brand = _normalize_text(brand_name)
    if not normalized_brand:
        stats.skipped_empty_brand += 1
        return
    normalized_brand = _truncate(normalized_brand, 255)

    info_obj = row.get("thongTinThuocCoBan")
    info = info_obj if isinstance(info_obj, dict) else {}
    active_raw = _clean_text(info.get("hoatChatChinh")) or _clean_text(row.get("hoatChatChinh"))
    active_parts = _split_active_ingredients(active_raw)
    normalized_name = " ".join(active_parts).strip() or normalized_brand
    normalized_name = _truncate(_normalize_text(normalized_name), 255)
    active_ingredients = ", ".join(active_parts).strip() or normalized_name

    so_dang_ky = _clean_text(row.get("soDangKy"))
    ten_khong_dau = _clean_text(row.get("tenKhongDau"))
    aliases = _build_aliases(brand_name, ten_khong_dau, so_dang_ky)

    note_payload = {
        "source": "davidrug",
        "so_dang_ky": so_dang_ky or None,
        "dang_bao_che": _clean_text(info.get("dangBaoChe")) or None,
        "ham_luong": _clean_text(info.get("hamLuong")) or None,
        "dong_goi": _clean_text(info.get("dongGoi")) or None,
    }

    mapping = by_brand.get(normalized_brand)
    now = datetime.now(tz=UTC)

    if mapping is None:
        mapping = VnDrugMapping(
            brand_name=brand_name,
            normalized_brand=normalized_brand,
            active_ingredients=active_ingredients,
            normalized_name=normalized_name,
            rx_cui="",
            mapping_source="import",
            notes=_safe_json_dumps(note_payload),
            is_active=True,
            created_by_user_id=import_user_id,
            updated_at=now,
        )
        if not dry_run:
            db.add(mapping)
            db.flush()
        by_brand[normalized_brand] = mapping
        stats.inserted += 1
    else:
        changed = False
        if not _clean_text(mapping.active_ingredients) and active_ingredients:
            mapping.active_ingredients = active_ingredients
            changed = True
        if _normalize_text(mapping.normalized_name or "") == _normalize_text(
            mapping.normalized_brand,
        ):
            if normalized_name and normalized_name != _normalize_text(
                mapping.normalized_name or "",
            ):
                mapping.normalized_name = normalized_name
                changed = True
        if not mapping.is_active:
            mapping.is_active = True
            changed = True
        if mapping.mapping_source in {"manual", "curated"}:
            # Keep curated source untouched.
            pass
        elif mapping.mapping_source != "import":
            mapping.mapping_source = "import"
            changed = True
        if changed:
            mapping.updated_at = now
            if not dry_run:
                db.add(mapping)
            stats.updated += 1

    if dry_run:
        return

    if mapping.id is None:
        db.flush()
    mapping_id = int(mapping.id)

    for index, alias_name in enumerate(aliases):
        normalized_alias = _normalize_text(alias_name)
        owner_mapping_id = alias_owner.get(normalized_alias)
        if owner_mapping_id is not None and owner_mapping_id != mapping_id:
            stats.skipped_alias_conflict += 1
            continue
        if owner_mapping_id == mapping_id:
            continue
        alias = VnDrugMappingAlias(
            mapping_id=mapping_id,
            alias_name=_truncate(alias_name, 255),
            normalized_alias=_truncate(normalized_alias, 255),
            is_primary=index == 0,
        )
        db.add(alias)
        alias_owner[normalized_alias] = mapping_id


def _iter_davidrug_rows(
    *,
    page_size: int,
    max_records: int,
    timeout_seconds: float,
    sleep_seconds: float,
    stats: SeedStats,
) -> Iterable[dict[str, Any]]:
    skip_count = 0
    fetched_total = 0
    expected_total = None

    while True:
        page = _fetch_davidrug_page(
            skip_count=skip_count,
            page_size=page_size,
            timeout_seconds=timeout_seconds,
        )
        stats.page_count += 1
        if expected_total is None:
            expected_total = page.total_count
            print(f"[seed] DAV totalCount={expected_total}", flush=True)
        if not page.items:
            break

        for item in page.items:
            yield item
            fetched_total += 1
            stats.fetched_rows += 1
            if max_records > 0 and fetched_total >= max_records:
                return

        skip_count += len(page.items)
        if expected_total is not None and skip_count >= expected_total:
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


def run_seed(
    *,
    page_size: int,
    max_records: int,
    timeout_seconds: float,
    sleep_seconds: float,
    commit_every: int,
    dry_run: bool,
    import_user_email: str,
) -> SeedStats:
    stats = SeedStats()
    db = SessionLocal()
    try:
        import_user = _ensure_import_user(db, import_user_email)
        by_brand, alias_owner = _load_existing_maps(db)
        print(
            "[seed] existing mappings="
            f"{len(by_brand)} aliases={len(alias_owner)} dry_run={dry_run}",
            flush=True,
        )

        processed_since_commit = 0
        for row in _iter_davidrug_rows(
            page_size=page_size,
            max_records=max_records,
            timeout_seconds=timeout_seconds,
            sleep_seconds=sleep_seconds,
            stats=stats,
        ):
            _upsert_row(
                db,
                row,
                by_brand=by_brand,
                alias_owner=alias_owner,
                import_user_id=int(import_user.id),
                stats=stats,
                dry_run=dry_run,
            )
            stats.parsed_rows += 1
            processed_since_commit += 1

            if not dry_run and processed_since_commit >= commit_every:
                db.commit()
                stats.commit_count += 1
                processed_since_commit = 0
                print(
                    "[seed] progress fetched="
                    f"{stats.fetched_rows} parsed={stats.parsed_rows} "
                    f"inserted={stats.inserted} updated={stats.updated}",
                    flush=True,
                )

        if not dry_run:
            db.commit()
            stats.commit_count += 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return stats


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed toàn bộ biệt dược VN từ DAVIDrug vào vn_drug_mappings.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Số bản ghi mỗi page (tối đa 100).",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Giới hạn số bản ghi cần import. 0 = import toàn bộ.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.05,
        help="Delay giữa các page để tránh quá tải nguồn.",
    )
    parser.add_argument("--commit-every", type=int, default=DEFAULT_COMMIT_EVERY)
    parser.add_argument(
        "--import-user-email",
        required=True,
        help="Email của user đã tồn tại để ghi created_by_user_id cho dữ liệu import.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--summary-json",
        default="",
        help="Đường dẫn file JSON để ghi summary sau khi chạy.",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    page_size = max(1, min(100, int(args.page_size)))
    max_records = max(0, int(args.max_records))
    timeout_seconds = max(5.0, float(args.timeout_seconds))
    sleep_seconds = max(0.0, float(args.sleep_seconds))
    commit_every = max(1, int(args.commit_every))
    summary_path = Path(args.summary_json).expanduser() if args.summary_json else None

    started_at = datetime.now(tz=UTC)
    print(
        "[seed] start "
        f"page_size={page_size} max_records={max_records or 'ALL'} "
        f"timeout={timeout_seconds}s commit_every={commit_every}",
        flush=True,
    )
    stats = run_seed(
        page_size=page_size,
        max_records=max_records,
        timeout_seconds=timeout_seconds,
        sleep_seconds=sleep_seconds,
        commit_every=commit_every,
        dry_run=bool(args.dry_run),
        import_user_email=str(args.import_user_email).strip(),
    )
    ended_at = datetime.now(tz=UTC)
    duration_seconds = round((ended_at - started_at).total_seconds(), 3)

    summary = {
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": duration_seconds,
        "dry_run": bool(args.dry_run),
        "page_size": page_size,
        "max_records": max_records,
        "timeout_seconds": timeout_seconds,
        "sleep_seconds": sleep_seconds,
        "commit_every": commit_every,
        "stats": {
            "page_count": stats.page_count,
            "fetched_rows": stats.fetched_rows,
            "parsed_rows": stats.parsed_rows,
            "inserted": stats.inserted,
            "updated": stats.updated,
            "skipped_empty_brand": stats.skipped_empty_brand,
            "skipped_alias_conflict": stats.skipped_alias_conflict,
            "commit_count": stats.commit_count,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[seed] summary saved to {summary_path}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
