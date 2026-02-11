'use client';

import { useEffect, useState } from 'react';
import SuggestionCard, { type ChartSuggestion } from './SuggestionCard';
import type { SkillInfo } from '@/lib/chart-engine-api';

interface TreeNode {
  name: string;
  fullPath: string;
  children: TreeNode[];
  isLeaf: boolean;
  messageCount?: number;
  totalMessageCount?: number;
  hasNumericData?: boolean;
  hasMLReadyDescendant?: boolean;
}

interface ChartSuggestionsProps {
  skills: SkillInfo[];
  onSelectSuggestion: (query: string) => void;
}

interface ScoredCandidate {
  node: TreeNode;
  score: number;
}

// Flatten tree to leaf nodes with numeric data
function collectCandidates(nodes: TreeNode[]): TreeNode[] {
  const results: TreeNode[] = [];
  function walk(node: TreeNode) {
    if (node.isLeaf && node.hasNumericData && (node.messageCount ?? 0) > 0) {
      results.push(node);
    }
    for (const child of node.children) {
      walk(child);
    }
  }
  for (const node of nodes) walk(node);
  return results;
}

// Score a leaf topic for "interestingness"
function scoreCandidate(node: TreeNode): number {
  let score = 0;
  const msgCount = node.messageCount ?? 0;

  // Activity (0-40): log scale, more messages = more interesting
  score += Math.min(40, Math.log10(msgCount + 1) * 15);

  // Numeric bonus (0-20): guaranteed since we pre-filter
  score += 20;

  // ML-ready bonus (0-15): 20+ messages
  if (msgCount >= 20) score += 15;

  // Depth bonus (0-15): deeper = more specific
  const depth = node.fullPath.split('/').length;
  score += Math.min(15, depth * 3);

  return score;
}

function matchChartType(skills: SkillInfo[]): string {
  const candidates = ['time_series', 'line'];
  for (const candidate of candidates) {
    const found = skills.find(
      s => s.id.includes(candidate) || s.chart_type === candidate
    );
    if (found) return found.chart_type;
  }
  return 'line';
}

function generateSuggestions(tree: TreeNode[], skills: SkillInfo[]): ChartSuggestion[] {
  const suggestions: ChartSuggestion[] = [];
  let idCounter = 0;

  // Trending: top scored individual topics (time series only)
  const candidates = collectCandidates(tree);
  const scored: ScoredCandidate[] = candidates
    .map(node => ({ node, score: scoreCandidate(node) }))
    .sort((a, b) => b.score - a.score);

  for (const { node } of scored.slice(0, 6)) {
    const name = node.name;
    // Get parent name for context in description
    const pathParts = node.fullPath.split('/');
    const parentName = pathParts.length > 1 ? pathParts[pathParts.length - 2] : '';
    const displayName = parentName ? `${parentName}/${name}` : name;
    suggestions.push({
      id: `suggestion-${idCounter++}`,
      query: `Show ${name} trends over the last hour for ${node.fullPath}`,
      description: `${displayName} time series`,
      reason: `${node.messageCount} messages`,
      topicPaths: [node.fullPath],
      chartType: matchChartType(skills),
      category: 'trending',
    });
  }

  return suggestions;
}

export type { ChartSuggestion as ChartSuggestionType };

export default function ChartSuggestions({ skills, onSelectSuggestion }: ChartSuggestionsProps) {
  const [suggestions, setSuggestions] = useState<ChartSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSuggestions() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch('/api/graph/tree');
        if (!response.ok) throw new Error('Failed to fetch topic data');
        const data = await response.json();
        const generated = generateSuggestions(data.tree, skills);
        setSuggestions(generated);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    loadSuggestions();
  }, [skills]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="ml-2 text-sm text-gray-400">Analyzing topics...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-3 py-4 text-center text-sm text-red-400">{error}</div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="px-3 py-4 text-center text-sm text-gray-500">
        No suggestions available. Try publishing some MQTT data first.
      </div>
    );
  }

  return (
    <div className="p-2 space-y-2">
      <p className="px-1 text-xs text-gray-500 mb-2">
        Click a suggestion to generate the chart
      </p>
      {suggestions.map((suggestion) => (
        <SuggestionCard
          key={suggestion.id}
          suggestion={suggestion}
          onClick={onSelectSuggestion}
        />
      ))}
    </div>
  );
}
