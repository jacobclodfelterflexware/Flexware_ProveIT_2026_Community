'use client';

import { useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import { Line, Bar, Scatter, Pie, Doughnut } from 'react-chartjs-2';
import type { ChartConfig } from '@/lib/chart-engine-api';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  TimeScale
);

interface ChartRendererProps {
  config: ChartConfig;
  className?: string;
}

/**
 * Renders the appropriate chart type based on config
 */
export default function ChartRenderer({ config, className = '' }: ChartRendererProps) {
  const chartData = useMemo(() => {
    return {
      labels: config.data.labels || [],
      datasets: config.data.datasets || [],
    };
  }, [config.data]);

  const chartOptions = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const opts: any = {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 300,
      },
      ...config.options,
    };
    // Ensure Y-axis has grace for better visualization of low-variance data
    if (opts.scales?.y && !opts.scales.y.grace && !opts.scales.y.beginAtZero) {
      opts.scales.y.grace = '10%';
    }
    return opts;
  }, [config.options]);

  // Render based on chart type
  switch (config.type) {
    case 'line':
      return (
        <div className={`w-full h-full ${className}`}>
          <Line data={chartData} options={chartOptions} />
        </div>
      );

    case 'bar':
      return (
        <div className={`w-full h-full ${className}`}>
          <Bar data={chartData} options={chartOptions} />
        </div>
      );

    case 'scatter':
      return (
        <div className={`w-full h-full ${className}`}>
          <Scatter data={chartData} options={chartOptions} />
        </div>
      );

    case 'pie':
      return (
        <div className={`w-full h-full ${className}`}>
          <Pie data={chartData} options={chartOptions} />
        </div>
      );

    case 'doughnut':
      return (
        <div className={`w-full h-full ${className}`}>
          <Doughnut data={chartData} options={chartOptions} />
        </div>
      );

    case 'gauge':
      return <GaugeChart config={config} className={className} />;

    case 'kpi':
      return <KPICard config={config} className={className} />;

    case 'heatmap':
      return <HeatmapChart config={config} className={className} />;

    case 'sparkline_grid':
      return <SparklineGrid config={config} className={className} />;

    default:
      return (
        <div className={`w-full h-full flex items-center justify-center text-gray-500 ${className}`}>
          <p>Unknown chart type: {config.type}</p>
        </div>
      );
  }
}

/**
 * Custom Gauge Chart component
 */
function GaugeChart({ config, className }: { config: ChartConfig; className?: string }) {
  const { value, percentage, min, max, unit, color } = config.data;

  const displayValue = typeof value === 'number' ? value.toFixed(1) : value;
  const pct = typeof percentage === 'number' ? percentage : 50;

  return (
    <div className={`w-full h-full flex flex-col items-center justify-center ${className}`}>
      <div className="relative w-48 h-24 overflow-hidden">
        {/* Background arc */}
        <div
          className="absolute inset-0 rounded-t-full"
          style={{
            background: `conic-gradient(from 180deg, #374151 0deg, #374151 180deg)`,
          }}
        />
        {/* Value arc */}
        <div
          className="absolute inset-0 rounded-t-full"
          style={{
            background: `conic-gradient(from 180deg, ${color || 'rgb(75, 192, 192)'} 0deg, ${color || 'rgb(75, 192, 192)'} ${pct * 1.8}deg, transparent ${pct * 1.8}deg)`,
          }}
        />
        {/* Center cutout */}
        <div className="absolute inset-4 bg-gray-900 rounded-t-full" />
      </div>
      <div className="text-center mt-2">
        <div className="text-3xl font-bold" style={{ color: color || 'rgb(75, 192, 192)' }}>
          {displayValue}{unit}
        </div>
        <div className="text-sm text-gray-500">
          {min} - {max}
        </div>
      </div>
    </div>
  );
}

/**
 * Custom KPI Card component
 */
function KPICard({ config, className }: { config: ChartConfig; className?: string }) {
  const { value, trend, trend_percentage, unit, format } = config.data as {
    value: number;
    trend?: string;
    trend_percentage?: number;
    unit?: string;
    format?: string;
  };

  const formatValue = (val: number) => {
    if (format === 'percentage') return `${val.toFixed(1)}%`;
    if (format === 'currency') return `$${val.toLocaleString()}`;
    return val.toLocaleString();
  };

  const trendColor = trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-gray-500';
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→';

  return (
    <div className={`w-full h-full flex flex-col items-center justify-center p-4 ${className}`}>
      <div className="text-4xl font-bold text-white">
        {formatValue(value)}{unit}
      </div>
      {trend && (
        <div className={`flex items-center gap-1 mt-2 ${trendColor}`}>
          <span className="text-xl">{trendIcon}</span>
          {trend_percentage !== undefined && (
            <span className="text-sm">{Math.abs(trend_percentage).toFixed(1)}%</span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Custom Heatmap component
 */
function HeatmapChart({ config, className }: { config: ChartConfig; className?: string }) {
  const { labels, matrix } = config.data as { labels: string[]; matrix: number[][] };

  if (!labels || !matrix) {
    return <div className={className}>No heatmap data</div>;
  }

  const getColor = (value: number) => {
    // Map -1 to 1 to color gradient
    const normalized = (value + 1) / 2; // 0 to 1
    const r = Math.round(255 * (1 - normalized));
    const g = Math.round(255 * normalized);
    const b = 100;
    return `rgb(${r}, ${g}, ${b})`;
  };

  return (
    <div className={`w-full h-full overflow-auto p-4 ${className}`}>
      <table className="mx-auto border-collapse">
        <thead>
          <tr>
            <th className="p-2"></th>
            {labels.map((label, i) => (
              <th key={i} className="p-2 text-xs text-gray-400 font-normal">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td className="p-2 text-xs text-gray-400">{labels[i]}</td>
              {row.map((value, j) => (
                <td
                  key={j}
                  className="p-2 text-xs text-center"
                  style={{
                    backgroundColor: getColor(value),
                    color: Math.abs(value) > 0.5 ? 'white' : 'black',
                  }}
                  title={`${labels[i]} vs ${labels[j]}: ${value.toFixed(3)}`}
                >
                  {value.toFixed(2)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Sparkline Grid component
 */
function SparklineGrid({ config, className }: { config: ChartConfig; className?: string }) {
  const { sparklines, columns } = config.data;

  if (!sparklines) {
    return <div className={className}>No sparkline data</div>;
  }

  const gridCols = columns || 3;

  return (
    <div
      className={`w-full h-full grid gap-4 p-4 ${className}`}
      style={{ gridTemplateColumns: `repeat(${gridCols}, 1fr)` }}
    >
      {sparklines.map((spark, i) => (
        <div key={i} className="bg-gray-800 rounded-lg p-3">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm text-gray-300 truncate">{spark.label}</span>
            <span className="text-lg font-bold text-white">{spark.current?.toFixed(1)}</span>
          </div>
          <div className="h-12">
            <MiniSparkline data={spark.data} />
          </div>
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Min: {spark.min?.toFixed(1)}</span>
            <span>Max: {spark.max?.toFixed(1)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Mini sparkline using SVG
 */
function MiniSparkline({ data }: { data: number[] }) {
  if (!data || data.length < 2) {
    return <div className="h-full bg-gray-700 rounded" />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((value, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 100 - ((value - min) / range) * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
      <polyline
        fill="none"
        stroke="rgb(75, 192, 192)"
        strokeWidth="2"
        points={points}
      />
    </svg>
  );
}
