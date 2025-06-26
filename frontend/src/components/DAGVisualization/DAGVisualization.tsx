import React, { useEffect, useRef, useMemo } from 'react';
import * as d3 from 'd3';
import { Card } from 'antd';
import type { WorkflowNode } from '../../types/workflow';

interface DAGVisualizationProps {
  nodes: Record<string, WorkflowNode>;
  outputs: Record<string, string>;
  inputs: Record<string, any>;
}

// Node type configuration
const nodeTypeConfig = {
  llm: { icon: '🤖', color: '#1890ff', label: 'LLM' },
  http: { icon: '🌐', color: '#52c41a', label: 'HTTP' },
  file: { icon: '📄', color: '#faad14', label: 'File' },
  python: { icon: '🐍', color: '#722ed1', label: 'Python' },
  conditional: { icon: '🔀', color: '#eb2f96', label: 'Conditional' },
  route: { icon: '🔀', color: '#eb2f96', label: 'Route' },
  split: { icon: '🔀', color: '#13c2c2', label: 'Split' },
  aggregate: { icon: '📊', color: '#fa8c16', label: 'Aggregate' },
  filter: { icon: '🔍', color: '#a0d911', label: 'Filter' },
  transform: { icon: '🔄', color: '#1890ff', label: 'Transform' },
  join: { icon: '🔗', color: '#2f54eb', label: 'Join' },
  foreach: { icon: '🔁', color: '#531dab', label: 'ForEach' },
};

export const DAGVisualization: React.FC<DAGVisualizationProps> = ({ nodes = {}, outputs = {} }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate hierarchical layout
  const layoutData = useMemo(() => {
    // Build adjacency lists
    const nodeIds = Object.keys(nodes);
    const allNodeIds = ['inputs', ...nodeIds, 'outputs'];
    const children: Record<string, string[]> = {};
    const parents: Record<string, string[]> = {};

    // Track which nodes are downstream of fan-out operations
    const downstreamOfFanOut: Set<string> = new Set();

    // Initialize
    allNodeIds.forEach((id) => {
      children[id] = [];
      parents[id] = [];
    });

    // Build relationships
    nodeIds.forEach((id) => {
      const node = nodes[id];
      if (!node.depends_on || node.depends_on.length === 0) {
        children['inputs'].push(id);
        parents[id].push('inputs');
      } else {
        node.depends_on.forEach((dep) => {
          if (nodes[dep]) {
            children[dep].push(id);
            parents[id].push(dep);
          }
        });
      }
    });

    // Connect to outputs
    Object.entries(outputs).forEach(([, sourceNode]) => {
      if (typeof sourceNode === 'string' && nodes[sourceNode]) {
        children[sourceNode].push('outputs');
        parents['outputs'].push(sourceNode);
      }
    });

    // Identify fan-out and fan-in nodes
    const fanOutNodes = new Set<string>();
    const fanInNodes = new Set<string>();
    nodeIds.forEach((id) => {
      const node = nodes[id];
      if (node.type === 'split' || node.type === 'foreach') {
        fanOutNodes.add(id);
      }
      if (node.type === 'aggregate' || node.type === 'join') {
        fanInNodes.add(id);
      }
    });

    // Track which nodes are upstream of fan-in operations
    const upstreamOfFanIn = new Set<string>();

    // BFS to mark all ancestors of fan-in nodes
    const markAncestors = (startNode: string) => {
      const queue = [...parents[startNode]];
      const visited = new Set<string>();

      while (queue.length > 0) {
        const current = queue.shift()!;
        if (visited.has(current)) continue;

        visited.add(current);
        upstreamOfFanIn.add(current);

        // Add parents to queue
        if (parents[current]) {
          queue.push(...parents[current]);
        }
      }
    };

    fanInNodes.forEach((fanInNode) => markAncestors(fanInNode));

    // BFS to mark all descendants of fan-out nodes, but stop at fan-in nodes
    const markDescendants = (startNode: string) => {
      const queue = [...children[startNode]];
      const visited = new Set<string>();

      while (queue.length > 0) {
        const current = queue.shift()!;
        if (visited.has(current)) continue;

        visited.add(current);

        // Only mark as downstream if it's also upstream of a fan-in
        if (upstreamOfFanIn.has(current)) {
          downstreamOfFanOut.add(current);
        }

        // Don't traverse past fan-in nodes
        if (!fanInNodes.has(current) && children[current]) {
          queue.push(...children[current]);
        }
      }
    };

    fanOutNodes.forEach((fanOutNode) => markDescendants(fanOutNode));

    // Calculate node levels - minimize depth while respecting dependencies
    const nodeLevel: Record<string, number> = {};

    // Helper to calculate minimum level for a node
    const calculateLevel = (nodeId: string): number => {
      if (nodeId in nodeLevel) return nodeLevel[nodeId];

      // Base case: inputs is at level 0
      if (nodeId === 'inputs') {
        nodeLevel[nodeId] = 0;
        return 0;
      }

      // Calculate based on parents
      let maxParentLevel = -1;
      parents[nodeId].forEach((parent) => {
        const parentLevel = calculateLevel(parent);
        maxParentLevel = Math.max(maxParentLevel, parentLevel);
      });

      nodeLevel[nodeId] = maxParentLevel + 1;
      return nodeLevel[nodeId];
    };

    // Calculate levels for all nodes
    allNodeIds.forEach((nodeId) => calculateLevel(nodeId));

    // Compact levels - move nodes to earlier levels if possible
    // This helps nodes that don't depend on each other to be at the same level
    const compactLevels = () => {
      let changed = true;
      while (changed) {
        changed = false;

        Object.keys(nodes).forEach((nodeId) => {
          const currentLevel = nodeLevel[nodeId];

          // Find the minimum level this node can be at
          let minLevel = 0;
          parents[nodeId].forEach((parent) => {
            if (parent in nodeLevel) {
              minLevel = Math.max(minLevel, nodeLevel[parent] + 1);
            }
          });

          // Also check children to ensure we don't create backward edges
          let maxLevel = Infinity;
          children[nodeId].forEach((child) => {
            if (child in nodeLevel && child !== 'outputs') {
              maxLevel = Math.min(maxLevel, nodeLevel[child] - 1);
            }
          });

          // Find optimal level
          const optimalLevel = Math.min(minLevel, maxLevel);
          if (optimalLevel < currentLevel && optimalLevel >= 0 && optimalLevel < Infinity) {
            nodeLevel[nodeId] = optimalLevel;
            changed = true;
          }
        });
      }
    };

    compactLevels();

    // Ensure outputs is at the last level
    const maxLevel = Math.max(...Object.values(nodeLevel));
    nodeLevel['outputs'] = maxLevel + 1;

    // Group nodes by level
    const levels: Record<number, string[]> = {};
    Object.entries(nodeLevel).forEach(([nodeId, level]) => {
      if (!levels[level]) {
        levels[level] = [];
      }
      levels[level].push(nodeId);
    });

    // Convert to array
    const levelArray = Object.keys(levels)
      .sort((a, b) => Number(a) - Number(b))
      .map((level) => levels[Number(level)]);

    // Calculate positions
    const nodeWidth = 180;
    const nodeHeight = 60;
    const levelSpacing = 280;
    const nodeSpacing = 120; // Increased spacing for better clarity

    const positions: Record<string, { x: number; y: number }> = {};

    // Position nodes with simple vertical centering
    levelArray.forEach((level, levelIndex) => {
      const x = levelIndex * levelSpacing + 100;
      const totalHeight = level.length * nodeSpacing;
      const startY = 300 - totalHeight / 2;

      level.forEach((nodeId, nodeIndex) => {
        positions[nodeId] = {
          x,
          y: startY + nodeIndex * nodeSpacing,
        };
      });
    });

    // Build edge list
    const edgeList: Array<{ source: string; target: string }> = [];
    Object.entries(children).forEach(([parent, childList]) => {
      childList.forEach((child) => {
        edgeList.push({ source: parent, target: child });
      });
    });

    // Pre-calculate which edges need to bypass and assign them lanes
    const bypassEdges = new Map<string, { lane: number; above: boolean }>();
    const edgesNeedingBypass: Array<{ edge: { source: string; target: string }; sy: number }> = [];

    edgeList.forEach((edge) => {
      const source = positions[edge.source];
      const target = positions[edge.target];
      if (!source || !target) return;

      const sx = source.x + nodeWidth / 2;
      const sy = source.y;
      const tx = target.x - nodeWidth / 2;

      // Check if this edge needs to bypass nodes
      const obstacleNodes = Object.entries(positions).filter(([id, pos]) => {
        if (id === edge.source || id === edge.target) return false;
        return pos.x > sx && pos.x < tx;
      });

      if (obstacleNodes.length > 0) {
        edgesNeedingBypass.push({ edge, sy });
      }
    });

    // Sort by Y position and assign lanes
    edgesNeedingBypass.sort((a, b) => a.sy - b.sy);

    // Assign lanes alternating above and below
    edgesNeedingBypass.forEach(({ edge }, index) => {
      const laneNumber = Math.floor(index / 2);
      const above = index % 2 === 0;
      bypassEdges.set(`${edge.source}-${edge.target}`, { lane: laneNumber, above });
    });

    return {
      positions,
      edges: edgeList,
      nodeWidth,
      nodeHeight,
      parents,
      children,
      downstreamOfFanOut,
      bypassEdges,
    };
  }, [nodes, outputs]);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = 600;
    const { positions, edges, nodeWidth, nodeHeight, downstreamOfFanOut, bypassEdges } = layoutData;
    const levelSpacing = 280; // Same as used in layout calculation

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current).attr('width', width).attr('height', height);

    // Create arrow markers
    const defs = svg.append('defs');

    // Different colored arrows
    ['#1890ff', '#52c41a', '#666', '#999'].forEach((color) => {
      defs
        .append('marker')
        .attr('id', `arrow-${color.replace('#', '')}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 8)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color);
    });

    // Create group for zoom/pan
    const g = svg.append('g');

    // Add zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 2])
      .on('zoom', (event) => {
        g.attr('transform', event.transform.toString());
      });

    svg.call(zoom);

    // Draw edges first (so they're behind nodes)
    const edgeGroup = g.append('g').attr('class', 'edges');

    edges.forEach((edge) => {
      const source = positions[edge.source];
      const target = positions[edge.target];

      if (!source || !target) return;

      // Only connect left-to-right if nodes are in correct order
      if (source.x >= target.x) return;

      // Calculate edge start and end points - always use side handles
      const sx = source.x + nodeWidth / 2;
      const sy = source.y;
      const tx = target.x - nodeWidth / 2;
      const ty = target.y;

      // Skip if horizontal distance is too small
      if (tx - sx < 10) return;

      // Determine edge color
      let edgeColor = '#999';
      let markerColor = '999';
      if (edge.source === 'inputs') {
        edgeColor = '#1890ff';
        markerColor = '1890ff';
      } else if (edge.target === 'outputs') {
        edgeColor = '#52c41a';
        markerColor = '52c41a';
      }

      // Calculate control points for smooth curve that avoids overlapping nodes
      const dx = tx - sx;
      let needsDetour = false;

      // Check all node positions to see if edge would cross them
      Object.entries(positions).forEach(([nodeId, pos]) => {
        if (nodeId !== edge.source && nodeId !== edge.target) {
          // Account for stacked cards offset (up to 18px for parallel nodes)
          const nodeLeftEdge = pos.x - nodeWidth / 2;
          const nodeRightEdge = pos.x + nodeWidth / 2 + (downstreamOfFanOut.has(nodeId) ? 18 : 0);
          const nodeTopEdge = pos.y - nodeHeight / 2;
          const nodeBottomEdge = pos.y + nodeHeight / 2 + (downstreamOfFanOut.has(nodeId) ? 18 : 0);

          // Check if node is in the horizontal path
          if (nodeRightEdge > sx && nodeLeftEdge < tx) {
            // For straight line between source and target
            const t = (pos.x - sx) / dx;
            if (t >= 0 && t <= 1) {
              const edgeY = sy + (ty - sy) * t;
              // Check if edge would pass through node bounds
              if (edgeY >= nodeTopEdge && edgeY <= nodeBottomEdge) {
                needsDetour = true;
              }
            }
          }
        }
      });

      // Additional check for edges that span multiple levels
      if (!needsDetour && Math.abs(tx - sx) > levelSpacing * 1.5) {
        // Check if there are any nodes at intermediate x positions
        const stepSize = nodeWidth;
        for (let checkX = sx + stepSize; checkX < tx - stepSize; checkX += stepSize) {
          Object.entries(positions).forEach(([nodeId, pos]) => {
            if (nodeId !== edge.source && nodeId !== edge.target) {
              // Check if a node is near this x position
              if (Math.abs(pos.x - checkX) < nodeWidth) {
                // Interpolate where the edge would be at this x
                const t = (checkX - sx) / (tx - sx);
                const edgeY = sy + (ty - sy) * t;

                // Check vertical collision
                const nodeTop = pos.y - nodeHeight / 2 - 10;
                const nodeBottom = pos.y + nodeHeight / 2 + 10;
                if (edgeY >= nodeTop && edgeY <= nodeBottom) {
                  needsDetour = true;
                }
              }
            }
          });
        }
      }

      let path;

      // For edges that need to detour around nodes
      if (needsDetour) {
        const edgeKey = `${edge.source}-${edge.target}`;
        const bypassInfo = bypassEdges.get(edgeKey);

        if (bypassInfo) {
          // Find all nodes between source and target that we need to avoid
          const obstacleNodes = Object.entries(positions).filter(([id, pos]) => {
            if (id === edge.source || id === edge.target) return false;
            return pos.x > sx && pos.x < tx;
          });

          if (obstacleNodes.length > 0) {
            // Get the Y bounds of obstacles
            const yPositions = obstacleNodes.map(([, p]) => p.y);
            const minObstacleY = Math.min(...yPositions) - nodeHeight / 2;
            const maxObstacleY = Math.max(...yPositions) + nodeHeight / 2;

            // Use pre-assigned lane
            const laneSpacing = 50;
            const baseOffset = 60;
            const routeY = bypassInfo.above
              ? minObstacleY - baseOffset - bypassInfo.lane * laneSpacing
              : maxObstacleY + baseOffset + bypassInfo.lane * laneSpacing;

            // Create a smooth curve that goes around
            const cp1x = sx + Math.min(dx * 0.3, 80);
            const cp2x = tx - Math.min(dx * 0.3, 80);

            path = `M ${sx} ${sy} C ${cp1x} ${sy}, ${cp1x} ${routeY}, ${(sx + tx) / 2} ${routeY} S ${cp2x} ${ty}, ${tx} ${ty}`;
          }
        }
      }

      if (!path && (needsDetour || Math.abs(ty - sy) > nodeHeight / 2)) {
        // Use a more curved path to avoid nodes
        const verticalDistance = Math.abs(ty - sy);
        const cp1x = sx + Math.min(dx * 0.4, 100);
        const cp2x = tx - Math.min(dx * 0.4, 100);

        // Make the curve more pronounced for vertical distances
        const curveOffset = Math.sign(ty - sy) * Math.min(verticalDistance * 0.7, 100);

        // For large vertical distances, use S-curve to avoid overlaps
        if (verticalDistance > nodeHeight * 2) {
          const midX = (sx + tx) / 2;
          path = `M ${sx} ${sy} C ${cp1x} ${sy}, ${midX} ${sy + curveOffset}, ${midX} ${(sy + ty) / 2} S ${cp2x} ${ty}, ${tx} ${ty}`;
        } else {
          path = `M ${sx} ${sy} C ${cp1x} ${sy + curveOffset}, ${cp2x} ${ty - curveOffset}, ${tx} ${ty}`;
        }
      } else if (!path) {
        // Simple horizontal curve for aligned nodes
        const cp1x = sx + dx * 0.5;
        const cp2x = tx - dx * 0.5;
        path = `M ${sx} ${sy} C ${cp1x} ${sy}, ${cp2x} ${ty}, ${tx} ${ty}`;
      }

      edgeGroup
        .append('path')
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', edgeColor)
        .attr('stroke-width', 1.5)
        .attr('opacity', 0.6)
        .attr('marker-end', `url(#arrow-${markerColor})`);
    });

    // Draw nodes
    const nodeGroup = g.append('g').attr('class', 'nodes');

    // Helper to draw a node
    function drawNode(id: string, type: string, label: string) {
      const pos = positions[id];
      if (!pos) return;

      const group = nodeGroup
        .append('g')
        .attr('transform', `translate(${pos.x - nodeWidth / 2}, ${pos.y - nodeHeight / 2})`);

      // Check if this node is downstream of a fan-out operation
      const isParallel = downstreamOfFanOut.has(id) && type !== 'aggregate' && type !== 'join';

      // Determine colors
      let fillColor = '#f0f0f0';
      let strokeColor = '#d9d9d9';
      const strokeWidth = 2;
      let icon = '📦';
      let typeLabel = type;

      if (type === 'input') {
        fillColor = '#e6f7ff';
        strokeColor = '#1890ff';
        icon = '📥';
        typeLabel = '';
      } else if (type === 'output') {
        fillColor = '#f6ffed';
        strokeColor = '#52c41a';
        icon = '📤';
        typeLabel = '';
      } else {
        const config = nodeTypeConfig[type as keyof typeof nodeTypeConfig];
        if (config) {
          fillColor = config.color + '20';
          strokeColor = config.color;
          icon = config.icon;
          typeLabel = config.label;
        }
      }

      // Draw stacked cards effect for parallel nodes
      if (isParallel) {
        // Draw shadow cards behind - more prominent stacking
        for (let i = 3; i >= 1; i--) {
          const offset = i * 6; // Bigger offset for more visibility
          group
            .append('rect')
            .attr('width', nodeWidth)
            .attr('height', nodeHeight)
            .attr('x', offset)
            .attr('y', offset)
            .attr('rx', 8)
            .attr('fill', i === 3 ? '#d0d0d0' : '#e0e0e0')
            .attr('stroke', '#999')
            .attr('stroke-width', 1.5)
            .attr('opacity', 0.7);
        }
      }

      // Draw main rectangle
      group
        .append('rect')
        .attr('width', nodeWidth)
        .attr('height', nodeHeight)
        .attr('rx', 8)
        .attr('fill', fillColor)
        .attr('stroke', strokeColor)
        .attr('stroke-width', strokeWidth)
        .style('filter', 'drop-shadow(0 1px 2px rgba(0, 0, 0, 0.1))');

      // Add icon
      group
        .append('text')
        .attr('x', 15)
        .attr('y', nodeHeight / 2 + 5)
        .attr('font-size', '20px')
        .text(icon);

      // Add main label
      group
        .append('text')
        .attr('x', nodeWidth / 2)
        .attr('y', nodeHeight / 2 - 5)
        .attr('text-anchor', 'middle')
        .attr('font-weight', 'bold')
        .attr('font-size', '14px')
        .text(label);

      // Add type label
      if (typeLabel) {
        group
          .append('text')
          .attr('x', nodeWidth / 2)
          .attr('y', nodeHeight / 2 + 15)
          .attr('text-anchor', 'middle')
          .attr('font-size', '12px')
          .attr('fill', '#666')
          .text(typeLabel);
      }

      // Add parallel instance indicator
      if (isParallel) {
        const parallelGroup = group
          .append('g')
          .attr('transform', `translate(${nodeWidth - 20}, -18)`);

        // Background with distinct color
        parallelGroup
          .append('rect')
          .attr('x', -25)
          .attr('y', -12)
          .attr('width', 50)
          .attr('height', 24)
          .attr('rx', 12)
          .attr('fill', '#FF6B6B')
          .attr('opacity', 0.9);

        // Parallel indicator text
        parallelGroup
          .append('text')
          .attr('text-anchor', 'middle')
          .attr('dy', 3)
          .attr('font-size', '11px')
          .attr('font-weight', 'bold')
          .attr('fill', 'white')
          .text('N × ∥');
      }
    }

    // Draw all nodes
    drawNode('inputs', 'input', 'Inputs');

    Object.entries(nodes).forEach(([id, node]) => {
      drawNode(id, node.type, id);
    });

    drawNode('outputs', 'output', 'Outputs');

    // Center the view
    const bounds = g.node()?.getBBox();
    if (bounds) {
      const fullWidth = bounds.width;
      const fullHeight = bounds.height;
      const midX = bounds.x + fullWidth / 2;
      const midY = bounds.y + fullHeight / 2;

      const scale = 0.9 * Math.min(width / fullWidth, height / fullHeight);
      const translate = [width / 2 - scale * midX, height / 2 - scale * midY];

      svg.call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
    }
  }, [layoutData, nodes]);

  // Don't render if we don't have nodes
  if (!nodes || Object.keys(nodes).length === 0) {
    return (
      <Card
        style={{ height: '600px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <span style={{ color: '#999' }}>No workflow nodes to visualize</span>
      </Card>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '600px',
        border: '1px solid #f0f0f0',
        borderRadius: '8px',
        overflow: 'hidden',
        background: '#fafafa',
      }}
    >
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>
    </div>
  );
};

export default DAGVisualization;
