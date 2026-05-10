"""PG-backed Repo 동치성 테스트.

PG 미가용 시 (env 미설정 또는 driver 미설치) 전체 모듈 skip.
in-memory Repo 와 동일 입력 → 동일 출력 검증.

실행:
    docker-compose up -d simulation-postgres
    SIM_DB_HOST=localhost SIM_DB_PORT=5433 SIM_DB_USER=simulation \
      SIM_DB_PASSWORD=simulation_dev SIM_DB_NAME=simulation \
      pytest tests/simulation/test_postgres_repo.py -q
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.simulation.storage.postgres.connection import is_pg_enabled

pytestmark = pytest.mark.skipif(
    not is_pg_enabled(),
    reason="PG 미가용 — SIMULATION_DATABASE_URL 또는 SIM_DB_HOST 미설정 / psycopg 미설치",
)


@pytest.fixture(scope="module", autouse=True)
def _seed_db():
    """모듈 시작 시 1회 시드. teardown 은 다음 모듈이 reset_schema 로 정리."""
    from backend.simulation.storage.postgres.seed import seed_all

    seed_all(reset=True)
    yield


def test_plant_mapping_repo():
    from backend.simulation.sandbox.fixtures import fixtures as fx
    from backend.simulation.sandbox.fixtures.repository_pg import PlantMappingPgRepo

    mem = fx.make_default_plant_mapping()
    pg = PlantMappingPgRepo()

    for sm_cd in ("A", "B", "C", "D", "K"):
        mem_v = mem.get(sm_cd)
        pg_v = pg.get(sm_cd)
        assert mem_v is not None and pg_v is not None
        assert mem_v.castCd == pg_v.castCd
        assert mem_v.machineCd == pg_v.machineCd

    assert pg.has("K") is True
    assert pg.has("ZZ") is False


def test_cast_spec_repo():
    from backend.simulation.sandbox.fixtures.repository_pg import CastSpecPgRepo

    pg = CastSpecPgRepo()
    row = pg.lookup("K", "K01", "K", "CC1", "M1", "A001")
    assert row is not None
    assert row.slabThickness == Decimal("220")

    miss = pg.lookup("K", "K01", "ZZ", "CC1", "M1", "A001")
    assert miss is None


def test_hr_spec_repo():
    from backend.simulation.sandbox.fixtures import fixtures as fx
    from backend.simulation.sandbox.fixtures.repository_pg import HrSpecPgRepo

    mem = fx.make_default_hr_spec()
    pg = HrSpecPgRepo()

    # mem 의 첫 row 키로 양쪽 비교
    sample = next(iter(mem._rows.values()))
    pg_row = pg.lookup(sample.cmpCd, sample.orgCd, sample.hrPlantCd, sample.prodTypeCd)
    assert pg_row is not None
    assert pg_row.widthLow == sample.widthLow
    assert pg_row.widthHigh == sample.widthHigh


def test_hr_min_wgt_2d_lookup():
    from backend.simulation.sandbox.fixtures.repository_pg import HrMinWgtPgRepo

    pg = HrMinWgtPgRepo()
    # cell ≥ input ORDER BY ASC LIMIT 1 — 가장 작은 cover cell
    result = pg.lookup("K", "K01", "K", Decimal("100"), Decimal("100"))
    # 시드 데이터 안에 100x100 이상 cell 이 1개 이상 존재
    assert result is not None
    assert result.thickness >= Decimal("100")
    assert result.width >= Decimal("100")


def test_edging_spec_wildcard_fallback():
    from backend.simulation.sandbox.fixtures.repository_pg import EdgingSpecPgRepo
    from backend.simulation.sandbox.fixtures.domain import EdgingSpecMissingError

    pg = EdgingSpecPgRepo()
    # 정확 매칭이 없는 그룹코드 → '*' fallback
    row = pg.find_spec("K", "K01", "NON_EXISTENT_GROUP")
    assert row is not None
    assert row.edgingGroupCd == "*"

    # 없는 회사 — '*' fallback 도 없음 → MissingError
    with pytest.raises(EdgingSpecMissingError):
        pg.find_spec("ZZ", "ZZ", "WHATEVER")


def test_productivity_std_default_fallback():
    from backend.simulation.sandbox.fixtures.repository_pg import ProductivityStdPgRepo

    pg = ProductivityStdPgRepo()
    # lookup miss → None
    miss = pg.lookup("K", "K01", "NON_PROC", "G01", "PK01", "C001")
    assert miss is None

    # lookup_or_default → 0.95
    default = pg.lookup_or_default("K", "K01", "NON_PROC", "G01", "PK01", "C001")
    assert default == Decimal("0.95")


def test_seed_idempotent():
    """seed_all(reset=True) 두 번 호출해도 동작 OK + 행 수 동일."""
    from backend.simulation.storage.postgres.seed import seed_all

    counts1 = seed_all(reset=True)
    counts2 = seed_all(reset=True)
    assert counts1 == counts2
    assert counts1["order_os"] == 5  # 샘플 주문 5건
