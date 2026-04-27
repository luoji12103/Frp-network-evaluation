import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { metricSeriesLatest } from '../lib/format';
import type { MetricSeries } from '../lib/types';

export function TimeSeriesChart({
  title,
  series,
  unit,
  height = 280,
}: {
  title: string;
  series: MetricSeries[];
  unit?: string | null;
  height?: number;
}) {
  const option: EChartsOption = {
    animationDuration: 300,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#0f172a',
      borderWidth: 0,
      textStyle: { color: '#f8fafc' },
    },
    legend: {
      top: 0,
      textStyle: { color: '#475569' },
    },
    grid: {
      left: 12,
      right: 12,
      top: 48,
      bottom: 16,
      containLabel: true,
    },
    xAxis: {
      type: 'time',
      axisLabel: { color: '#64748b' },
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: unit || undefined,
      nameTextStyle: { color: '#64748b' },
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: '#e2e8f0' } },
    },
    series: series.map((item, index) => ({
      name: `${item.name}${metricSeriesLatest(item) !== null ? ` · ${metricSeriesLatest(item)}` : ''}`,
      type: 'line',
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2.5 },
      emphasis: { focus: 'series' },
      data: item.points.map((point) => [point.timestamp, point.value]),
      color: ['#0f766e', '#0369a1', '#9333ea', '#d97706', '#b91c1c'][index % 5],
    })),
  };

  return <ReactECharts option={option} notMerge style={{ height }} className="w-full" aria-label={title} />;
}
