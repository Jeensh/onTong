"""Repo factory — 환경변수에 따라 in-memory / PG 분기.

`SIMULATION_DATABASE_URL` 또는 `SIM_DB_HOST` 설정 시 PG-backed Repo 반환.
미설정 시 기존 in-memory Repo 반환 → 기존 189 pytest 호환.

호출부는 `get_*_repo(in_memory_rows)` 처럼 fallback 데이터를 함께 전달.
in-memory 모드면 그 데이터를 그대로 반환, PG 모드면 데이터는 무시 (DB 가 권위).
"""

from __future__ import annotations

from typing import Optional, Union

from backend.simulation.storage.postgres.connection import is_pg_enabled

from . import repository as mem
from . import repository_pg as pg


def get_plant_mapping_repo(
    mappings: Optional[dict] = None,
) -> Union[mem.PlantMappingRepo, pg.PlantMappingPgRepo]:
    if is_pg_enabled():
        return pg.PlantMappingPgRepo()
    return mem.PlantMappingRepo(mappings)


def get_cast_spec_repo(rows=None) -> Union[mem.CastSpecRepo, pg.CastSpecPgRepo]:
    if is_pg_enabled():
        return pg.CastSpecPgRepo()
    return mem.CastSpecRepo(rows)


def get_productivity_std_repo(rows=None) -> Union[mem.ProductivityStdRepo, pg.ProductivityStdPgRepo]:
    if is_pg_enabled():
        return pg.ProductivityStdPgRepo()
    return mem.ProductivityStdRepo(rows)


def get_hr_spec_repo(rows=None) -> Union[mem.HrSpecRepo, pg.HrSpecPgRepo]:
    if is_pg_enabled():
        return pg.HrSpecPgRepo()
    return mem.HrSpecRepo(rows)


def get_hr_min_wgt_repo(rows=None) -> Union[mem.HrMinWgtRepo, pg.HrMinWgtPgRepo]:
    if is_pg_enabled():
        return pg.HrMinWgtPgRepo()
    return mem.HrMinWgtRepo(rows)


def get_hr_max_wgt_repo(rows=None) -> Union[mem.HrMaxWgtRepo, pg.HrMaxWgtPgRepo]:
    if is_pg_enabled():
        return pg.HrMaxWgtPgRepo()
    return mem.HrMaxWgtRepo(rows)


def get_edging_group_repo(rows=None) -> Union[mem.EdgingGroupRepo, pg.EdgingGroupPgRepo]:
    if is_pg_enabled():
        return pg.EdgingGroupPgRepo()
    return mem.EdgingGroupRepo(rows)


def get_edging_spec_repo(rows=None) -> Union[mem.EdgingSpecRepo, pg.EdgingSpecPgRepo]:
    if is_pg_enabled():
        return pg.EdgingSpecPgRepo()
    return mem.EdgingSpecRepo(rows)


def get_customer_std_repo(rows=None) -> Union[mem.CustomerStdRepo, pg.CustomerStdPgRepo]:
    if is_pg_enabled():
        return pg.CustomerStdPgRepo()
    return mem.CustomerStdRepo(rows)
