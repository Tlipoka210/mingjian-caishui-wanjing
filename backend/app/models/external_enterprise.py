"""外部上市公司财务数据模型 — 用于可复用实证（FraudGCN数据集）。"""
from __future__ import annotations

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ExternalEnterpriseFinancials(Base):
    """外部A股上市公司财务数据（FraudGCN数据集）。"""
    __tablename__ = "external_enterprise_financials"

    stock_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[int] = mapped_column(Integer, default=0)  # 0=正常, 1=欺诈

    # 原始资产负债表字段
    total_assets: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    total_liab: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    current_assets: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    current_liab: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    equity: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    accounts_receivable: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    inventory: Mapped[float] = mapped_column(Numeric(20, 2), default=0)

    # 原始利润表字段
    revenue: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    cost: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    net_profit: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    operating_profit: Mapped[float] = mapped_column(Numeric(20, 2), default=0)

    # 原始现金流字段
    operating_cf: Mapped[float] = mapped_column(Numeric(20, 2), default=0)

    # 计算的财务比率（与明鉴引擎对齐）
    current_ratio: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    quick_ratio: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    debt_ratio: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    gross_margin: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    net_margin: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    roe: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    roa: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    asset_turnover: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    receivables_turnover: Mapped[float] = mapped_column(Numeric(12, 4), default=0)
    inventory_turnover: Mapped[float] = mapped_column(Numeric(12, 4), default=0)

    # 引擎评分
    computed_score: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    computed_level: Mapped[str] = mapped_column(String(20), default="low")
