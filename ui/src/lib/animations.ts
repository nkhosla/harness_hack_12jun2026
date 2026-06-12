"use client";

import type { gsap as GSAPType } from "gsap";

let gsapInstance: typeof GSAPType | null = null;

async function getGsap(): Promise<typeof GSAPType> {
  if (!gsapInstance) {
    const mod = await import("gsap");
    gsapInstance = mod.gsap;
  }
  return gsapInstance;
}

export async function fadeUpIn(el: Element, delay = 0): Promise<void> {
  const gsap = await getGsap();
  gsap.fromTo(
    el,
    { opacity: 0, y: 16 },
    { opacity: 1, y: 0, duration: 0.35, ease: "power2.out", delay }
  );
}

export async function staggerIn(
  els: Element[] | NodeListOf<Element>,
  staggerDelay = 0.06
): Promise<void> {
  const gsap = await getGsap();
  gsap.fromTo(
    Array.from(els),
    { opacity: 0, y: 16 },
    {
      opacity: 1,
      y: 0,
      duration: 0.35,
      ease: "power2.out",
      stagger: staggerDelay,
    }
  );
}

export async function cardHoverIn(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.to(el, {
    y: -4,
    boxShadow:
      "0 10px 25px -5px rgb(0 0 0 / 0.08), 0 4px 10px -5px rgb(0 0 0 / 0.05)",
    duration: 0.2,
    ease: "power2.out",
  });
}

export async function cardHoverOut(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.to(el, {
    y: 0,
    boxShadow:
      "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)",
    duration: 0.2,
    ease: "power2.out",
  });
}

export async function focusRingIn(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.to(el, {
    scale: 1.015,
    duration: 0.15,
    ease: "power2.out",
  });
}

export async function focusRingOut(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.to(el, {
    scale: 1,
    duration: 0.15,
    ease: "power2.out",
  });
}

export async function slideInFromLeft(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.fromTo(
    el,
    { opacity: 0, x: -20 },
    { opacity: 1, x: 0, duration: 0.3, ease: "power2.out" }
  );
}

export async function underlineIn(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.to(el, { backgroundSize: "100% 1px", duration: 0.2, ease: "power2.out" });
}

export async function underlineOut(el: Element): Promise<void> {
  const gsap = await getGsap();
  gsap.to(el, { backgroundSize: "0% 1px", duration: 0.2, ease: "power2.out" });
}
