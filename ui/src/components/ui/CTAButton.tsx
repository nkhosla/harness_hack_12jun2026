"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { postSlate } from "@/lib/api";
import { DEMO_REGION, DEMO_HORIZON } from "@/lib/constants";
import { cardHoverIn, cardHoverOut, focusRingIn, focusRingOut } from "@/lib/animations";

interface CTAButtonProps {
  label?: string;
  size?: "md" | "lg";
}

export function CTAButton({ label = "Create slate →", size = "lg" }: CTAButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const ref = React.useRef<HTMLButtonElement>(null);

  async function handleClick() {
    setError("");
    setLoading(true);
    try {
      const { run_id } = await postSlate(DEMO_REGION, DEMO_HORIZON);
      router.push(`/runs/${run_id}`);
    } catch {
      setError("Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  const sizeClasses =
    size === "lg"
      ? "py-4 px-10 text-base font-semibold"
      : "py-3 px-7 text-sm font-medium";

  return (
    <div>
      <button
        ref={ref}
        onClick={handleClick}
        disabled={loading}
        onMouseEnter={() => ref.current && cardHoverIn(ref.current)}
        onMouseLeave={() => ref.current && cardHoverOut(ref.current)}
        onFocus={() => ref.current && focusRingIn(ref.current)}
        onBlur={() => ref.current && focusRingOut(ref.current)}
        className={[
          sizeClasses,
          "rounded-md bg-accent text-white tracking-wide",
          "transition-colors duration-150 hover:bg-accent/90",
          "focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
          "outline-none disabled:opacity-60 disabled:cursor-not-allowed",
        ].join(" ")}
      >
        {loading ? "Creating slate…" : label}
      </button>
      {error && (
        <p className="text-danger text-xs mt-2 max-w-xs">{error}</p>
      )}
    </div>
  );
}
