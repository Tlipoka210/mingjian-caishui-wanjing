"""外部数据导入脚本 — 解析FraudGCN Excel → PostgreSQL。"""
from __future__ import annotations

import logging
import os

from sqlalchemy import func, select

from app.db.urls import get_sync_engine
from app.db.session import Base
from app.models.external_enterprise import ExternalEnterpriseFinancials

logger = logging.getLogger(__name__)


def import_external_data(force: bool = False) -> int:
    """导入外部上市公司数据。返回导入行数。跳过已存在数据（除非force=True）。"""
    from app.etl.adapters.listed_company_adapter import prepare_enterprises

    engine = get_sync_engine()
    Base.metadata.create_all(engine, tables=[ExternalEnterpriseFinancials.__table__])

    with engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(ExternalEnterpriseFinancials)).scalar()

    if count > 0 and not force:
        logger.info("External data already exists (%d rows), skipping import", count)
        return 0

    logger.info("Starting external data import...")
    enterprises = prepare_enterprises()

    if force:
        with engine.begin() as conn:
            conn.execute(ExternalEnterpriseFinancials.__table__.delete())
            logger.info("Cleared existing external data (force=True)")

    # 批量插入
    with engine.begin() as conn:
        conn.execute(ExternalEnterpriseFinancials.__table__.insert(), enterprises)

    logger.info("Imported %d external enterprises", len(enterprises))
    return len(enterprises)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import_external_data(force=True)
