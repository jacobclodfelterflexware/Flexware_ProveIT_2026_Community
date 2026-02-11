'use client';

import { NODE_COLORS } from '@/lib/graph-transformer';

const LEGEND_ITEMS = [
  { label: 'Selected Topic', color: NODE_COLORS.topic_uncurated },
  { label: 'Parent Path', color: NODE_COLORS.parent },
  { label: 'Message', color: NODE_COLORS.message },
];

export default function GraphLegend() {
  return (
    <div className="absolute bottom-2 right-2 bg-gray-800/90 backdrop-blur-sm rounded px-3 py-2 text-xs border border-gray-700">
      <div className="space-y-1.5">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.label} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-gray-300">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
