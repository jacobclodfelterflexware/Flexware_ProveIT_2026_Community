'use client';

import ForceGraph3D from 'react-force-graph-3d';

// Wrapper component that receives the ref via a custom prop
// This is the official workaround for Next.js dynamic import ref forwarding issues
// See: https://github.com/vasturiano/react-force-graph/issues/357
interface ForceGraphWrapperProps {
  fgRef: React.MutableRefObject<any>;
  [key: string]: any;
}

export default function ForceGraphWrapper({ fgRef, ...props }: ForceGraphWrapperProps) {
  return <ForceGraph3D ref={fgRef} {...props} />;
}
