"use client";

import * as React from "react";
import { cardHoverIn, cardHoverOut, focusRingIn, focusRingOut } from "@/lib/animations";

interface AnimatedCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  tabIndex?: number;
  className?: string;
  "data-card"?: boolean;
}

export function AnimatedCard({
  children,
  className,
  tabIndex,
  ...props
}: AnimatedCardProps) {
  const ref = React.useRef<HTMLDivElement>(null);

  const handleMouseEnter = () => { if (ref.current) cardHoverIn(ref.current); };
  const handleMouseLeave = () => { if (ref.current) cardHoverOut(ref.current); };
  const handleFocus = () => { if (ref.current) focusRingIn(ref.current); };
  const handleBlur = () => { if (ref.current) focusRingOut(ref.current); };

  return (
    <div
      ref={ref}
      tabIndex={tabIndex}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
      onBlur={handleBlur}
      className={[
        "bg-surface rounded-lg shadow-card outline-none",
        "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    >
      {children}
    </div>
  );
}
