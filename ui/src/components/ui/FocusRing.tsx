"use client";

import * as React from "react";
import { focusRingIn, focusRingOut } from "@/lib/animations";

interface FocusRingProps {
  children: React.ReactElement<React.HTMLAttributes<HTMLElement>>;
  className?: string;
}

export function FocusRing({ children, className }: FocusRingProps) {
  const ref = React.useRef<HTMLElement>(null);

  const handleFocus = React.useCallback(() => {
    if (ref.current) focusRingIn(ref.current);
  }, []);

  const handleBlur = React.useCallback(() => {
    if (ref.current) focusRingOut(ref.current);
  }, []);

  return React.cloneElement(children, {
    ref,
    onFocus: handleFocus,
    onBlur: handleBlur,
    className: [
      children.props.className,
      "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
      className,
    ]
      .filter(Boolean)
      .join(" "),
  } as React.HTMLAttributes<HTMLElement>);
}
