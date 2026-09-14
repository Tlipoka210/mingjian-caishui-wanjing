"""FraudGCN 上市公司数据 Adapter — CSMAR字段 → 明鉴指标映射。

读取 Excel，计算四能力比率，返回标准化数据供引擎评估。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

EXTERNAL_DATA_DIR = os.getenv("EXTERNAL_DATA_DIR", "/app/data/external")
FEATURE_FILE = "data_raw_feature.xlsx"

# CSMAR字段 → 明鉴指标映射（基于CSMAR年报数据字典）
CSMAR_BALANCE_SHEET = {
    "A001000000": "total_assets",       # 资产总计
    "A001100000": "current_assets",     # 流动资产合计
    "A001200000": "noncurrent_assets",  # 非流动资产合计
    "A001110000": "trading_assets",     # 交易性金融资产
    "A001111000": "notes_receivable",   # 应收票据
    "A001112000": "accounts_receivable",# 应收账款
    "A001121000": "inventory",          # 存货
    "A002000000": "total_liab",         # 负债合计
    "A002100000": "current_liab",       # 流动负债合计
    "A002200000": "noncurrent_liab",    # 非流动负债合计
    "A003000000": "equity",             # 所有者权益合计
}

CSMAR_INCOME_STATEMENT = {
    "B001000000": "revenue",            # 营业收入
    "B002000000": "cost",              # 营业成本
    "B001100000": "operating_profit",   # 营业利润
    "B006000000": "net_profit",         # 净利润
    "B001300000": "total_profit",       # 利润总额
}

CSMAR_CASHFLOW = {
    "C001000000": "operating_cf",       # 经营活动现金流量净额
}

# 所有CSMAR字段映射
CSMAR_FIELD_MAP: dict[str, str] = {}
CSMAR_FIELD_MAP.update(CSMAR_BALANCE_SHEET)
CSMAR_FIELD_MAP.update(CSMAR_INCOME_STATEMENT)
CSMAR_FIELD_MAP.update(CSMAR_CASHFLOW)

# 核心财务比率（用于引擎评估）
COMPUTED_RATIOS = [
    "current_ratio", "quick_ratio", "debt_ratio",
    "gross_margin", "net_margin", "roe", "roa",
    "asset_turnover",
]


def _ratio(num: float, den: float, lo: float = -10.0, hi: float = 10.0) -> float:
    """安全比率计算，与pipeline.py对齐。den绝对值<=1返回0（弃权）。"""
    if abs(den) <= 1.0:
        return 0.0
    return max(lo, min(hi, num / den))


def load_raw_features(filepath: str | None = None) -> pd.DataFrame:
    """读取FraudGCN原始特征Excel。"""
    if filepath is None:
        filepath = os.path.join(EXTERNAL_DATA_DIR, FEATURE_FILE)
    logger.info("Loading external features from %s", filepath)
    df = pd.read_excel(filepath, engine="openpyxl")
    logger.info("Loaded %d rows, %d columns", len(df), len(df.columns))
    return df


def map_csmar_fields(df: pd.DataFrame) -> pd.DataFrame:
    """将CSMAR编码列重命名为明鉴指标名，保留未映射列。"""
    rename_map = {}
    for csmar_code, mingjian_name in CSMAR_FIELD_MAP.items():
        if csmar_code in df.columns:
            rename_map[csmar_code] = mingjian_name
    df = df.rename(columns=rename_map)
    # 确保映射后的字段存在，缺失的填0
    for _, mingjian_name in CSMAR_FIELD_MAP.items():
        if mingjian_name not in df.columns:
            df[mingjian_name] = 0.0
    return df


def compute_financial_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """计算明鉴四能力比率，与pipeline.py口径对齐。"""
    ta = df["total_assets"]
    cl = df["current_liab"]
    tl = df["total_liab"]
    ca = df["current_assets"]
    inv = df["inventory"]
    ar = df.get("accounts_receivable", pd.Series(0, index=df.index))
    rev = df["revenue"]
    cost = df["cost"]
    np_ = df["net_profit"]
    equity = df["equity"]

    # 偿债能力
    df["current_ratio"] = _ratio_series(ca, cl)
    df["quick_ratio"] = _ratio_series(ca - inv, cl)
    df["debt_ratio"] = _ratio_series(tl, ta)

    # 盈利能力
    df["gross_margin"] = _ratio_series(rev - cost, rev)
    df["net_margin"] = _ratio_series(np_, rev)
    df["roe"] = _ratio_series(np_, equity)
    df["roa"] = _ratio_series(np_, ta)

    # 营运能力（应收账款周转率需要期初数据，此处用单期近似）
    df["asset_turnover"] = _ratio_series(rev, ta)
    df["receivables_turnover"] = _ratio_series(rev, ar)
    df["inventory_turnover"] = _ratio_series(cost, inv)

    # 成长能力（单年数据无法计算同比，标记为0=弃权）
    df["revenue_yoy"] = 0.0
    df["profit_yoy"] = 0.0

    return df


def _ratio_series(num: pd.Series, den: pd.Series) -> pd.Series:
    """向量化安全比率，den绝对值<=1返回0。"""
    mask = den.abs() > 1.0
    result = pd.Series(0.0, index=num.index)
    result[mask] = (num[mask] / den[mask]).clip(-10, 10)
    return result


def score_enterprise(row: dict[str, Any]) -> tuple[float, str]:
    """用明鉴引擎的比率阈值给单家企业打分。

    返回 (score 0-100, risk_level)。
    score越高 = 风险越高；但为了AUC计算，我们返回风险分数。
    使用多维度加权评分（对齐assessment.py的财务维度）。
    """
    from app.services.financial_benchmarks import (
        FINANCIAL_RATIOS,
        assess_financial_ratio,
    )

    warnings = 0
    total_checks = 0
    risk_score = 0.0

    for field, cfg in FINANCIAL_RATIOS.items():
        value = row.get(field)
        if value is None or value == 0:
            continue  # 跳过弃权项
        total_checks += 1
        level = assess_financial_ratio(field, value, owner_equity=row.get("equity"))
        if level == "预警":
            warnings += 1
            risk_score += 20  # 每个预警 +20分
        elif level == "账务异常":
            warnings += 1
            risk_score += 40  # 异常 +40分
        elif level == "计算失效":
            risk_score += 10  # 失效 +10分

    # 额外风险信号
    debt = row.get("debt_ratio", 0)
    if debt > 0.9:
        risk_score += 30  # 极高负债率
    elif debt > 0.8:
        risk_score += 15

    roe = row.get("roe", 0)
    if roe < -0.1:
        risk_score += 25  # 严重亏损

    np_ = row.get("net_margin", 0)
    if np_ < -0.2:
        risk_score += 20  # 净利率极低

    # 归一化到0-100
    score = min(100.0, risk_score)

    # 风险等级
    if score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    return score, level


def prepare_enterprises(filepath: str | None = None) -> list[dict[str, Any]]:
    """完整流水线：读取→映射→计算比率→打分。返回企业数据列表。"""
    df = load_raw_features(filepath)
    df = map_csmar_fields(df)
    df = compute_financial_ratios(df)

    enterprises = []
    for _, row in df.iterrows():
        data = row.to_dict()
        score, level = score_enterprise(data)
        enterprises.append({
            "stock_code": str(int(row.get("Stkcd", 0))),
            "year": int(row.get("year", 2021)),
            "label": int(row.get("label", 0)),
            # 原始字段
            "total_assets": float(row.get("total_assets", 0)),
            "total_liab": float(row.get("total_liab", 0)),
            "current_assets": float(row.get("current_assets", 0)),
            "current_liab": float(row.get("current_liab", 0)),
            "equity": float(row.get("equity", 0)),
            "revenue": float(row.get("revenue", 0)),
            "cost": float(row.get("cost", 0)),
            "net_profit": float(row.get("net_profit", 0)),
            "operating_profit": float(row.get("operating_profit", 0)),
            "operating_cf": float(row.get("operating_cf", 0)),
            "accounts_receivable": float(row.get("accounts_receivable", 0)),
            "inventory": float(row.get("inventory", 0)),
            # 计算比率
            "current_ratio": float(row.get("current_ratio", 0)),
            "quick_ratio": float(row.get("quick_ratio", 0)),
            "debt_ratio": float(row.get("debt_ratio", 0)),
            "gross_margin": float(row.get("gross_margin", 0)),
            "net_margin": float(row.get("net_margin", 0)),
            "roe": float(row.get("roe", 0)),
            "roa": float(row.get("roa", 0)),
            "asset_turnover": float(row.get("asset_turnover", 0)),
            "receivables_turnover": float(row.get("receivables_turnover", 0)),
            "inventory_turnover": float(row.get("inventory_turnover", 0)),
            # 引擎评分
            "computed_score": score,
            "computed_level": level,
        })

    logger.info("Prepared %d enterprises (fraud=%d, normal=%d)",
                len(enterprises),
                sum(1 for e in enterprises if e["label"] == 1),
                sum(1 for e in enterprises if e["label"] == 0))
    return enterprises
