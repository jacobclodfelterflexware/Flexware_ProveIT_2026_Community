'use client';

import { useState } from 'react';
import type { SMProfile } from '@/types/machines';

interface SMProfileSectionProps {
  smprofile: SMProfile;
}

const FIELD_LABELS: Record<string, string> = {
  manufacturer: 'Manufacturer',
  serialNumber: 'Serial Number',
  productInstanceUri: 'Product Instance URI',
  manufacturerUri: 'Manufacturer URI',
  model: 'Model',
  productCode: 'Product Code',
  hardwareRevision: 'Hardware Revision',
  softwareRevision: 'Software Revision',
  deviceClass: 'Device Class',
  yearOfConstruction: 'Year of Construction',
  monthOfConstruction: 'Month of Construction',
  initialOperationDate: 'Initial Operation Date',
  assetId: 'Asset ID',
  componentName: 'Component Name',
  location: 'Location',
};

export default function SMProfileSection({ smprofile }: SMProfileSectionProps) {
  const [expanded, setExpanded] = useState(false);

  const entries = Object.entries(smprofile).filter(
    ([key]) => key !== '$namespace'
  );

  return (
    <div className="mt-6 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      {/* Collapsible Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-700/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <div className="text-left">
            <h2 className="text-lg font-semibold text-gray-100">CESMII SM Profile</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              {smprofile.manufacturer} <span className="text-gray-600">•</span> {smprofile.model || smprofile.deviceClass || 'Machine Identification'}
            </p>
          </div>
        </div>
        <span className="text-xs text-gray-500 font-mono">{smprofile.$namespace?.split('/').pop()}</span>
      </button>

      {/* Collapsible Content */}
      {expanded && (
        <div className="p-4 border-t border-gray-700">
          <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Field
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Value
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {entries.map(([key, value]) => (
                  <tr key={key}>
                    <td className="px-4 py-2 text-gray-400">
                      {FIELD_LABELS[key] || key}
                    </td>
                    <td className="px-4 py-2 font-mono text-gray-200">
                      {String(value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
