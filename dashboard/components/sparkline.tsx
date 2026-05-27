"use client";

/**
 * Sparkline — tiny, dependency-free SVG line chart.
 *
 * One <svg> with a polyline + an area fill. Designed for stat cards and
 * dashboards where pulling in recharts would be overkill.
 */

export type SparkPoint = { x: number; y: number; label?: string };

export function Sparkline({
  points,
  width = 220,
  height = 56,
  stroke = "var(--sentinel-accent)",
  fill = "var(--sentinel-accent-dim)",
  showAxis = false,
}: {
  points: SparkPoint[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  showAxis?: boolean;
}) {
  if (points.length === 0) {
    return (
      <div
        style={{
          width,
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--sentinel-text-muted)",
          fontSize: "0.7rem",
        }}
      >
        no data
      </div>
    );
  }

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys, 0);
  const yMax = Math.max(...ys);
  const pad = 4;
  const w = width - pad * 2;
  const h = height - pad * 2;
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;

  const sx = (x: number) => pad + ((x - xMin) / xRange) * w;
  const sy = (y: number) => pad + h - ((y - yMin) / yRange) * h;

  const poly = points.map((p) => `${sx(p.x)},${sy(p.y)}`).join(" ");
  const area = `${sx(xs[0])},${pad + h} ${poly} ${sx(xs[xs.length - 1])},${pad + h}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polygon points={area} fill={fill} opacity={0.35} />
      <polyline
        points={poly}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {showAxis && (
        <line
          x1={pad}
          y1={pad + h}
          x2={pad + w}
          y2={pad + h}
          stroke="var(--sentinel-border-subtle)"
          strokeWidth={0.5}
        />
      )}
    </svg>
  );
}
