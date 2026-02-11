'use client';

import { useEffect } from 'react';
import dynamic from 'next/dynamic';

const GraphVisualization = dynamic(
  () => import('@/components/machines/GraphVisualization'),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-black flex items-center justify-center">
        <div className="text-cyan-400 text-lg">Loading...</div>
      </div>
    ),
  }
);

export default function ShowcasePage() {
  // Hide navbar on mount
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    const navbar = document.querySelector('nav');
    if (navbar) {
      navbar.style.display = 'none';
    }

    return () => {
      document.body.style.overflow = '';
      if (navbar) {
        navbar.style.display = '';
      }
    };
  }, []);

  return (
    <div className="fixed inset-0 bg-black">
      <GraphVisualization
        similarResults={[]}
        enableAutoRotate={true}
        enableSlowZoom={true}
        enableLightning={true}
      />
    </div>
  );
}
