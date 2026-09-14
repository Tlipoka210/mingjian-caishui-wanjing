"""可复用实证引擎 — AUC计算与数据源对比统计。"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core_metrics import CoreMetrics
from app.models.external_enterprise import ExternalEnterpriseFinancials

logger = logging.getLogger(__name__)


def _safe_auc(labels: list[int], scores: list[float]) -> float | None:
    """计算ROC-AUC，样本不足或标签单一返回None。"""
    if len(labels) < 10:
        return None
    unique_labels = set(labels)
    if len(unique_labels) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score
        return round(float(roc_auc_score(labels, scores)), 4)
    except Exception as e:
        logger.warning("AUC calculation failed: %s", e)
        return None


def _score_distribution(scores: list[float], bins: int = 10) -> list[dict[str, Any]]:
    """计算得分分布直方图数据。"""
    if not scores:
        return []
    arr = np.array(scores)
    hist, edges = np.histogram(arr, bins=bins, range=(0, 100))
    result = []
    for i in range(len(hist)):
        result.append({
            "range_start": round(float(edges[i]), 1),
            "range_end": round(float(edges[i + 1]), 1),
            "count": int(hist[i]),
        })
    return result


async def compute_external_stats(db: AsyncSession) -> dict[str, Any]:
    """计算外部数据源的AUC和统计信息。"""
    rows = (await db.execute(
        select(ExternalEnterpriseFinancials)
    )).scalars().all()

    if not rows:
        return {"available": False, "message": "外部数据未导入"}

    labels = [r.label for r in rows]
    scores = [float(r.computed_score) for r in rows]

    fraud_count = sum(1 for l in labels if l == 1)
    normal_count = len(labels) - fraud_count

    auc = _safe_auc(labels, scores)

    # 按风险等级统计
    level_counts = {}
    for r in rows:
        lvl = r.computed_level or "low"
        level_counts[lvl] = level_counts.get(lvl, 0) + 1

    # 欺诈/正常企业的平均得分
    fraud_scores = [s for l, s in zip(labels, scores) if l == 1]
    normal_scores = [s for l, s in zip(labels, scores) if l == 0]

    return {
        "available": True,
        "sample_count": len(rows),
        "fraud_count": fraud_count,
        "normal_count": normal_count,
        "fraud_rate": round(fraud_count / len(rows), 4) if rows else 0,
        "auc": auc,
        "avg_fraud_score": round(float(np.mean(fraud_scores)), 2) if fraud_scores else 0,
        "avg_normal_score": round(float(np.mean(normal_scores)), 2) if normal_scores else 0,
        "score_distribution": _score_distribution(scores),
        "level_distribution": level_counts,
        "year": 2021,
        "source": "FraudGCN (XNetLab/MRG-for-Finance, GitHub)",
        "data_description": "4,043家中国A股上市公司2021年财务数据",
    }


async def compute_internal_stats(db: AsyncSession) -> dict[str, Any]:
    """计算内部数据源（193家匿名企业）的统计信息。"""
    rows = (await db.execute(
        select(CoreMetrics)
    )).scalars().all()

    if not rows:
        return {"available": False, "message": "内部数据未导入"}

    # 使用CoreMetrics的实际字段计算财务健康度
    finance_scores = []
    for r in rows:
        # 基于关键财务指标计算风险分数
        risk = 0.0
        # 负债率过高 → 风险
        dr = float(r.debt_ratio or 0)
        if dr > 0.7:
            risk += 25
        elif dr > 0.5:
            risk += 10
        # 利润率为负 → 风险
        pm = float(r.profit_margin or 0)
        if pm < 0:
            risk += 20
        # 营收同比下降 → 风险
        ry = float(r.revenue_yoy or 0)
        if ry < -0.2:
            risk += 15
        finance_scores.append(min(100, risk))

    # 统计有完整财务报表的企业数
    has_fs = sum(1 for r in rows if getattr(r, "has_financial_statements", False))

    return {
        "available": True,
        "sample_count": len(rows),
        "has_financial_statements": has_fs,
        "avg_debt_ratio": round(float(np.mean([float(r.debt_ratio or 0) for r in rows])), 4),
        "avg_profit_margin": round(float(np.mean([float(r.profit_margin or 0) for r in rows])), 4),
        "score_distribution": _score_distribution(finance_scores),
        "source": "明鉴内部脱敏数据（193家匿名企业）",
        "dimensions": ["税务健康", "经营真实性", "发票健康", "行业地位", "法律合规", "财务健康"],
    }


async def compute_external_auc_details(db: AsyncSession) -> dict[str, Any]:
    """计算外部数据AUC的详细信息（用于前端图表展示）。"""
    rows = (await db.execute(
        select(ExternalEnterpriseFinancials)
    )).scalars().all()

    if not rows:
        return {"available": False}

    labels = np.array([r.label for r in rows])
    scores = np.array([float(r.computed_score) for r in rows])

    auc = _safe_auc(labels.tolist(), scores.tolist())
    if auc is None:
        return {"available": False, "message": "AUC计算失败（标签单一或样本不足）"}

    # 计算ROC曲线点
    from sklearn.metrics import roc_curve
    fpr, tpr, thresholds = roc_curve(labels, scores)
    roc_points = [
        {"fpr": round(float(f), 4), "tpr": round(float(t), 4)}
        for f, t in zip(fpr[::max(1, len(fpr) // 50)], tpr[::max(1, len(tpr) // 50)])
    ]

    # 最佳阈值（Youden's J）
    j_scores = tpr - fpr
    best_idx = int(np.argmax(j_scores))

    # 混淆矩阵（使用最佳阈值）
    best_threshold = float(thresholds[best_idx])
    pred = (scores >= best_threshold).astype(int)
    tp = int(((pred == 1) & (labels == 1)).sum())
    fp = int(((pred == 1) & (labels == 0)).sum())
    tn = int(((pred == 0) & (labels == 0)).sum())
    fn = int(((pred == 0) & (labels == 1)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "available": True,
        "auc": auc,
        "roc_curve": roc_points,
        "best_threshold": round(best_threshold, 2),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "optimal_point": {
            "fpr": round(float(fpr[best_idx]), 4),
            "tpr": round(float(tpr[best_idx]), 4),
        },
    }
