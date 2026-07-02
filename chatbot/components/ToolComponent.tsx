import { ChevronDown, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

export default function ToolComponent({
  tool_name,
  content,
  status
}: {
  tool_name: string;
  content: string;
  status: string;
}) {
  const [open, setOpen] = useState(false);

  const badgeConfig = useMemo(() => {
    switch (tool_name) {
      case "retrieve_docs":
        return {
          label: "Retrieval",
          className:
            "bg-cyan-500/10 text-cyan-300 border border-cyan-500/20",
        };

      case "highlight_components":
        return {
          label: "Visualization",
          className:
            "bg-green-500/10 text-green-300 border border-green-500/20",
        };

      case "calculator":
        return {
          label: "Computation",
          className:
            "bg-purple-500/10 text-purple-300 border border-purple-500/20",
        };

      default:
        return {
          label: "Tool",
          className:
            "bg-slate-500/10 text-slate-300 border border-slate-500/20",
        };
    }
  }, [tool_name]);

  const statusColor =
    status === "completed"
      ? "text-green-300 bg-green-500/10"
      : status === "error"
        ? "text-red-300 bg-red-500/10"
        : "text-yellow-300 bg-yellow-500/10";
  return (
    <div
      className="
        my-2
        overflow-hidden
        rounded-xl
        border border-cyan-500/20
        bg-white/[0.04]
        shadow-lg
        backdrop-blur-xl
      "
    >
      {/* Header */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="
          flex w-full items-center justify-between
          px-4 py-3
          transition-all duration-200
          hover:bg-cyan-500/10
          cursor-pointer
          select-none
        "
      >
        <div className="flex items-center gap-2">
          {open ? (
            <ChevronDown className="h-4 w-4 text-cyan-300" />
          ) : (
            <ChevronRight className="h-4 w-4 text-cyan-300" />
          )}

          <span className="font-medium text-cyan-200">
            Using {tool_name}
          </span>
          <span
            className={`
              rounded-full px-2 py-0.5 text-xs
              ${badgeConfig.className}
            `}
          >
            {badgeConfig.label}
          </span>
        </div>


        <span
          className={`
              rounded-full px-2 py-0.5 text-xs
              ${statusColor}
            `}
        >
          {status}
        </span>
      </button>

      {/* Content */}
      <div
        className={`
          overflow-hidden
          transition-all duration-300 ease-in-out
          ${open ? "max-h-[500px]" : "max-h-0"}
        `}
      >
        <div
          className="
            border-t border-cyan-500/10
            bg-black/20
            px-4 py-3
            max-h-[400px]
            overflow-y-auto
          "
        >
          <pre
            className="
              whitespace-pre-wrap
              overflow-x-auto
              break-words
              text-sm
              font-mono
              leading-relaxed
              text-zinc-300
            "
          >
            {content}
          </pre>
        </div>
      </div>
    </div>
  );
}