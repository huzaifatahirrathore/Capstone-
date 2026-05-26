import { ProgressBar } from "../common/ProgressBar";
const STATUS_STYLES = {
  Active: {
    dot: "bg-emerald-500",
    text: "text-emerald-700",
    bg: "bg-emerald-50",
    label: "Active",
  },
  Pending: {
    dot: "bg-amber-400",
    text: "text-amber-700",
    bg: "bg-amber-50",
    label: "Pending",
  },
  Completed: {
    dot: "bg-[#008080]",
    text: "text-[#008080]",
    bg: "bg-[#008080]/10",
    label: "Completed",
  },
};

export function ProjectCard({ project, selected, onClick }) {
  const st = STATUS_STYLES[project.status];
  return (
    <button
      onClick={onClick}
      className={`w-full text-left bg-[#F9F6F0] rounded-xl p-3.5 border transition-all duration-200 hover:shadow-md group ${
        selected
          ? "border-[#008080] shadow-md ring-1 ring-[#008080]/20"
          : "border-[#E5DDD0] hover:border-[#C4B8A8]"
      }`}
    >
      <div className="flex gap-3">
        <div className="shrink-0 w-[72px] h-[72px] rounded-lg overflow-hidden bg-[#D6CDBF]">
          <img
            src={project.thumb}
            alt={project.name}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-0.5">
            <p className="text-[#2C2420] text-[0.82rem] font-semibold leading-snug line-clamp-2">
              {project.name}
            </p>
            <span
              className={`shrink-0 inline-flex items-center gap-1 text-[0.62rem] font-semibold px-2 py-0.5 rounded-full ${st.bg} ${st.text}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
              {st.label}
            </span>
          </div>

          <p className="text-[#8C7B68] text-[0.68rem] mb-2">
            {project.region} ·{" "}
            <span className="font-semibold text-[#5C4A38]">
              {project.hectares} ha
            </span>
          </p>

          <div className="space-y-1">
            <div className="flex justify-between items-center">
              <span className="text-[#8C7B68] text-[0.62rem]">
                Goal Achievement
              </span>
              <span className="text-[0.65rem] font-bold text-[#008080]">
                {project.goalPct}%
              </span>
            </div>
            <ProgressBar pct={project.goalPct} />
          </div>
        </div>
      </div>

      {project.verified && (
        <div className="mt-3 pt-3 border-t border-[#EDE6DB]">
          <span className="inline-flex items-center gap-1.5 bg-[#008080]/10 text-[#008080] text-[0.62rem] font-semibold px-3 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-[#008080] animate-pulse" />
            Blockchain Verified
          </span>
        </div>
      )}
    </button>
  );
}
