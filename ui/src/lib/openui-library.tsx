"use client";

import * as React from "react";
import { defineComponent, createLibrary } from "@openuidev/react-lang";
import { z } from "zod";
import { StatusPill } from "@/components/ui/StatusPill";
import { fadeUpIn } from "@/lib/animations";
import type { ProgressEvent } from "@/lib/types";

function agentColor(agent: string): string {
  if (agent === "Scout") return "text-blue-700";
  if (agent === "Strategist") return "text-accent";
  if (agent.startsWith("Architect")) return "text-amber-700";
  return "text-ink-muted";
}

const AgentEvent = defineComponent({
  name: "AgentEvent",
  description:
    "One progress event from a campaign agent. Args: agent name, status, detail text.",
  props: z.object({
    agent: z.string().describe("Agent name, e.g. Scout, Architect[water], Strategist"),
    status: z
      .enum(["started", "tool_call", "done", "failed"])
      .describe("Event status"),
    detail: z.string().describe("Human-readable detail of what the agent is doing"),
  }),
  component: ({ props }) => {
    const ref = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => {
      if (ref.current) fadeUpIn(ref.current);
    }, []);
    return (
      <div
        ref={ref}
        className="flex items-start gap-3 py-3 border-b border-border/50 opacity-0"
      >
        <span
          className={`text-sm font-semibold w-36 shrink-0 ${agentColor(props.agent)}`}
        >
          {props.agent}
        </span>
        <StatusPill status={props.status as ProgressEvent["status"]} />
        <span className="text-sm text-ink-muted leading-5">{props.detail}</span>
      </div>
    );
  },
});

const RunSummary = defineComponent({
  name: "RunSummary",
  description:
    "Completion banner shown when the slate is finalized. Args: message text.",
  props: z.object({
    message: z.string().describe("Completion message"),
  }),
  component: ({ props }) => {
    const ref = React.useRef<HTMLDivElement>(null);
    React.useEffect(() => {
      if (ref.current) fadeUpIn(ref.current);
    }, []);
    return (
      <div
        ref={ref}
        className="mt-6 rounded-lg bg-accent-light border border-accent/20 px-5 py-4 opacity-0"
      >
        <p className="text-sm font-medium text-accent">{props.message}</p>
      </div>
    );
  },
});

const Timeline = defineComponent({
  name: "Timeline",
  description:
    "Root container: a vertical timeline of agent progress events, optionally ending with a RunSummary.",
  props: z.object({
    children: z.array(z.union([AgentEvent.ref, RunSummary.ref])),
  }),
  component: ({ props, renderNode }) => (
    <div className="space-y-0" aria-live="polite" aria-label="Agent progress">
      {(props.children as unknown[]).map((child, i) => (
        <React.Fragment key={i}>{renderNode(child)}</React.Fragment>
      ))}
    </div>
  ),
});

export const progressLibrary = createLibrary({
  components: [Timeline, AgentEvent, RunSummary],
  root: "Timeline",
});
