'use client';

interface ChartSuggestion {
  id: string;
  query: string;
  description: string;
  reason: string;
  topicPaths: string[];
  chartType: string;
  category: 'trending' | 'comparison' | 'overview' | 'status';
}

interface SuggestionCardProps {
  suggestion: ChartSuggestion;
  onClick: (query: string) => void;
}

const categoryColors: Record<string, string> = {
  trending: 'bg-blue-900/50 text-blue-300',
  comparison: 'bg-purple-900/50 text-purple-300',
  overview: 'bg-emerald-900/50 text-emerald-300',
  status: 'bg-amber-900/50 text-amber-300',
};

const chartTypeIcons: Record<string, string> = {
  line: 'M3 17l4-4 4 4 4-8 4 4',
  bar: 'M9 19V6h2v13H9zm4 0V3h2v16h-2zm-8 0v-8h2v8H5z',
  gauge: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z',
  sparkline_grid: 'M4 5h4v4H4V5zm6 0h4v4h-4V5zm6 0h4v4h-4V5zM4 11h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4z',
};

export type { ChartSuggestion };

export default function SuggestionCard({ suggestion, onClick }: SuggestionCardProps) {
  const iconPath = chartTypeIcons[suggestion.chartType] || chartTypeIcons.line;

  return (
    <button
      onClick={() => onClick(suggestion.query)}
      className="w-full text-left p-3 rounded-lg bg-gray-700/30 hover:bg-gray-700/60 border border-gray-700/50 hover:border-gray-600 transition-all group"
    >
      <div className="flex items-start gap-2.5">
        {/* Chart type icon */}
        <svg
          className="w-4 h-4 mt-0.5 text-gray-500 group-hover:text-gray-300 flex-shrink-0 transition-colors"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d={iconPath} />
        </svg>

        <div className="flex-1 min-w-0">
          {/* Description */}
          <p className="text-sm text-gray-200 group-hover:text-white transition-colors">
            {suggestion.description}
          </p>

          {/* Topic paths - show last 2-3 segments for context */}
          <p className="text-xs font-mono text-cyan-400/70 truncate mt-1">
            {suggestion.topicPaths.length <= 2
              ? suggestion.topicPaths.map(p => {
                  const parts = p.split('/');
                  return parts.length > 2 ? parts.slice(-3).join('/') : p;
                }).join(', ')
              : (() => {
                  const parts = suggestion.topicPaths[0].split('/');
                  const short = parts.length > 2 ? parts.slice(-3).join('/') : suggestion.topicPaths[0];
                  return `${short} +${suggestion.topicPaths.length - 1} more`;
                })()}
          </p>

          {/* Tags */}
          <div className="flex items-center gap-2 mt-1.5">
            <span className={`text-xs px-1.5 py-0.5 rounded ${categoryColors[suggestion.category]}`}>
              {suggestion.category}
            </span>
            <span className="text-xs text-gray-500">
              {suggestion.reason}
            </span>
          </div>
        </div>
      </div>
    </button>
  );
}
