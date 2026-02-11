'use client';

import { useState } from 'react';

interface JsonTreeViewerProps {
  data: any;
  level?: number;
}

export default function JsonTreeViewer({ data, level = 0 }: JsonTreeViewerProps) {
  const [isExpanded, setIsExpanded] = useState(level < 2); // Auto-expand first 2 levels

  if (data === null) {
    return <span className="text-gray-400">null</span>;
  }

  if (data === undefined) {
    return <span className="text-gray-400">undefined</span>;
  }

  if (typeof data === 'boolean') {
    return <span className="text-purple-400">{data.toString()}</span>;
  }

  if (typeof data === 'number') {
    return <span className="text-blue-400">{data}</span>;
  }

  if (typeof data === 'string') {
    return <span className="text-green-400">"{data}"</span>;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <span className="text-gray-400">[]</span>;
    }

    return (
      <div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-yellow-400 hover:text-yellow-300 focus:outline-none"
        >
          {isExpanded ? '▼' : '▶'} Array[{data.length}]
        </button>
        {isExpanded && (
          <div className="ml-4 border-l border-gray-700 pl-2">
            {data.map((item, index) => (
              <div key={index} className="my-1">
                <span className="text-gray-500">{index}: </span>
                <JsonTreeViewer data={item} level={level + 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (typeof data === 'object') {
    const keys = Object.keys(data);
    if (keys.length === 0) {
      return <span className="text-gray-400">{'{}'}</span>;
    }

    return (
      <div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-yellow-400 hover:text-yellow-300 focus:outline-none"
        >
          {isExpanded ? '▼' : '▶'} Object
        </button>
        {isExpanded && (
          <div className="ml-4 border-l border-gray-700 pl-2">
            {keys.map((key) => (
              <div key={key} className="my-1">
                <span className="text-cyan-400">{key}</span>
                <span className="text-gray-500">: </span>
                <JsonTreeViewer data={data[key]} level={level + 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return <span className="text-gray-400">{String(data)}</span>;
}
