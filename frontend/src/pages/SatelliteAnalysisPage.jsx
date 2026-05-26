import { useState } from "react";
import { TopNav }         from "../components/TopNav";
import { FileDropzone }   from "../components/FileDropzone";
import { ScanTimeline }   from "../components/ScanTimeline";
import { CanopyViewport } from "../components/CanopyViewport";
import { MetricWidget }   from "../components/MetricWidget";
import { ZapIcon, TrendUpIcon, LeafIcon, CpuIcon, ChevronIcon } from "../common/Icons";

const BASELINE_DATES = ["May 2021", "Jun 2022", "Sep 2023", "Jan 2025", "May 2026"];

const CONCLUSION_POINTS = [
  "Significant biomass density increase detected across primary zone",
  "Estimated 4.2 hectares transitioned to active canopy cover",
  "Mean NDVI value rose from 0.31 → 0.67, indicating dense green vegetation",
  "3 distinct reforested clusters identified with ≥85% confidence threshold",
  "Southern boundary shows emergent shrub layer consistent with early succession",
  "No deforestation activity detected within or adjacent to the project polygon",
  "Canopy closure rate exceeds baseline projection by approximately 18%",
];

export default function SatelliteAnalysisPage() {
  const [baseline,  setBaseline]  = useState("May 2021");
  const [compare,   setCompare]   = useState("May 2026");
  const [beforeUrl, setBeforeUrl] = useState(null);
  const [afterUrl,  setAfterUrl]  = useState(null);
  const [running,   setRunning]   = useState(false);
  const [done,      setDone]      = useState(true);   // pre-filled so the output is visible

  const handleRun = () => {
    if (running) return;
    setDone(false);
    setRunning(true);
    setTimeout(() => { setRunning(false); setDone(true); }, 2400);
  };

  return (
    <div className="flex flex-col h-screen bg-[#2C2D30] overflow-hidden font-sans">

      {/* ── Top Nav (shared terracotta) ── */}
      <TopNav subtitle="Enterprise" title="AI Satellite Analysis" />

      {/* ── Scrollable body ── */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6">

        {/* ── Page header ── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-white text-xl font-bold tracking-tight leading-none">
              Aquitaine Carbon Sink
            </h1>
            <p className="text-[#6B7280] text-sm mt-1">
              AI-powered multi-temporal canopy change detection
            </p>
          </div>

          {/* Baseline date toggles */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-[#37393D] border border-[#404348] rounded-xl px-3 py-2">
              <span className="text-[#6B7280] text-[0.65rem] font-bold uppercase tracking-wider shrink-0">Baseline</span>
              <div className="relative">
                <select
                  value={baseline}
                  onChange={e => setBaseline(e.target.value)}
                  className="appearance-none bg-transparent text-[#9CA3AF] text-sm font-semibold pr-5 outline-none cursor-pointer"
                >
                  {BASELINE_DATES.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <span className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-[#6B7280]"><ChevronIcon /></span>
              </div>
            </div>

            <span className="text-[#4B5563] font-bold text-sm">→</span>

            <div className="flex items-center gap-2 bg-[#37393D] border border-[#00E6E6]/30 rounded-xl px-3 py-2">
              <span className="text-[#00E6E6]/60 text-[0.65rem] font-bold uppercase tracking-wider shrink-0">Compare</span>
              <div className="relative">
                <select
                  value={compare}
                  onChange={e => setCompare(e.target.value)}
                  className="appearance-none bg-transparent text-[#00E6E6] text-sm font-semibold pr-5 outline-none cursor-pointer"
                >
                  {BASELINE_DATES.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
                <span className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-[#00E6E6]/60"><ChevronIcon /></span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Section 1: Upload + Timeline ── */}
        <div className="bg-[#37393D] rounded-2xl border border-[#404348] p-5 space-y-4">
          <p className="text-[#9CA3AF] text-[0.65rem] font-bold uppercase tracking-widest">
            Input Imagery
          </p>

          {/* Two dropzones */}
          <div className="flex gap-4" style={{ height: "190px" }}>
            <FileDropzone
              label="Before Image"
              tag={baseline}
              onFile={(_, url) => setBeforeUrl(url)}
            />
            <FileDropzone
              label="After Image"
              tag={compare}
              onFile={(_, url) => setAfterUrl(url)}
            />
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={running}
            className="w-full flex items-center justify-center gap-2.5 bg-[#008080] hover:bg-[#006666] disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold text-sm py-3.5 rounded-xl transition-colors duration-200 shadow-lg"
            style={{ boxShadow: running ? "none" : "0 0 20px rgba(0,128,128,0.35)" }}
          >
            {running ? (
              <>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" className="animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Analysing…
              </>
            ) : (
              <>
                <ZapIcon size={15} />
                Run AI Canopy Analysis
              </>
            )}
          </button>

          {/* Timeline */}
          <ScanTimeline progress={96} running={running} />
        </div>

        {/* ── Section 2: AI Output Viewport ── */}
        {done && (
          <div>
            <p className="text-[#6B7280] text-[0.65rem] font-bold uppercase tracking-widest mb-3">
              AI Generated Output
            </p>
            <CanopyViewport imageUrl={afterUrl} />
          </div>
        )}

        {/* ── Section 3: Data & Conclusion Grid ── */}
        {done && (
          <div>
            <p className="text-[#6B7280] text-[0.65rem] font-bold uppercase tracking-widest mb-3">
              Analysis Results
            </p>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">

              {/* Left — Conclusion panel (7 cols) */}
              <div className="md:col-span-7 bg-[#37393D] rounded-2xl border border-[#404348] p-5">
                <div className="flex items-center gap-2 mb-4">
                  <span className="w-2 h-2 rounded-full bg-[#00E6E6]" />
                  <p className="text-white text-sm font-bold">Conclusion</p>
                  <span className="ml-auto text-[#4B5563] text-[0.6rem] font-mono">
                    Model: EcoNet-v3 · {new Date().toLocaleDateString()}
                  </span>
                </div>

                <ul className="space-y-3">
                  {CONCLUSION_POINTS.map((point, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-[#008080] shrink-0" />
                      <p className="text-[#D1D5DB] text-sm leading-relaxed">{point}</p>
                    </li>
                  ))}
                </ul>

                {/* Raw API output strip */}
                <div className="mt-4 pt-4 border-t border-[#404348]">
                  <p className="text-[#4B5563] text-[0.6rem] font-bold uppercase tracking-widest mb-2">
                    Raw API Response
                  </p>
                  <pre className="bg-[#2C2D30] text-[#00E6E6] text-[0.58rem] rounded-lg px-4 py-3 overflow-x-auto font-mono leading-relaxed">
{`{
  "model":       "ecoledger-canopy-v3",
  "confidence":  0.96,
  "zones":       3,
  "area_ha":     4.2,
  "ndvi_delta":  "+0.36",
  "carbon_tons": 8500,
  "canopy_pct":  "+45%"
}`}
                  </pre>
                </div>
              </div>

              {/* Right — Metrics (5 cols) */}
              <div className="md:col-span-5 flex flex-col gap-4">

                <MetricWidget
                  icon={TrendUpIcon}
                  label="Canopy Growth"
                  value="+45%"
                  sub="vs. May 2021 baseline · 3 detected zones"
                  variant="teal"
                />

                <MetricWidget
                  icon={LeafIcon}
                  label="Estimated Carbon Sequestered"
                  value="8,500"
                  sub="Metric tons CO₂ equivalent · annualised"
                  variant="default"
                />

                {/* AI Confidence Score — prominent badge style */}
                <div className="flex-1 bg-[#00E6E6]/10 border border-[#00E6E6]/30 rounded-2xl p-5 flex flex-col justify-between"
                  style={{ boxShadow: "0 0 24px rgba(0,230,230,0.08)" }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[#00E6E6]/70 text-[0.65rem] font-bold uppercase tracking-widest">
                      AI Confidence Score
                    </span>
                    <CpuIcon size={15} />
                  </div>

                  {/* Score ring */}
                  <div className="flex items-center justify-center py-4">
                    <div className="relative w-28 h-28">
                      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                        <circle cx="50" cy="50" r="42" fill="none" stroke="#1a3d3d" strokeWidth="10" />
                        <circle
                          cx="50" cy="50" r="42"
                          fill="none"
                          stroke="#00E6E6"
                          strokeWidth="10"
                          strokeLinecap="round"
                          strokeDasharray={`${2 * Math.PI * 42 * 0.96} ${2 * Math.PI * 42}`}
                          style={{ filter: "drop-shadow(0 0 6px #00E6E6)" }}
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-[#00E6E6] text-3xl font-black leading-none">96%</span>
                        <span className="text-[#00E6E6]/50 text-[0.6rem] mt-1">confidence</span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    {[
                      { label: "Precision",   val: "97.2%" },
                      { label: "Recall",      val: "94.8%" },
                      { label: "F1 Score",    val: "0.96"  },
                    ].map(({ label, val }) => (
                      <div key={label} className="flex items-center justify-between">
                        <span className="text-[#00E6E6]/50 text-[0.62rem]">{label}</span>
                        <span className="text-[#00E6E6] text-[0.7rem] font-bold tabular-nums">{val}</span>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            </div>
          </div>
        )}

        {/* Bottom padding */}
        <div className="h-4" />
      </div>
    </div>
  );
}
