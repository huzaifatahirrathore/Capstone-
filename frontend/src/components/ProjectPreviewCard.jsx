import { ArrowRightIcon, CheckCircleIcon } from "../common/Icons";
import { ProgressBar } from "../common/ProgressBar";

const STATUS_STYLES = {
  Active:    { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50"   },
  Pending:   { dot: "bg-amber-400",   text: "text-amber-700",   bg: "bg-amber-50"     },
  Completed: { dot: "bg-[#008080]",   text: "text-[#008080]",   bg: "bg-[#008080]/10" },
};

const REQUIRED = ["name", "region", "sponsor", "status", "hectares"];

export function ProjectPreviewCard({ form, onContinue }) {
  const filled    = REQUIRED.filter(f => form[f] && String(form[f]).trim() !== "").length;
  const pct       = Math.round((filled / REQUIRED.length) * 100);
  const canSubmit = filled === REQUIRED.length;
  const st        = STATUS_STYLES[form.status] ?? STATUS_STYLES.Pending;

  return (
    <div className="w-72 shrink-0 bg-[#F9F6F0] rounded-2xl border border-[#D6CDBF] shadow-sm flex flex-col overflow-hidden">

      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-[#E5DDD0]">
        <p className="text-[#2C2420] text-sm font-bold mb-0.5">Card Preview</p>
        <p className="text-[#8C7B68] text-[0.68rem] leading-relaxed">
          Live preview of how this project will appear on the dashboard.
        </p>
      </div>

      {/* Preview card */}
      <div className="px-4 py-4">
        <div className="bg-white rounded-xl p-3.5 border border-[#E5DDD0] shadow-sm">
          <div className="flex gap-3">
            {/* Thumbnail */}
            <div className="shrink-0 w-[72px] h-[72px] rounded-lg overflow-hidden bg-[#D6CDBF] flex items-center justify-center">
              {form.thumb
                ? <img src={form.thumb} alt="thumb" className="w-full h-full object-cover" />
                : <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#A3A090" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              }
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2 mb-0.5">
                <p className="text-[#2C2420] text-[0.82rem] font-semibold leading-snug line-clamp-2">
                  {form.name || <span className="text-[#C4B8A8]">Project Name</span>}
                </p>
                {form.status && (
                  <span className={`shrink-0 inline-flex items-center gap-1 text-[0.62rem] font-semibold px-2 py-0.5 rounded-full ${st.bg} ${st.text}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${st.dot}`} />
                    {form.status}
                  </span>
                )}
              </div>
              <p className="text-[#8C7B68] text-[0.68rem] mb-2">
                {form.region || "Region"} ·{" "}
                <span className="font-semibold text-[#5C4A38]">
                  {form.hectares ? `${form.hectares} ha` : "— ha"}
                </span>
              </p>
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <span className="text-[#8C7B68] text-[0.62rem]">Goal Achievement</span>
                  <span className="text-[0.65rem] font-bold text-[#008080]">{form.goalPct}%</span>
                </div>
                <ProgressBar pct={form.goalPct} />
              </div>
            </div>
          </div>

          {form.verified && (
            <div className="mt-3 pt-3 border-t border-[#EDE6DB]">
              <span className="inline-flex items-center gap-1.5 bg-[#008080]/10 text-[#008080] text-[0.62rem] font-semibold px-3 py-1 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-[#008080] animate-pulse" />
                Blockchain Verified
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Completion tracker */}
      <div className="flex-1 px-5 py-3 space-y-3">
        <div className="flex items-center justify-between mb-1">
          <p className="text-[#8C7B68] text-[0.62rem] font-bold uppercase tracking-widest">Completion</p>
          <span className="text-[0.68rem] font-bold text-[#008080]">{pct}%</span>
        </div>
        <div className="w-full h-1.5 bg-[#E5DDD0] rounded-full overflow-hidden">
          <div className="h-full bg-[#008080] rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
        </div>

        <div className="space-y-2 pt-1">
          {[
            { label: "Project Name",   key: "name"     },
            { label: "Region",         key: "region"   },
            { label: "Sponsor",        key: "sponsor"  },
            { label: "Status",         key: "status"   },
            { label: "Hectares",       key: "hectares" },
          ].map(({ label, key }) => {
            const ok = Boolean(form[key] && String(form[key]).trim() !== "");
            return (
              <div key={key} className="flex items-center gap-2.5">
                <span className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 ${ok ? "bg-[#008080]/15 text-[#008080]" : "bg-[#E5DDD0] text-[#B0A090]"}`}>
                  {ok
                    ? <CheckCircleIcon size={10} />
                    : <span className="w-1.5 h-1.5 rounded-full bg-[#C4B8A8]" />
                  }
                </span>
                <span className={`text-[0.68rem] ${ok ? "text-[#4A6B65]" : "text-[#B0A090]"}`}>{label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Action */}
      <div className="shrink-0 px-5 py-4 border-t border-[#E5DDD0]">
        <button
          onClick={onContinue}
          disabled={!canSubmit}
          className="w-full bg-[#008080] hover:bg-[#006666] disabled:opacity-40 disabled:cursor-not-allowed text-white text-[0.78rem] font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors duration-200 shadow-sm"
        >
          Continue to Boundary
          <ArrowRightIcon size={14} />
        </button>
        {!canSubmit && (
          <p className="text-center text-[#B0A090] text-[0.62rem] mt-2">
            Fill all required fields to continue
          </p>
        )}
      </div>
    </div>
  );
}
