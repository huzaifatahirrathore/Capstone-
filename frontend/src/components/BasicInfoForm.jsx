import { ChevronIcon } from "../common/Icons";
import { REGIONS, SPONSORS, STATUSES } from "../data/plantationProjects";

const REGION_OPTIONS = REGIONS.filter((r) => !r.startsWith("All"));
const SPONSOR_OPTIONS = SPONSORS.filter((s) => !s.startsWith("All"));
const STATUS_OPTIONS = STATUSES.filter((s) => !s.startsWith("All"));

function Field({ label, hint, children }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <label className="text-[#2C2420] text-[0.75rem] font-semibold">
          {label}
        </label>
        {hint && <span className="text-[#B0A090] text-[0.62rem]">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function TextInput({ value, onChange, placeholder, mono = false }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full bg-white border border-[#D6CDBF] rounded-xl px-4 py-3 text-sm text-[#2C2420] placeholder:text-[#C4B8A8] outline-none focus:border-[#A3431F] focus:ring-2 focus:ring-[#A3431F]/10 transition-all ${mono ? "font-mono" : ""}`}
    />
  );
}

function SelectInput({ value, onChange, options }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none bg-white border border-[#D6CDBF] rounded-xl px-4 py-3 text-sm text-[#2C2420] outline-none focus:border-[#A3431F] focus:ring-2 focus:ring-[#A3431F]/10 transition-all cursor-pointer pr-10"
      >
        <option value="">Select…</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-[#A3431F]">
        <ChevronIcon />
      </span>
    </div>
  );
}

const STATUS_COLORS = {
  Active: {
    dot: "bg-emerald-500",
    ring: "ring-emerald-200",
    text: "text-emerald-700",
    bg: "bg-emerald-50",
  },
  Pending: {
    dot: "bg-amber-400",
    ring: "ring-amber-200",
    text: "text-amber-700",
    bg: "bg-amber-50",
  },
  Completed: {
    dot: "bg-[#008080]",
    ring: "ring-teal-200",
    text: "text-[#008080]",
    bg: "bg-teal-50",
  },
};

export function BasicInfoForm({ form, onChange }) {
  const set = (field) => (val) => onChange({ ...form, [field]: val });

  return (
    <div className="flex-1 bg-[#F9F6F0] rounded-2xl border border-[#D6CDBF] overflow-hidden flex flex-col shadow-sm min-h-0">
      <div className="shrink-0 px-6 py-4 border-b border-[#E5DDD0]">
        <p className="text-[#2C2420] text-sm font-bold">Project Details</p>
        <p className="text-[#8C7B68] text-[0.65rem] mt-0.5">
          Fill in the core metadata for this plantation project
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="space-y-5">
          <Field label="Project Name" hint="Required">
            <TextInput
              value={form.name}
              onChange={set("name")}
              placeholder="e.g. Aquitaine Carbon Sink"
            />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Region">
              <SelectInput
                value={form.region}
                onChange={set("region")}
                options={REGION_OPTIONS}
              />
            </Field>
            <Field label="Sponsor">
              <SelectInput
                value={form.sponsor}
                onChange={set("sponsor")}
                options={SPONSOR_OPTIONS}
              />
            </Field>
          </div>

          <Field label="Status">
            <div className="flex gap-2.5">
              {STATUS_OPTIONS.map((s) => {
                const c = STATUS_COLORS[s];
                const sel = form.status === s;
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => set("status")(s)}
                    className={`
                      flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-semibold transition-all duration-150
                      ${
                        sel
                          ? `${c.bg} ${c.text} border-current ring-2 ${c.ring}`
                          : "bg-white text-[#8C7B68] border-[#D6CDBF] hover:border-[#C4B8A8]"
                      }
                    `}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${sel ? c.dot : "bg-[#D6CDBF]"}`}
                    />
                    {s}
                  </button>
                );
              })}
            </div>
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Area (Hectares)" hint="e.g. 52.7M">
              <div className="relative">
                <TextInput
                  value={form.hectares}
                  onChange={set("hectares")}
                  placeholder="52.7M"
                  mono
                />
                <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#B0A090] text-[0.68rem] font-medium pointer-events-none">
                  ha
                </span>
              </div>
            </Field>
            <Field label="Goal Achievement" hint={`${form.goalPct}%`}>
              <div className="space-y-2">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={form.goalPct}
                  onChange={(e) => set("goalPct")(Number(e.target.value))}
                  className="w-full accent-[#008080]"
                />
                <div className="w-full h-1.5 bg-[#E5DDD0] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${form.goalPct}%`,
                      background:
                        form.goalPct === 100
                          ? "#008080"
                          : `linear-gradient(90deg, #A3431F ${100 - form.goalPct}%, #008080 100%)`,
                    }}
                  />
                </div>
              </div>
            </Field>
          </div>

          <Field label="Satellite Thumbnail" hint="Image URL">
            <TextInput
              value={form.thumb}
              onChange={set("thumb")}
              placeholder="https://…"
            />
            {form.thumb && (
              <div className="mt-2 w-24 h-16 rounded-xl overflow-hidden border border-[#D6CDBF] bg-[#E5DDD0]">
                <img
                  src={form.thumb}
                  alt="preview"
                  className="w-full h-full object-cover"
                />
              </div>
            )}
          </Field>

          <Field label="Blockchain Verification">
            <button
              type="button"
              onClick={() => set("verified")(!form.verified)}
              className={`
                inline-flex items-center gap-3 px-4 py-3 rounded-xl border text-sm font-semibold transition-all duration-200
                ${
                  form.verified
                    ? "bg-[#008080]/10 text-[#008080] border-[#008080]/30 ring-2 ring-[#008080]/10"
                    : "bg-white text-[#8C7B68] border-[#D6CDBF] hover:border-[#C4B8A8]"
                }
              `}
            >
              <span
                className={`relative inline-flex w-10 h-5 rounded-full transition-colors duration-200 shrink-0 ${form.verified ? "bg-[#008080]" : "bg-[#D6CDBF]"}`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${form.verified ? "translate-x-5" : "translate-x-0.5"}`}
                />
              </span>
              {form.verified ? "Blockchain Verified" : "Not yet verified"}
              {form.verified && (
                <span className="ml-auto text-[0.62rem] bg-[#008080]/15 px-2 py-0.5 rounded-full">
                  On-chain
                </span>
              )}
            </button>
          </Field>
        </div>
      </div>
    </div>
  );
}
