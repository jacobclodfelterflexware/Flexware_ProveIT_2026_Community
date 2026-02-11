'use client';

import { useRef, useCallback, useMemo, useEffect, useState, Component, ReactNode } from 'react';
import dynamic from 'next/dynamic';
import type { SimilarResult } from '@/types/machines';
import type { GraphMetrics } from '@/types/graph';

// Error boundary to catch WebGL/Three.js errors
class GraphErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: string }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: '' };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
          <div className="text-center text-gray-400 p-4">
            <svg className="w-12 h-12 mx-auto mb-2 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-sm">3D visualization error</p>
            <p className="text-xs text-gray-500 mt-1">WebGL may not be available</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// Dynamic import of wrapper component to avoid SSR issues with WebGL
// The wrapper passes ref via custom fgRef prop (official workaround for Next.js dynamic import ref issues)
// See: https://github.com/vasturiano/react-force-graph/issues/357
const ForceGraph3DWrapper = dynamic(
  () => import('./ForceGraphWrapper'),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-400 text-sm">Loading 3D renderer...</p>
        </div>
      </div>
    )
  }
);

const LOADING_MESSAGES = [
  'Computing graph layout...',
  'Mapping topic relationships...',
  'Positioning nodes in 3D space...',
  'Calculating force-directed layout...',
  'Analyzing connection patterns...',
  'Building knowledge topology...',
  'Rendering neural pathways...',
  'Optimizing node positions...',
  'Weaving the knowledge web...',
  'Running similarity visualization...',
];

interface GraphNode {
  id: string;           // Topic path
  name: string;         // Leaf segment (e.g., "speed", "temperature")
  depth: number;        // Hierarchy level
  similarity?: number;  // 0-1 similarity score (if matched)
  val?: number;         // Node size
}

interface GraphLink {
  source: string;
  target: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

interface GraphVisualizationProps {
  similarResults: SimilarResult[];
  suggestedTopic?: string;
  isSearching?: boolean;
  enableAutoRotate?: boolean;
  enableSlowZoom?: boolean;
  enableLightning?: boolean;
  enableMqttHighlight?: boolean;
  // Manual controls for debugging
  manualControls?: {
    camera?: { x: number; y: number; z: number };
    target?: { x: number; y: number; z: number };
    disableAutoRotate?: boolean;
  };
  onMetricsUpdate?: (metrics: GraphMetrics) => void;
  onLayoutReady?: () => void;  // Callback when graph layout is complete and visible
  // Expose internal graph ref for frame-by-frame recording
  onGraphRefReady?: (ref: any) => void;
}

export default function GraphVisualization({
  similarResults,
  suggestedTopic,
  isSearching,
  enableAutoRotate = false,
  enableSlowZoom = false,
  enableLightning = false,
  enableMqttHighlight = false,
  manualControls,
  onMetricsUpdate,
  onLayoutReady,
  onGraphRefReady
}: GraphVisualizationProps) {
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [layoutComplete, setLayoutComplete] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 1280, height: 600 });
  const [readyToShow, setReadyToShow] = useState(false);
  const [lightningLinks, setLightningLinks] = useState<Set<string>>(new Set());
  const [lightningNodes, setLightningNodes] = useState<Set<string>>(new Set());
  const [flashingNodes, setFlashingNodes] = useState<Set<string>>(new Set());
  const [loadingMsgIndex, setLoadingMsgIndex] = useState(0);

  // Cycle loading messages while graph layout is computing
  useEffect(() => {
    if (readyToShow) return;
    const interval = setInterval(() => {
      setLoadingMsgIndex(prev => (prev + 1) % LOADING_MESSAGES.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [readyToShow]);

  // Notify parent when layout is ready and visible
  useEffect(() => {
    if (readyToShow && onLayoutReady) {
      onLayoutReady();
    }
  }, [readyToShow, onLayoutReady]);

  // Expose internal graph ref for external control (e.g., frame-by-frame recording)
  useEffect(() => {
    if (layoutComplete && fgRef.current && onGraphRefReady) {
      onGraphRefReady(fgRef.current);
    }
  }, [layoutComplete, onGraphRefReady]);

  // Set readyToShow when layout completes (for non-auto-rotate mode)
  useEffect(() => {
    if (layoutComplete && !enableAutoRotate) {
      setReadyToShow(true);
    }
  }, [layoutComplete, enableAutoRotate]);

  // Track tick count for debugging
  const tickCountRef = useRef(0);

  // Debug: track engine ticks to see if simulation is running
  const handleEngineTick = useCallback(() => {
    tickCountRef.current++;
    // Log every 50 ticks
    if (tickCountRef.current % 50 === 0) {
      console.log('[Graph] Engine tick:', tickCountRef.current);
    }
  }, []);

  // Callback when force layout completes
  // react-force-graph mutates node objects in place with x,y,z coordinates
  // We can compute the center directly from graphData.nodes after layout
  const handleEngineStop = useCallback(() => {
    console.log('[Graph] === ENGINE STOP === (after', tickCountRef.current, 'ticks)');
    console.log('[Graph] Computing center from graphData.nodes (mutated in place by force-graph)');

    // react-force-graph mutates the original node objects with x, y, z positions
    // So we can read positions directly from graphData.nodes
    if (graphData.nodes.length > 0) {
      let sumX = 0, sumY = 0, sumZ = 0, count = 0;
      graphData.nodes.forEach((node: any) => {
        if (typeof node.x === 'number' && typeof node.y === 'number' && typeof node.z === 'number') {
          sumX += node.x;
          sumY += node.y;
          sumZ += node.z;
          count++;
        }
      });

      if (count > 0) {
        graphCenterRef.current = {
          x: sumX / count,
          y: sumY / count,
          z: sumZ / count
        };
        console.log('[Graph] Center computed from mutated nodes:', graphCenterRef.current);
        console.log('[Graph] Nodes with positions:', count, '/', graphData.nodes.length);

        // Log first node for debugging
        const firstNode = graphData.nodes[0] as any;
        console.log('[Graph] First node position:', { x: firstNode.x, y: firstNode.y, z: firstNode.z });
      } else {
        console.log('[Graph] WARNING: No nodes have positions yet');
      }
    }

    setLayoutComplete(true);
  }, [graphData.nodes]); // Depend on graphData.nodes

  // Reset layoutComplete when graph data changes (new data = new layout)
  useEffect(() => {
    console.log('[Graph] graphData changed, resetting layoutComplete');
    setLayoutComplete(false);
  }, [graphData]);

  // Measure container dimensions and update when it resizes
  useEffect(() => {
    if (!containerRef.current) return;

    // Force initial measurement after browser layout is complete
    // This fixes the issue where w-full h-full containers don't have
    // computed dimensions when ResizeObserver first fires
    requestAnimationFrame(() => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        console.log('[Graph] Initial container measurement:', { width: rect.width, height: rect.height });
        if (rect.width > 0 && rect.height > 0) {
          setDimensions({ width: rect.width, height: rect.height });
        }
      }
    });

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        console.log('[Graph] Container resized:', { width, height });
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [loading]);  // Re-run when loading changes so we measure after container mounts

  // Re-center graph when dimensions change after layout completes
  // This handles cases where modal animations or container resizing happens after initial layout
  useEffect(() => {
    if (!layoutComplete || !fgRef.current?.zoomToFit || enableAutoRotate) {
      return;
    }

    console.log('[Graph] Dimensions changed after layout complete, re-centering');

    // Small delay to ensure dimensions are fully applied
    const timeout = setTimeout(() => {
      if (fgRef.current?.zoomToFit) {
        console.log('[Graph] Re-centering with zoomToFit after dimension change');
        fgRef.current.zoomToFit(400, 100);
      }
    }, 100);

    return () => clearTimeout(timeout);
  }, [dimensions.width, dimensions.height, layoutComplete, enableAutoRotate]);

  // Emit live metrics to parent component for manual controls debugging
  useEffect(() => {
    if (!onMetricsUpdate || !fgRef.current) return;

    const interval = setInterval(() => {
      if (!fgRef.current) return;

      const camera = fgRef.current.camera();
      const controls = fgRef.current.controls();
      const renderer = fgRef.current.renderer();

      const metrics: GraphMetrics = {
        windowDimensions: {
          width: window.innerWidth,
          height: window.innerHeight,
          aspectRatio: (window.innerWidth / window.innerHeight).toFixed(2)
        },
        containerDimensions: {
          width: dimensions.width,
          height: dimensions.height,
          aspectRatio: dimensions.height > 0
            ? (dimensions.width / dimensions.height).toFixed(2)
            : 'N/A'
        },
        canvasDimensions: {
          width: renderer.domElement.clientWidth,
          height: renderer.domElement.clientHeight,
          aspectRatio: (renderer.domElement.clientWidth / renderer.domElement.clientHeight).toFixed(2)
        },
        cameraPosition: {
          x: parseFloat(camera.position.x.toFixed(2)),
          y: parseFloat(camera.position.y.toFixed(2)),
          z: parseFloat(camera.position.z.toFixed(2))
        },
        controlsTarget: {
          x: parseFloat(controls.target.x.toFixed(2)),
          y: parseFloat(controls.target.y.toFixed(2)),
          z: parseFloat(controls.target.z.toFixed(2))
        },
        distance: parseFloat(Math.sqrt(
          Math.pow(camera.position.x - controls.target.x, 2) +
          Math.pow(camera.position.y - controls.target.y, 2) +
          Math.pow(camera.position.z - controls.target.z, 2)
        ).toFixed(2)),
        graphCenter: graphCenterRef.current,
        nodeCount: graphData.nodes.length
      };

      // Check for size mismatch
      if (dimensions.width > 0 && renderer.domElement.clientWidth !== dimensions.width) {
        metrics.sizeMismatch = {
          canvasWidth: renderer.domElement.clientWidth,
          containerWidth: dimensions.width,
          horizontalOffset: Math.round((renderer.domElement.clientWidth - dimensions.width) / 2)
        };
      }

      onMetricsUpdate(metrics);
    }, 100); // Update every 100ms

    return () => clearInterval(interval);
  }, [onMetricsUpdate, dimensions, graphData.nodes.length]);

  // Apply manual camera controls when provided
  useEffect(() => {
    if (!manualControls?.camera || !manualControls?.target || !fgRef.current?.cameraPosition) {
      return;
    }

    console.log('[Graph] Applying manual controls:', manualControls);

    // Position camera at manual coordinates, looking at manual target
    fgRef.current.cameraPosition(
      manualControls.camera,
      manualControls.target,
      0 // Instant transition
    );
  }, [manualControls]);

  // Fetch graph data on mount
  useEffect(() => {
    const fetchGraphData = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/graph/all');
        if (!response.ok) {
          throw new Error('Failed to fetch graph data');
        }
        const data = await response.json();
        setGraphData(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching graph data:', err);
        setError('Failed to load graph data');
      } finally {
        setLoading(false);
      }
    };

    fetchGraphData();
  }, []);

  // Build similarity map for O(1) lookup
  const similarityMap = useMemo(() => {
    const map = new Map<string, number>();
    similarResults.forEach(r => map.set(r.topic_path, r.similarity));

    // Debug logging to diagnose path matching issues
    if (similarResults.length > 0) {
      const graphNodeIds = new Set(graphData.nodes.map(n => n.id));
      const matchedCount = similarResults.filter(r => graphNodeIds.has(r.topic_path)).length;
      console.log('[Graph] Similar results:', similarResults.length, '| Matched in graph:', matchedCount);
      if (matchedCount < similarResults.length) {
        console.log('[Graph] Unmatched paths:', similarResults.filter(r => !graphNodeIds.has(r.topic_path)).map(r => r.topic_path));
      }
    }

    return map;
  }, [similarResults, graphData.nodes]);

  // Build set of links and nodes on path from similar nodes to root
  const { highlightedLinks, highlightedNodes } = useMemo(() => {
    const links = new Set<string>();
    const nodes = new Set<string>();
    if (similarResults.length === 0) return { highlightedLinks: links, highlightedNodes: nodes };

    // Build parent lookup: child -> parent
    const parentMap = new Map<string, string>();
    graphData.links.forEach((link: any) => {
      const source = typeof link.source === 'object' ? link.source.id : link.source;
      const target = typeof link.target === 'object' ? link.target.id : link.target;
      parentMap.set(source, target);
    });

    // For each similar node, trace path to root
    similarResults.forEach(result => {
      let current = result.topic_path;
      nodes.add(current); // Add the similar node itself
      while (current) {
        const parent = parentMap.get(current);
        if (parent) {
          links.add(`${current}->${parent}`);
          nodes.add(parent); // Add all nodes on path to root
          current = parent;
        } else {
          break;
        }
      }
    });

    return { highlightedLinks: links, highlightedNodes: nodes };
  }, [similarResults, graphData.links]);

  // Node color based on similarity score and path highlighting
  const nodeColor = useCallback((node: any) => {
    const nodeId = node.id as string;
    // Flash effect - bright white burst when first traversed
    if (flashingNodes.has(nodeId)) return '#ffffff';
    // Lightning effect - bright green glow
    if (lightningNodes.has(nodeId)) return '#00ff00';
    if (nodeId === suggestedTopic) return '#22c55e'; // Green for selected/suggested
    const sim = similarityMap.get(nodeId);
    if (sim !== undefined) {
      // Gradient from blue (low similarity) to bright cyan/white (high similarity)
      // Using HSL for better visual gradient
      const lightness = 40 + (sim * 30); // 40% to 70% - brighter for higher similarity
      const saturation = 70 + (sim * 30); // 70% to 100%
      return `hsl(${200 - sim * 40}, ${saturation}%, ${lightness}%)`;
    }
    // Nodes on path to root get highlighted color
    if (highlightedNodes.has(nodeId)) {
      return 'hsl(160, 80%, 45%)'; // Cyan/green for path nodes
    }
    return '#374151'; // Gray for non-matching
  }, [similarityMap, suggestedTopic, highlightedNodes, lightningNodes, flashingNodes]);

  // Node size based on similarity and path highlighting (1.5x bigger)
  const nodeVal = useCallback((node: any) => {
    const nodeId = node.id as string;
    const sim = similarityMap.get(nodeId);
    if (sim !== undefined) {
      return 12 + sim * 36; // Bigger nodes for higher similarity (12-48 range, 1.5x)
    }
    // Nodes on path to root are also larger
    if (highlightedNodes.has(nodeId)) {
      return 9;
    }
    return 3; // Small for non-matching (1.5x)
  }, [similarityMap, highlightedNodes]);

  // Node label showing name and similarity score
  const nodeLabel = useCallback((node: any) => {
    const nodeId = node.id as string;
    const nodeName = node.name as string;
    const sim = similarityMap.get(nodeId);
    if (sim !== undefined) {
      return `${nodeName}\nSimilarity: ${(sim * 100).toFixed(1)}%`;
    }
    return nodeName;
  }, [similarityMap]);

  // Store the computed graph center after layout completes
  const graphCenterRef = useRef({ x: 0, y: 0, z: 0 });

  // Fallback: Calculate center from graphData.nodes if not already computed
  // This runs after layoutComplete is set and relies on nodes being mutated in place
  useEffect(() => {
    // Skip if center was already computed (non-zero values)
    if (graphCenterRef.current.x !== 0 || graphCenterRef.current.y !== 0 || graphCenterRef.current.z !== 0) {
      console.log('[Graph] Center already computed, skipping fallback effect');
      return;
    }
    if (!layoutComplete) return;

    console.log('[Graph] Center compute fallback effect - checking graphData.nodes for positions');

    // Calculate center from graphData.nodes (mutated in place by force-graph)
    if (graphData.nodes.length > 0) {
      let sumX = 0, sumY = 0, sumZ = 0;
      let count = 0;

      graphData.nodes.forEach((node: any) => {
        if (typeof node.x === 'number' && typeof node.y === 'number' && typeof node.z === 'number') {
          sumX += node.x;
          sumY += node.y;
          sumZ += node.z;
          count++;
        }
      });

      if (count > 0) {
        graphCenterRef.current = {
          x: sumX / count,
          y: sumY / count,
          z: sumZ / count
        };
        console.log('[Graph] === COMPUTED CENTER (fallback effect) ===', graphCenterRef.current);
      }
    }
  }, [layoutComplete, graphData.nodes]);

  // Center graph after layout completes (only when NOT auto-rotating)
  // Uses polling since ref forwarding doesn't work with Next.js dynamic import
  useEffect(() => {
    if (!layoutComplete || enableAutoRotate) return;

    let attempts = 0;
    const maxAttempts = 50; // 5 seconds max

    const tryZoomToFit = () => {
      attempts++;
      if (fgRef.current?.zoomToFit) {
        console.log('[Graph] Centering with zoomToFit (attempt', attempts, ')');
        fgRef.current.zoomToFit(400, 100); // 400ms transition, 100px padding
        return true;
      }
      return false;
    };

    // Try immediately
    if (tryZoomToFit()) return;

    // Poll every 100ms
    const interval = setInterval(() => {
      if (tryZoomToFit() || attempts >= maxAttempts) {
        clearInterval(interval);
        if (attempts >= maxAttempts) {
          console.log('[Graph] zoomToFit: gave up after', maxAttempts, 'attempts');
        }
      }
    }, 100);

    return () => clearInterval(interval);
  }, [layoutComplete, enableAutoRotate]);

  // Auto-rotation effect: zoomed out, spinning around the graph center
  useEffect(() => {
    // Skip if rotation is disabled or graph not ready
    if (!enableAutoRotate || manualControls?.disableAutoRotate || !layoutComplete || graphData.nodes.length === 0) {
      return;
    }

    let rotateIntervalId: NodeJS.Timeout | null = null;
    let setupComplete = false;

    const startRotation = () => {
      if (setupComplete || !fgRef.current?.cameraPosition || !fgRef.current?.zoomToFit) {
        return;
      }
      setupComplete = true;

      // Zoom to fit the graph instantly (0ms) with some padding
      fgRef.current.zoomToFit(0, 50);
      setReadyToShow(true);

      // Get camera position after zoomToFit
      const camera = fgRef.current.camera();
      const controls = fgRef.current.controls();

      const target = { x: controls.target.x, y: controls.target.y, z: controls.target.z };
      const camPos = { x: camera.position.x, y: camera.position.y, z: camera.position.z };

      // Calculate distance from camera to target
      const dx = camPos.x - target.x;
      const dz = camPos.z - target.z;
      let currentDistance = Math.sqrt(dx * dx + camPos.y * camPos.y + dz * dz);
      const startDistance = currentDistance;
      const minDistance = currentDistance * 0.05; // Super close zoom to center

      // Start rotation immediately
      let angle = Math.atan2(dx, dz);

      rotateIntervalId = setInterval(() => {
        if (!fgRef.current) return;

        angle += Math.PI / 3000; // Very slow rotation speed (~100 seconds per revolution)

        // Slow zoom if enabled
        if (enableSlowZoom && currentDistance > minDistance) {
          currentDistance *= 0.9997; // 1.5x faster zoom
        }

        fgRef.current.cameraPosition({
          x: target.x + currentDistance * Math.sin(angle),
          y: camPos.y * (currentDistance / startDistance), // Scale height proportionally
          z: target.z + currentDistance * Math.cos(angle)
        }, target);
      }, 16); // ~60fps
    };

    // Try to start immediately, then poll if ref not ready
    startRotation();
    const checkInterval = setInterval(() => {
      if (!setupComplete) startRotation();
      else clearInterval(checkInterval);
    }, 100);

    return () => {
      clearInterval(checkInterval);
      if (rotateIntervalId) clearInterval(rotateIntervalId);
    };
  }, [enableAutoRotate, enableSlowZoom, manualControls?.disableAutoRotate, layoutComplete, graphData.nodes.length]);

  // Lightning effect - partial fork from rotating roots with ramping intensity
  useEffect(() => {
    if (!enableLightning || graphData.nodes.length === 0 || graphData.links.length === 0) return;

    // Build children map (parent -> children[]) and find ALL roots
    const childrenMap = new Map<string, string[]>();
    const hasParent = new Set<string>();

    graphData.links.forEach((link: any) => {
      const source = typeof link.source === 'object' ? link.source.id : link.source;
      const target = typeof link.target === 'object' ? link.target.id : link.target;
      // source is child, target is parent
      hasParent.add(source);
      if (!childrenMap.has(target)) {
        childrenMap.set(target, []);
      }
      childrenMap.get(target)!.push(source);
    });

    // Find ALL root nodes (have children but no parent)
    const rootNodes = graphData.nodes.filter(n => !hasParent.has(n.id) && childrenMap.has(n.id));

    if (rootNodes.length === 0) return;

    let timeoutIds: NodeJS.Timeout[] = [];
    const startTime = Date.now();
    const totalDuration = 60000; // 60 seconds for full ramp up
    let currentRootIndex = 0; // Cycle through roots

    const fireWave = () => {
      const activeLinks = new Set<string>();
      const activeNodes = new Set<string>();
      let currentFlashing = new Set<string>();

      // Pick current root and cycle to next for next wave
      const rootNode = rootNodes[currentRootIndex].id;
      currentRootIndex = (currentRootIndex + 1) % rootNodes.length;

      // Build waves with PARTIAL FORKING (2-4 random children per node for fuller coverage)
      const waves: string[][] = [];
      let currentWave = [rootNode];
      const visited = new Set<string>();

      while (currentWave.length > 0) {
        waves.push([...currentWave]);
        currentWave.forEach(n => visited.add(n));

        const nextWave: string[] = [];
        currentWave.forEach(nodeId => {
          const children = childrenMap.get(nodeId) || [];
          if (children.length > 0) {
            // Randomly pick 3-5 children (near full coverage)
            const shuffled = [...children].sort(() => Math.random() - 0.5);
            const rand = Math.random();
            // 5% chance of 1, 10% chance of 2, 25% chance of 3, 60% chance of 4+ (much fuller)
            const numToTake = Math.min(children.length, rand < 0.05 ? 1 : rand < 0.15 ? 2 : rand < 0.4 ? 3 : 5);
            shuffled.slice(0, numToTake).forEach(child => {
              if (!visited.has(child)) {
                nextWave.push(child);
              }
            });
          }
        });
        currentWave = nextWave;
      }

      // Calculate intensity based on elapsed time (0 to 1)
      const elapsed = Date.now() - startTime;
      const intensity = Math.min(1, elapsed / totalDuration);

      // Ramp parameters based on intensity
      const baseStepDelay = 800 - (intensity * 500); // 800ms -> 300ms
      const flashDuration = 150 + (intensity * 100); // 150ms -> 250ms

      // Animate each wave
      let cumulativeDelay = 0;
      waves.forEach((wave) => {
        const tid = setTimeout(() => {
          // Add all nodes in this wave
          wave.forEach(nodeId => {
            activeNodes.add(nodeId);
            currentFlashing.add(nodeId);

            // Find links from this node to its parent
            graphData.links.forEach((link: any) => {
              const source = typeof link.source === 'object' ? link.source.id : link.source;
              const target = typeof link.target === 'object' ? link.target.id : link.target;
              if (source === nodeId) {
                activeLinks.add(`${source}->${target}`);
              }
            });
          });

          setLightningNodes(new Set(activeNodes));
          setLightningLinks(new Set(activeLinks));
          setFlashingNodes(new Set(currentFlashing));

          // Remove flash after short duration
          const flashTid = setTimeout(() => {
            wave.forEach(nodeId => currentFlashing.delete(nodeId));
            setFlashingNodes(new Set(currentFlashing));
          }, flashDuration);
          timeoutIds.push(flashTid);

        }, cumulativeDelay);

        timeoutIds.push(tid);
        cumulativeDelay += baseStepDelay;
      });

      // Hold at full illumination, then instant clear (5x longer hold)
      const holdTime = 10000 + (intensity * 15000); // 10s -> 25s hold

      // Instant clear after hold time
      const clearTid = setTimeout(() => {
        setLightningLinks(new Set());
        setLightningNodes(new Set());
        setFlashingNodes(new Set());
      }, cumulativeDelay + holdTime);
      timeoutIds.push(clearTid);

      // Schedule next wave
      const nextDelay = 8000 - (intensity * 5000); // 8s -> 3s between waves
      const nextTid = setTimeout(fireWave, cumulativeDelay + holdTime + nextDelay);
      timeoutIds.push(nextTid);
    };

    // Start first wave after short delay
    const startTid = setTimeout(fireWave, 1000);
    timeoutIds.push(startTid);

    return () => {
      timeoutIds.forEach(id => clearTimeout(id));
    };
  }, [enableLightning, graphData.nodes, graphData.links]);

  // MQTT highlight effect via SSE proxy - lights up nodes when payloads arrive
  useEffect(() => {
    if (!enableMqttHighlight || graphData.nodes.length === 0) return;

    // Build parent lookup: child -> parent
    const parentMap = new Map<string, string>();
    graphData.links.forEach((link: any) => {
      const source = typeof link.source === 'object' ? link.source.id : link.source;
      const target = typeof link.target === 'object' ? link.target.id : link.target;
      parentMap.set(source, target);
    });

    const activeHighlights = new Map<string, NodeJS.Timeout>();

    // Connect via SSE proxy (server subscribes to MQTT internally)
    const eventSource = new EventSource('/api/mqtt/stream');

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type !== 'message') return;

      const topic = data.topic;
      const nodeExists = graphData.nodes.some(n => n.id === topic);
      if (!nodeExists) return;

      // Collect nodes to highlight: the topic + all parents to root
      const nodesToHighlight = new Set<string>();
      nodesToHighlight.add(topic);

      let current = topic;
      while (current) {
        const parent = parentMap.get(current);
        if (parent) {
          nodesToHighlight.add(parent);
          current = parent;
        } else {
          break;
        }
      }

      // Flash the leaf node briefly
      setFlashingNodes(prev => {
        const next = new Set(prev);
        next.add(topic);
        return next;
      });
      setTimeout(() => {
        setFlashingNodes(prev => {
          const next = new Set(prev);
          next.delete(topic);
          return next;
        });
      }, 200);

      // Add to lightning nodes (green glow)
      setLightningNodes(prev => {
        const next = new Set(prev);
        nodesToHighlight.forEach(n => next.add(n));
        return next;
      });

      // Clear highlight after 3 seconds
      nodesToHighlight.forEach(nodeId => {
        const existing = activeHighlights.get(nodeId);
        if (existing) clearTimeout(existing);

        const timeout = setTimeout(() => {
          setLightningNodes(prev => {
            const next = new Set(prev);
            next.delete(nodeId);
            return next;
          });
          activeHighlights.delete(nodeId);
        }, 3000);

        activeHighlights.set(nodeId, timeout);
      });
    };

    eventSource.onerror = (err) => {
      console.error('[MQTT SSE] Connection error:', err);
    };

    return () => {
      eventSource.close();
      activeHighlights.forEach(timeout => clearTimeout(timeout));
    };
  }, [enableMqttHighlight, graphData.nodes, graphData.links]);

  if (loading) {
    return (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-gray-400 text-sm">Loading knowledge graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-2 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="text-sm">{error}</p>
          <p className="text-xs text-gray-500 mt-1">Graph visualization unavailable</p>
        </div>
      </div>
    );
  }

  if (graphData.nodes.length === 0) {
    return (
      <div className="w-full h-full bg-gray-950 rounded-lg flex items-center justify-center">
        <div className="text-center text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-2 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <p className="text-sm">No topics in knowledge graph</p>
          <p className="text-xs text-gray-500 mt-1">Topics will appear as messages are ingested</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full bg-gray-950 rounded-lg overflow-hidden relative">
      {/* Loading overlay while force layout is computing (opacity:0 phase) */}
      {!readyToShow && (
        <div className="absolute inset-0 z-20 bg-gray-950 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-cyan-500 mx-auto mb-3"></div>
            <p className="text-gray-300 text-sm transition-opacity duration-500" key={loadingMsgIndex}>
              {LOADING_MESSAGES[loadingMsgIndex]}
            </p>
          </div>
        </div>
      )}
      {/* Status indicator */}
      {isSearching && (
        <div className="absolute top-4 left-4 z-10 bg-blue-600/90 backdrop-blur px-3 py-1.5 rounded-full text-sm flex items-center gap-2">
          <div className="animate-spin rounded-full h-3 w-3 border-t-2 border-b-2 border-white"></div>
          Searching...
        </div>
      )}

      {/* Similarity results count */}
      {!isSearching && similarResults.length > 0 && (
        <div className="absolute top-4 left-4 z-10 bg-green-600/90 backdrop-blur px-3 py-1.5 rounded-full text-sm">
          {similarResults.length} similar topics found
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-10 bg-gray-900/90 backdrop-blur p-3 rounded-lg text-xs">
        <p className="text-gray-400 mb-2 font-medium">Similarity</p>
        <div className="flex items-center gap-2 mb-1">
          <div className="w-3 h-3 rounded-full bg-[#374151]"></div>
          <span className="text-gray-500">No match</span>
        </div>
        <div className="flex items-center gap-2 mb-1">
          <div className="w-3 h-3 rounded-full" style={{ background: 'hsl(180, 80%, 50%)' }}></div>
          <span className="text-gray-400">Low similarity</span>
        </div>
        <div className="flex items-center gap-2 mb-1">
          <div className="w-3 h-3 rounded-full" style={{ background: 'hsl(160, 100%, 70%)' }}></div>
          <span className="text-gray-300">High similarity</span>
        </div>
        {suggestedTopic && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="text-green-400">Suggested</span>
          </div>
        )}
      </div>

      {/* Controls hint */}
      <div className="absolute bottom-4 right-4 z-10 text-xs text-gray-500">
        Drag to rotate | Scroll to zoom | Right-click drag to pan
      </div>

      <GraphErrorBoundary>
        {dimensions.width > 0 && dimensions.height > 0 ? (
          <ForceGraph3DWrapper
            fgRef={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={graphData}
          nodeColor={nodeColor}
          nodeVal={nodeVal}
          nodeLabel={nodeLabel}
          nodeOpacity={0.9}
          linkOpacity={isSearching ? 0.4 : 0.2}
          linkWidth={(link: any) => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            const linkKey = `${sourceId}->${targetId}`;
            // Lightning effect - thick bright lines (3x thicker)
            if (lightningLinks.has(linkKey)) return 18;
            // Highlight entire path to root for similar nodes - thick lines
            if (highlightedLinks.has(linkKey)) return 8;
            const sim = similarityMap.get(targetId);
            return sim ? 4 + sim * 6 : 1;
          }}
          linkColor={(link: any) => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            const linkKey = `${sourceId}->${targetId}`;
            // Lightning effect - bright green
            if (lightningLinks.has(linkKey)) {
              return '#00ff00';
            }
            // Highlight entire path to root for similar nodes
            if (highlightedLinks.has(linkKey)) {
              return 'hsl(160, 100%, 50%)'; // Bright cyan/green for path
            }
            const sim = similarityMap.get(targetId);
            if (sim) {
              return `hsl(${200 - sim * 40}, ${70 + sim * 30}%, ${40 + sim * 20}%)`;
            }
            return '#4b5563';
          }}
          backgroundColor="#030712"
          showNavInfo={false}
          // Callback when force simulation completes - triggers centering/rotation
          onEngineStop={handleEngineStop}
          // Debug: track simulation ticks
          onEngineTick={handleEngineTick}
          // Free 3D layout for better centering and panning (no dagMode)
          // Performance - warmupTicks for pre-render
          // cooldownTicks controls when simulation stops and onEngineStop fires
          // - 0 = stops immediately (too early, positions not ready)
          // - undefined = never stops (simulation runs forever)
          // - 200 = runs for ~200 ticks after warmup, enough for positions to stabilize
          warmupTicks={100}
          cooldownTicks={200}
          // Disable node dragging when auto-rotating to avoid conflicts
          enableNodeDrag={!enableAutoRotate}
          // Enable OrbitControls for manual panning/testing
          enableNavigationControls={true}
          // Particle effects - sparks during search and on similar paths
          linkDirectionalParticles={(link: any) => {
            if (isSearching) return 3; // Sparks everywhere during search
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            const sim = similarityMap.get(targetId);
            return sim && sim > 0.5 ? Math.ceil(sim * 4) : 0; // More particles for higher similarity
          }}
          linkDirectionalParticleSpeed={isSearching ? 0.02 : 0.008}
          linkDirectionalParticleWidth={(link: any) => {
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            const sim = similarityMap.get(targetId);
            return sim ? 2 + sim * 3 : 1.5;
          }}
          linkDirectionalParticleColor={(link: any) => {
            if (isSearching) return '#60a5fa'; // Blue sparks during search
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            const sim = similarityMap.get(targetId);
            if (sim) {
              return sim > 0.7 ? '#22c55e' : '#fbbf24'; // Green for high, yellow for medium
            }
            return '#60a5fa';
          }}
        />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-gray-400 text-sm">Initializing 3D renderer...</div>
          </div>
        )}
      </GraphErrorBoundary>
    </div>
  );
}
