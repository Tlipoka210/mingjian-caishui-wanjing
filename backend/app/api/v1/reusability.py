"""可复用实证 API — 对比两个数据源的引擎区分度。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.reusability_engine import (
    compute_external_auc_details,
    compute_external_stats,
    compute_internal_stats,
)

router = APIRouter(prefix="/reusability", tags=["reusability"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    """两个数据源的对比摘要。"""
    external = await compute_external_stats(db)
    internal = await compute_internal_stats(db)

    return {
        "internal": internal,
        "external": external,
        "conclusion": {
            "headline": "同一引擎 · 两个数据源 · 都有区分度",
            "detail": (
                "明鉴引擎的财务指标评估逻辑在公开A股数据上同样具有区分能力。"
                "三口径真实性（申报/发票/银行流水比对）只有涉税数据能做，"
                "这恰是明鉴系统的最硬护城河。"
            ),
        },
    }


@router.get("/external-metrics")
async def get_external_metrics(db: AsyncSession = Depends(get_db)):
    """外部数据的详细指标。"""
    return await compute_external_stats(db)


@router.get("/auc-details")
async def get_auc_details(db: AsyncSession = Depends(get_db)):
    """AUC计算详情（ROC曲线、混淆矩阵）。"""
    return await compute_external_auc_details(db)
