const STAGES = [
  { label: "Image Ingestion",          pct: 100 },
  { label: "Preprocessing",            pct: 100 },
  { label: "Neural Net Inference",     pct: 100 },
  { label: "Canopy Detection",         pct: 100 },
  { label: "Report Generation",        pct:  96 },
];

export function ScanTimeline({ progress = 96, running = false }) {
  /* Map overall 0-100 to which stage we're in */
  const stageWidth = 100 / STAGES.length;

  return (
    <div className="bg-[#37393D] rounded-xl px-5 py-4 border border-[#404348]">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {running && (
            <span className="w-2 h-2 rounded-full bg-[#00E6E6] animate-ping" />
          )}
          <span className="text-[#9CA3AF] text-[0.7rem] font-bold uppercase tracking-widest">
            Scanning Progress
          </span>
        </div>
        <span className="text-[#00E6E6] text-sm font-bold tabular-nums">{progress}%</span>
      </div>

      {/* Stage nodes track */}
      <div className="relative">
        {/* Background rail */}
        <div className="absolute top-[11px] left-0 right-0 h-0.5 bg-[#4A4D52] rounded-full" />

        {/* Filled rail */}
        <div
          className="absolute top-[11px] left-0 h-0.5 rounded-full transition-all duration-700"
          style={{
            width: `${progress}%`,
            background: "linear-gradient(90deg, #008080 0%, #00E6E6 100%)",
            boxShadow: "0 0 8px #00E6E6aa",
          }}
        />

        {/* Stage markers */}
        <div className="relative flex justify-between">
          {STAGES.map((stage, i) => {
            const stagePct = (i / (STAGES.length - 1)) * 100;
            const done   = progress >= stagePct + 0.1;
            const active = Math.abs(progress - stagePct) < stageWidth / 2 && !done;

            return (
              <div key={stage.label} className="flex flex-col items-center gap-1.5" style={{ width: "20%" }}>
                {/* Node */}
                <div
                  className={`
                    w-[22px] h-[22px] rounded-full border-2 flex items-center justify-center z-10 transition-all duration-300
                    ${done
                      ? "bg-[#008080] border-[#00E6E6] shadow-[0_0_8px_#00E6E6aa]"
                      : active
                        ? "bg-[#2C2D30] border-[#00E6E6] shadow-[0_0_12px_#00E6E6]"
                        : "bg-[#2C2D30] border-[#4A4D52]"
                    }
                  `}
                >
                  {done && (
                    <svg viewBox="0 0 12 12" width="10" height="10" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                      <polyline points="2 6 5 9 10 3" />
                    </svg>
                  )}
                  {active && (
                    <span className="w-2 h-2 rounded-full bg-[#00E6E6] animate-pulse" />
                  )}
                </div>

                {/* Label */}
                <span className={`text-center text-[0.57rem] font-medium leading-tight w-full px-0.5 ${done ? "text-[#9CA3AF]" : active ? "text-[#00E6E6]" : "text-[#4B5563]"}`}>
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
