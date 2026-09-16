import { useId } from "react";
import clsx from "clsx";

type Particle = {
  left: string;
  bottom: string;
  size: number;
  duration: number;
  delay: number;
  drift: number;
  color: string;
};

const PARTICLES: Particle[] = [
  { left: "8%", bottom: "14%", size: 4, duration: 13, delay: 0, drift: 18, color: "bg-accent" },
  { left: "16%", bottom: "54%", size: 3, duration: 17, delay: -6, drift: -14, color: "bg-status-medium" },
  { left: "28%", bottom: "30%", size: 5, duration: 15, delay: -3, drift: 26, color: "bg-accent" },
  { left: "47%", bottom: "64%", size: 3, duration: 12, delay: -8, drift: -20, color: "bg-status-success" },
  { left: "58%", bottom: "20%", size: 4, duration: 19, delay: -11, drift: 12, color: "bg-accent" },
  { left: "70%", bottom: "48%", size: 3, duration: 14, delay: -2, drift: -16, color: "bg-status-high" },
  { left: "80%", bottom: "14%", size: 5, duration: 16, delay: -9, drift: 22, color: "bg-accent" },
  { left: "90%", bottom: "38%", size: 3, duration: 18, delay: -4, drift: -10, color: "bg-status-medium" },
  { left: "36%", bottom: "76%", size: 4, duration: 15, delay: -12, drift: 16, color: "bg-accent" },
];

function DotGrid({ patternId, tile, radius, className, opacity }: { patternId: string; tile: number; radius: number; className: string; opacity: number }) {
  return (
    <svg
      className={clsx("absolute -inset-8 h-[calc(100%+64px)] w-[calc(100%+64px)]", className)}
      style={{ opacity }}
      fill="none"
      aria-hidden
    >
      <defs>
        <pattern id={patternId} width={tile} height={tile} patternUnits="userSpaceOnUse">
          <circle cx="3" cy="3" r={radius} fill="currentColor" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
    </svg>
  );
}

export default function MotionBackground({ className }: { className?: string }) {
  const softId = useId();
  const accentId = useId();

  return (
    <div aria-hidden className={clsx("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <DotGrid
        patternId={softId}
        tile={22}
        radius={1.3}
        className="text-border-strong animate-grid-pan motion-reduce:animate-none"
        opacity={0.7}
      />
      <DotGrid
        patternId={accentId}
        tile={22}
        radius={1.7}
        className="text-accent animate-grid-pan-rev motion-reduce:animate-none"
        opacity={0.32}
      />
      {PARTICLES.map((p, i) => (
        <span
          key={`${p.left}-${p.bottom}`}
          style={
            {
              left: p.left,
              bottom: p.bottom,
              width: p.size,
              height: p.size,
              animationDuration: `${p.duration}s`,
              animationDelay: `${p.delay}s`,
              "--drift-x": `${p.drift}px`,
              opacity: 0.3 + (i % 3) * 0.22,
            } as React.CSSProperties
          }
          className={clsx(
            "absolute rounded-full animate-particle-rise motion-reduce:animate-none",
            p.color
          )}
        />
      ))}
    </div>
  );
}