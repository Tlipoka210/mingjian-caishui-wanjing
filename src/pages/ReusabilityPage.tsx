import { useEffect, useState } from 'react';
import { reusabilityApi } from '@/api/reusability';
import PieChart from '@/components/charts/PieChart';
import BarChart from '@/components/charts/BarChart';
import Skeleton from '@/components/ui/Skeleton';
import Card from '@/components/ui/Card';

interface SummaryData {
  internal: {
    available: boolean;
    sample_count: number;
    has_financial_statements?: number;
    avg_tax_health?: number;
    avg_finance_score?: number;
    source?: string;
    dimensions?: string[];
  };
  external: {
    available: boolean;
    sample_count: number;
    fraud_count: number;
    normal_count: number;
    fraud_rate: number;
    auc: number | null;
    avg_fraud_score?: number;
    avg_normal_score?: number;
    score_distribution?: { range_start: number; range_end: number; count: number }[];
    level_distribution?: Record<string, number>;
    source?: string;
    data_description?: string;
  };
  conclusion: {
    headline: string;
    detail: string;
  };
}

interface AucDetails {
  available: boolean;
  auc: number;
  roc_curve: { fpr: number; tpr: number }[];
  best_threshold: number;
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  precision: number;
  recall: number;
  f1: number;
}

export default function ReusabilityPage() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [aucDetails, setAucDetails] = useState<AucDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [summaryRes, aucRes] = await Promise.all([
          reusabilityApi.getSummary(),
          reusabilityApi.getAucDetails(),
        ]);
        setSummary(summaryRes as SummaryData);
        setAucDetails(aucRes as AucDetails);
      } catch (e) {
        setError(e instanceof Error ? e.message : '加载失败');
      } finally {
        setIsLoading(false);
      }
    };
    void fetchData();
  }, []);

  if (isLoading) {
    return (
      <div className="h-full overflow-auto p-6 space-y-6">
        <Skeleton height="48px" className="rounded-xl" />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton height="200px" className="rounded-xl" />
          <Skeleton height="200px" className="rounded-xl" />
        </div>
        <Skeleton height="300px" className="rounded-xl" />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-warm-400 text-lg">加载失败</p>
          <p className="text-warm-500 text-sm mt-2">{error || '请稍后重试'}</p>
        </div>
      </div>
    );
  }

  const ext = summary.external;
  const int_ = summary.internal;

  const aucColor = (ext.auc ?? 0) >= 0.7 ? 'text-emerald-600' : (ext.auc ?? 0) >= 0.6 ? 'text-amber-600' : 'text-warm-400';
  const aucLabel = (ext.auc ?? 0) >= 0.8 ? '优秀' : (ext.auc ?? 0) >= 0.7 ? '良好' : (ext.auc ?? 0) >= 0.6 ? '中等' : '偏低';

  const levelPieData = ext.level_distribution
    ? Object.entries(ext.level_distribution).map(([k, v]) => ({
        name: k === 'high' ? '高风险' : k === 'medium' ? '中风险' : '低风险',
        value: v,
      }))
    : [];

  const scoreDistData = ext.score_distribution
    ? {
        categories: ext.score_distribution.map((d) => `${Math.round(d.range_start)}-${Math.round(d.range_end)}`),
        values: ext.score_distribution.map((d) => d.count),
      }
    : null;

  return (
    <div className="h-full overflow-auto p-6 space-y-6">
      {/* 标题区 */}
      <div className="text-center py-4">
        <h1 className="text-2xl font-bold text-warm-800">{summary.conclusion.headline}</h1>
        <p className="text-warm-500 mt-2 text-sm max-w-2xl mx-auto">{summary.conclusion.detail}</p>
      </div>

      {/* 对比卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 内部数据 */}
        <Card index={0} className="p-6 border border-warm-200">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-full bg-amber-400" />
            <h2 className="font-semibold text-warm-700">内部数据 · 明鉴脱敏</h2>
          </div>
          {int_.available ? (
            <div className="grid grid-cols-2 gap-4">
              <Stat label="样本量" value={`${int_.sample_count}家`} />
              <Stat label="财务报表" value={`${int_.has_financial_statements ?? '—'}家`} />
              <Stat label="平均税务健康" value={int_.avg_tax_health != null ? `${int_.avg_tax_health}` : '—'} />
              <Stat label="平均财务得分" value={int_.avg_finance_score != null ? `${int_.avg_finance_score}` : '—'} />
            </div>
          ) : (
            <p className="text-warm-400 text-sm">数据未导入</p>
          )}
          <p className="text-warm-400 text-xs mt-4">{int_.source}</p>
        </Card>

        {/* 外部数据 */}
        <Card index={1} className="p-6 border-2 border-amber-200">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <h2 className="font-semibold text-warm-700">外部数据 · A股公开</h2>
          </div>
          {ext.available ? (
            <div className="grid grid-cols-2 gap-4">
              <Stat label="样本量" value={`${ext.sample_count}家`} />
              <Stat label="欺诈样本" value={`${ext.fraud_count}家 (${(ext.fraud_rate * 100).toFixed(1)}%)`} />
              <div className="col-span-2">
                <div className="flex items-baseline gap-2">
                  <span className="text-sm text-warm-500">引擎AUC</span>
                  <span className={`text-3xl font-bold ${aucColor}`}>{ext.auc?.toFixed(4) ?? '—'}</span>
                  <span className={`text-sm font-medium ${aucColor}`}>{aucLabel}</span>
                </div>
              </div>
              <Stat label="欺诈企业均分" value={ext.avg_fraud_score?.toFixed(1) ?? '—'} />
              <Stat label="正常企业均分" value={ext.avg_normal_score?.toFixed(1) ?? '—'} />
            </div>
          ) : (
            <p className="text-warm-400 text-sm">外部数据未导入</p>
          )}
          <p className="text-warm-400 text-xs mt-4">{ext.source}</p>
        </Card>
      </div>

      {/* AUC详情 */}
      {aucDetails?.available && (
        <Card index={2} className="p-6 border border-warm-200">
          <h2 className="font-semibold text-warm-700 mb-4">AUC 详情</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Stat label="最佳阈值" value={aucDetails.best_threshold?.toFixed(2) ?? '—'} />
            <Stat label="精确率" value={(aucDetails.precision * 100).toFixed(1) + '%'} />
            <Stat label="召回率" value={(aucDetails.recall * 100).toFixed(1) + '%'} />
            <Stat label="F1" value={(aucDetails.f1 * 100).toFixed(1) + '%'} />
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm text-warm-600">
            <div>
              <p className="font-medium mb-1">混淆矩阵</p>
              <p>TP={aucDetails.confusion_matrix.tp} FP={aucDetails.confusion_matrix.fp}</p>
              <p>FN={aucDetails.confusion_matrix.fn} TN={aucDetails.confusion_matrix.tn}</p>
            </div>
            <div>
              <p className="font-medium mb-1">含义解读</p>
              <p className="text-warm-500">
                AUC={ext.auc?.toFixed(4)} 表示：随机抽取一家欺诈企业与一家正常企业，
                引擎给欺诈企业的风险分数高于正常企业的概率为 {(ext.auc ?? 0) * 100}%。
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* 图表区 */}
      {ext.available && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {levelPieData.length > 0 && (
            <Card index={3} className="p-6 border border-warm-200">
              <h3 className="font-semibold text-warm-700 mb-2">外部数据 · 风险等级分布</h3>
              <PieChart data={levelPieData} height={240} innerRadius="45%" />
            </Card>
          )}
          {scoreDistData && (
            <Card index={4} className="p-6 border border-warm-200">
              <h3 className="font-semibold text-warm-700 mb-2">外部数据 · 引擎得分分布</h3>
              <BarChart data={scoreDistData} height={240} />
            </Card>
          )}
        </div>
      )}

      {/* 诚实边界 */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
        <p className="font-medium mb-1">诚实边界</p>
        <p>
          三口径真实性（增值税申报/发票/银行流水比对）无法在公开数据上复现——
          申报数据、发票明细、银行流水不公开。这恰是明鉴系统的最硬护城河。
          可复用的是：财务指标评估、经营分析指标的引擎逻辑。
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-warm-400">{label}</p>
      <p className="text-lg font-semibold text-warm-800">{value}</p>
    </div>
  );
}
