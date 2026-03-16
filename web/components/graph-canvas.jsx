"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

const layerColors = {
  Frontend: "#93c5fd",
  Backend: "#86efac",
  Database: "#fdba74",
  Infrastructure: "#c4b5fd",
  Shared: "#d1d5db"
};

const preferredLayerOrder = ["Frontend", "Backend", "Shared", "Database", "Infrastructure"];

export function GraphCanvas({ nodes, edges, onSelect, selectedNodeId, layoutMode = "force" }) {
  const svgRef = useRef(null);

  useEffect(() => {
    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth || 960;
    const height = svgRef.current.clientHeight || 620;

    svg.selectAll("*").remove();
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const root = svg.append("g");
    const zoom = d3.zoom().scaleExtent([0.35, 2.4]).on("zoom", (event) => {
      root.attr("transform", event.transform);
    });
    svg.call(zoom);

    const simulationNodes = nodes.map((node) => ({ ...node }));
    const nodeById = new Map(simulationNodes.map((node) => [node.id, node]));
    const simulationLinks = edges.map((edge) => ({
      ...edge,
      source: typeof edge.source === "string" ? (nodeById.get(edge.source) || edge.source) : edge.source,
      target: typeof edge.target === "string" ? (nodeById.get(edge.target) || edge.target) : edge.target
    }));
    const simulation =
      layoutMode === "force"
        ? d3
            .forceSimulation(simulationNodes)
            .force(
              "link",
              d3
                .forceLink(simulationLinks)
                .id((item) => item.id)
                .distance(110)
                .strength(0.25)
            )
            .force("charge", d3.forceManyBody().strength(-260))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(38))
        : null;

    if (layoutMode === "layered") {
      applyLayeredLayout(simulationNodes, width, height);
    } else if (layoutMode === "radial") {
      applyRadialLayout(simulationNodes, width, height);
    }

    const link = root
      .append("g")
      .attr("stroke", "rgba(31, 29, 26, 0.22)")
      .attr("stroke-width", 1.2)
      .selectAll("line")
      .data(simulationLinks)
      .join("line");

    const node = root
      .append("g")
      .selectAll("g")
      .data(simulationNodes)
      .join("g")
      .style("cursor", "pointer")
      .call(simulation ? drag(simulation) : (selection) => selection);

    node
      .append("circle")
      .attr("r", (item) => (item.id === selectedNodeId ? 24 : 19))
      .attr("fill", (item) => layerColors[item.layer] || layerColors.Shared)
      .attr("stroke", (item) => (item.id === selectedNodeId ? "#0f766e" : "rgba(31, 29, 26, 0.35)"))
      .attr("stroke-width", (item) => (item.id === selectedNodeId ? 3 : 1.5));

    node
      .append("text")
      .text((item) => item.label)
      .attr("y", 34)
      .attr("text-anchor", "middle")
      .attr("font-size", 11)
      .attr("font-family", "var(--font-mono), monospace")
      .attr("fill", "#2f2a24");

    node
      .append("title")
      .text((item) => `${item.label}\n${item.language} · ${item.layer}\n${item.path}`);

    node.on("click", (_, item) => {
      onSelect(item);
      if (item.url) {
        window.open(item.url, "_blank", "noopener,noreferrer");
      }
    });

    const renderFrame = () => {
      link
        .attr("x1", (item) => item.source.x)
        .attr("y1", (item) => item.source.y)
        .attr("x2", (item) => item.target.x)
        .attr("y2", (item) => item.target.y);

      node.attr("transform", (item) => `translate(${item.x},${item.y})`);
    };

    if (simulation) {
      simulation.on("tick", renderFrame);
    } else {
      renderFrame();
    }

    return () => {
      simulation?.stop();
    };
  }, [edges, layoutMode, nodes, onSelect, selectedNodeId]);

  return <svg aria-label="Architecture graph" className="graph-canvas" ref={svgRef} role="img" />;
}

function drag(simulation) {
  function dragStarted(event, item) {
    if (!event.active) {
      simulation.alphaTarget(0.2).restart();
    }
    item.fx = item.x;
    item.fy = item.y;
  }

  function dragged(event, item) {
    item.fx = event.x;
    item.fy = event.y;
  }

  function dragEnded(event, item) {
    if (!event.active) {
      simulation.alphaTarget(0);
    }
    item.fx = null;
    item.fy = null;
  }

  return d3.drag().on("start", dragStarted).on("drag", dragged).on("end", dragEnded);
}

function applyLayeredLayout(nodes, width, height) {
  const grouped = groupNodesByLayer(nodes);
  const orderedLayers = sortLayers([...grouped.keys()]);
  const horizontalPadding = 110;
  const verticalPadding = 110;
  const usableWidth = Math.max(width - horizontalPadding * 2, 1);
  const columnGap = orderedLayers.length > 1 ? usableWidth / (orderedLayers.length - 1) : 0;

  orderedLayers.forEach((layer, layerIndex) => {
    const layerNodes = grouped.get(layer) || [];
    const usableHeight = Math.max(height - verticalPadding * 2, 1);
    const rowGap = layerNodes.length > 1 ? usableHeight / (layerNodes.length - 1) : 0;
    layerNodes.forEach((node, nodeIndex) => {
      node.x = horizontalPadding + columnGap * layerIndex;
      node.y =
        layerNodes.length === 1
          ? height / 2
          : verticalPadding + rowGap * nodeIndex;
    });
  });
}

function applyRadialLayout(nodes, width, height) {
  const grouped = groupNodesByLayer(nodes);
  const orderedLayers = sortLayers([...grouped.keys()]);
  const centerX = width / 2;
  const centerY = height / 2;
  const baseRadius = Math.min(width, height) * 0.16;
  const ringGap = Math.min(width, height) * 0.1;

  orderedLayers.forEach((layer, layerIndex) => {
    const layerNodes = grouped.get(layer) || [];
    const radius = baseRadius + ringGap * layerIndex;
    layerNodes.forEach((node, nodeIndex) => {
      const angle = (Math.PI * 2 * nodeIndex) / Math.max(layerNodes.length, 1);
      node.x = centerX + Math.cos(angle) * radius;
      node.y = centerY + Math.sin(angle) * radius;
    });
  });
}

function groupNodesByLayer(nodes) {
  const grouped = new Map();
  [...nodes]
    .sort((left, right) => left.label.localeCompare(right.label))
    .forEach((node) => {
      const existing = grouped.get(node.layer) || [];
      existing.push(node);
      grouped.set(node.layer, existing);
    });
  return grouped;
}

function sortLayers(layers) {
  const custom = layers.filter((layer) => !preferredLayerOrder.includes(layer)).sort();
  return [...preferredLayerOrder.filter((layer) => layers.includes(layer)), ...custom];
}
