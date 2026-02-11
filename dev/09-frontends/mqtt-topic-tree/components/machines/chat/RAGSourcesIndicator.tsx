'use client';

interface RAGSourcesIndicatorProps {
  visible: boolean;
}

/**
 * Loading indicator shown while injecting RAG sources
 */
export default function RAGSourcesIndicator({ visible }: RAGSourcesIndicatorProps) {
  if (!visible) return null;

  return (
    <div className="flex items-center gap-2 px-4 py-2 mx-3 mb-2 bg-purple-900/30 border border-purple-800/50 rounded-lg">
      {/* Pulsing dots animation */}
      <div className="flex gap-1">
        <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
        <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
      </div>

      {/* Text */}
      <span className="text-sm text-purple-300 font-medium">
        Injecting RAG sources...
      </span>

      {/* Search icon */}
      <svg
        className="w-4 h-4 text-purple-400 animate-pulse"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
    </div>
  );
}
