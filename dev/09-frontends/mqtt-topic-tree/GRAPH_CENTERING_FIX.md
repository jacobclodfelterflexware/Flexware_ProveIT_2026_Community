# 3D Graph Centering Fix - Documentation

## Problem Summary

The 3D force graph visualization (using react-force-graph-3d) was consistently appearing off-center, shifted to the right in the viewport. This issue persisted through 20+ different attempted fixes involving camera positioning, rotation adjustments, and various centering strategies.

## Root Cause

**The Issue**: `react-force-graph-3d` defaults to using `window.innerWidth` × `window.innerHeight` for canvas sizing, but the graph was rendering inside a **smaller container** with max-width constraints (Tailwind's `max-w-7xl` class).

**The Math**:
- Window width: 1920px (full browser width)
- Container width: 1248px (max-w-7xl constraint)
- **Result**: Camera centered the graph for a 1920px canvas, but only the center 1248px was visible
- **Horizontal offset**: (1920 - 1248) / 2 = **336px off-center to the right**

## The Solution

### Step 1: Container-Based Sizing with ResizeObserver

Instead of letting react-force-graph-3d auto-size to the window, we explicitly measured the actual container dimensions and passed them to the component.

**File**: `components/machines/GraphVisualization.tsx`

```typescript
// Lines 100, 162-178

// 1. Initialize dimensions state with fallback
const [dimensions, setDimensions] = useState({ width: 1280, height: 600 });

// 2. Measure container dimensions with ResizeObserver
useEffect(() => {
  if (!containerRef.current) return;

  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const { width, height } = entry.contentRect;
      console.log('[Graph] Container resized:', { width, height });
      setDimensions({ width, height });
    }
  });

  resizeObserver.observe(containerRef.current);

  return () => {
    resizeObserver.disconnect();
  };
}, []);
```

**Key Points**:
- `ResizeObserver` measures the actual container's `contentRect`
- Updates happen automatically when container size changes
- Fallback dimensions (1280×600) prevent 0×0 canvas during initial render

### Step 2: Conditional Rendering

Only render ForceGraph3D after we have valid dimensions to prevent black canvas issues.

**File**: `components/machines/GraphVisualization.tsx`

```typescript
// Lines 494-562

<GraphErrorBoundary>
  {dimensions.width > 0 && dimensions.height > 0 ? (
    <ForceGraph3DWrapper
      fgRef={fgRef}
      width={dimensions.width}      // ← Pass measured width
      height={dimensions.height}    // ← Pass measured height
      graphData={graphData}
      // ... other props
    />
  ) : (
    <div className="w-full h-full flex items-center justify-center">
      <div className="text-gray-400 text-sm">Initializing 3D renderer...</div>
    </div>
  )}
</GraphErrorBoundary>
```

**Why This Works**:
- ForceGraph3D receives the exact container dimensions instead of window dimensions
- Camera calculations use the actual visible canvas size
- Graph appears mathematically centered in the viewport

### Step 3: Container Reference

Ensure the container has a ref for ResizeObserver to observe.

**File**: `components/machines/GraphVisualization.tsx`

```typescript
// Line 449

return (
  <div ref={containerRef} className="w-full h-full bg-gray-950 rounded-lg overflow-hidden relative">
    {/* Graph content */}
  </div>
);
```

## Additional Implementation: Manual Controls Interface

As part of the debugging process, we also implemented a comprehensive manual controls interface that allows real-time experimentation with camera and target positions.

### Manual Controls Features

**File**: `app/graph-test/page.tsx`

1. **Camera Position Controls**: Sliders and number inputs for X, Y, Z coordinates (-5000 to 5000 range)
2. **Target Position Controls**: Sliders and number inputs for where the camera looks
3. **Live Metrics Display**: Real-time monitoring of:
   - Window, Container, and Canvas dimensions with aspect ratios
   - Size mismatch detection and offset calculation
   - Current camera and target positions
   - Distance calculations
   - Graph center and node count

4. **Preset Views**: Quick buttons for Front View, Top View, Side View
5. **Auto-Rotate Toggle**: Disable rotation during experimentation
6. **Copy Values Button**: Copy current configuration to clipboard
7. **Reset Button**: Restore default camera/target positions

### GraphMetrics Interface

**File**: `types/graph.ts`

```typescript
export interface GraphMetrics {
  // Dimensions
  windowDimensions: { width: number; height: number; aspectRatio: string };
  containerDimensions: { width: number; height: number; aspectRatio: string };
  canvasDimensions: { width: number; height: number; aspectRatio: string };

  // Positions
  cameraPosition: { x: number; y: number; z: number };
  controlsTarget: { x: number; y: number; z: number };
  distance: number;

  // Graph data
  graphCenter: { x: number; y: number; z: number };
  nodeCount: number;

  // Diagnostics
  sizeMismatch?: {
    canvasWidth: number;
    containerWidth: number;
    horizontalOffset: number;
  };
}
```

### Metrics Collection

**File**: `components/machines/GraphVisualization.tsx`

The component now emits live metrics every 100ms when `onMetricsUpdate` callback is provided:

```typescript
// Lines 180-229

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
```

## Files Modified

1. **types/graph.ts** (lines 90-112)
   - Added `GraphMetrics` interface for live metrics data

2. **components/machines/GraphVisualization.tsx**
   - Lines 6: Added `GraphMetrics` import
   - Lines 72-84: Extended props interface with `manualControls` and `onMetricsUpdate`
   - Lines 86-93: Added new props to component signature
   - Lines 100: Changed initial dimensions to `{ width: 1280, height: 600 }` (fallback)
   - Lines 162-178: Added ResizeObserver effect to measure container
   - Lines 180-229: Added metrics collection effect
   - Lines 232-245: Added manual camera positioning effect
   - Line 302: Updated auto-rotation condition to respect `manualControls?.disableAutoRotate`
   - Lines 449: Added `ref={containerRef}` to container div
   - Lines 494-562: Added conditional rendering with width/height props

3. **app/graph-test/page.tsx**
   - Lines 5: Added `GraphMetrics` import
   - Lines 9-13: Added manual controls state
   - Lines 20-24: Created manualControls object
   - Lines 107-119: Added enable toggle in instructions panel
   - Lines 123-329: Added manual controls panel with camera/target sliders
   - Lines 332-400: Added live metrics display panel
   - Lines 408-410: Passed `manualControls` and `onMetricsUpdate` to GraphVisualization

## Verification

### Check for Size Mismatch

Open browser console and look for:

```
[Graph] ⚠️ SIZING MISMATCH DETECTED!
[Graph] Canvas is 1920 px but container is 1248 px
[Graph] Horizontal offset: 336 px
```

If you see this, the container-based sizing is NOT being applied.

### Confirm Correct Sizing

You should see:

```
[Graph] Container resized: { width: 1248, height: 600 }
[Graph] ✅ Canvas size matches container size
```

### Manual Controls Testing

1. Navigate to `/graph-test`
2. Enable "Enable Manual Controls" checkbox
3. Observe Live Metrics panel
4. Confirm "Canvas" dimensions match "Container" dimensions
5. No "SIZE MISMATCH" warning should appear

## Why Previous Attempts Failed

Over 20+ attempts were made using camera positioning, rotation adjustments, and manual offsets:

1. **Manual camera offsets** (X=-800, X=+800, etc.) - Addressed symptoms, not root cause
2. **Target offsets** - Same issue - treating symptoms
3. **zoomToFit() with various padding** - Still used window dimensions
4. **Manual distance calculations** - Ignored viewport framing issues
5. **Dynamic center reading** - Correct graph center, wrong viewport assumptions

**The key insight**: All these approaches assumed the canvas was correctly sized. The real issue was that the canvas itself was sized for the wrong viewport.

## The Winning Combination

1. **Measure the actual container** with ResizeObserver
2. **Pass explicit width/height** to ForceGraph3D
3. **Use fallback dimensions** to prevent black canvas
4. **Conditionally render** only when dimensions are valid
5. **Let zoomToFit() do its job** with the correctly sized canvas

## Impact

- **Before**: Graph consistently 336px off-center to the right
- **After**: Graph perfectly centered in viewport
- **Result**: Professional, polished user experience without manual adjustments

## Lessons Learned

1. **Trust the library**: `zoomToFit()` was never broken - our assumptions about canvas sizing were wrong
2. **Measure, don't assume**: Use ResizeObserver to get actual container dimensions
3. **Container vs Window**: Always be explicit about which viewport you're targeting
4. **Diagnostics matter**: The manual controls interface helped confirm the solution
5. **Persistence pays off**: 20+ attempts led to the correct mental model

---

**Date Fixed**: January 10, 2026
**Total Debugging Sessions**: 3+
**Total Attempts**: 20+
**Final Solution**: Container-based sizing with ResizeObserver
**Status**: ✅ RESOLVED

---

## Follow-up Fix: Connect Machine Wizard (January 10, 2026)

### Problem
The graph was STILL off-center in the Connect Machine wizard modal, even after the ResizeObserver fix above was implemented. The `/graph-test` page worked fine, but the wizard showed the graph shifted ~193px to the right.

### Root Cause
The ResizeObserver useEffect had `[]` (empty) dependencies, but the GraphVisualization component has a **loading state** that returns a different DOM structure:

1. Component mounts → `loading = true` → returns loading spinner div (**NO containerRef attached**)
2. useEffect with `[]` deps runs → `containerRef.current` is **null** → returns early, never sets up ResizeObserver
3. Data loads → `loading = false` → actual container div with `ref={containerRef}` mounts
4. useEffect has `[]` deps → **never re-runs** → dimensions stay at fallback 1280x600

The `/graph-test` page worked because it doesn't have a loading state that changes the DOM structure - the container is always present.

### Console Evidence
```
[Wizard] GraphVisualization container dimensions: { width: 894, height: 758 }  // Actual size
[Graph] Container dimensions (from ResizeObserver): { width: 1280, height: 600 }  // Fallback!
```

The wizard's outer container correctly measured 894x758, but GraphVisualization's internal state was stuck at the fallback 1280x600.

### The Fix
Two changes to `components/machines/GraphVisualization.tsx`:

**1. Add `requestAnimationFrame` for initial measurement (lines 168-176):**
```typescript
requestAnimationFrame(() => {
  if (containerRef.current) {
    const rect = containerRef.current.getBoundingClientRect();
    console.log('[Graph] Initial container measurement:', { width: rect.width, height: rect.height });
    if (rect.width > 0 && rect.height > 0) {
      setDimensions({ width: rect.width, height: rect.height });
    }
  }
});
```

**2. Add `loading` to useEffect dependency array (line 193):**
```typescript
// Before
}, []);

// After
}, [loading]);  // Re-run when loading changes so we measure after container mounts
```

### Why This Works
- When `loading` changes from `true` to `false`, the useEffect re-runs
- At that point, the actual container div with `ref={containerRef}` is now mounted
- `containerRef.current` is no longer null
- ResizeObserver successfully attaches and measures the real container dimensions

### Verification
After the fix, console shows:
```
[Graph] Initial container measurement: { width: 894, height: 758 }
[Graph] Container resized: { width: 894, height: 758 }
[Graph] ✅ Canvas size matches container size
```

### Key Insight
When a component has conditional rendering based on loading state, useEffects with `[]` dependencies will run **before** the final DOM structure is mounted. Always include any state variables in the dependency array if they affect which DOM elements are rendered.

**Status**: ✅ FULLY RESOLVED
