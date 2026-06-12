import * as React from "react";

type BadgeVariant = "rank" | "area" | "status-done" | "status-started" | "status-tool" | "status-failed" | "default";

const variantClasses: Record<BadgeVariant, string> = {
  rank: "bg-accent text-white font-semibold",
  area: "bg-accent-light text-accent font-medium",
  "status-done": "bg-accent-light text-accent",
  "status-started": "bg-blue-50 text-blue-700",
  "status-tool": "bg-amber-50 text-amber-700",
  "status-failed": "bg-red-50 text-danger",
  default: "bg-gray-100 text-ink-muted",
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs tracking-wide",
        variantClasses[variant],
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {children}
    </span>
  );
}
