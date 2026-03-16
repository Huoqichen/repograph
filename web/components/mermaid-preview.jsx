"use client";

import { useEffect, useId, useRef, useState } from "react";

export function MermaidPreview({ chart, fallbackLabel }) {
  const containerRef = useRef(null);
  const [hasError, setHasError] = useState(false);
  const instanceId = useId().replace(/:/g, "");

  useEffect(() => {
    let isActive = true;

    async function renderChart() {
      if (!chart || !containerRef.current) {
        return;
      }

      setHasError(false);

      try {
        const mermaidModule = await import("mermaid");
        const mermaid = mermaidModule.default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "loose",
          theme: "neutral",
          flowchart: {
            htmlLabels: true,
            curve: "basis",
            useMaxWidth: true
          }
        });

        const renderId = `repomap-mermaid-${instanceId}-${Date.now()}`;
        const { svg, bindFunctions } = await mermaid.render(renderId, chart);
        if (!isActive || !containerRef.current) {
          return;
        }

        containerRef.current.innerHTML = svg;
        bindFunctions?.(containerRef.current);
      } catch {
        if (isActive) {
          setHasError(true);
        }
      }
    }

    void renderChart();
    return () => {
      isActive = false;
      if (containerRef.current) {
        containerRef.current.innerHTML = "";
      }
    };
  }, [chart, instanceId]);

  if (hasError) {
    return <div className="mermaid-fallback">{fallbackLabel}</div>;
  }

  return <div className="mermaid-preview" ref={containerRef} />;
}
