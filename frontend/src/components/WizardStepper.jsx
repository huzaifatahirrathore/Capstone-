import { CheckCircleIcon, ChainIcon, MapPinIcon } from "../common/Icons";

const STEPS = [
  { id: 1, label: "Basic Info",  short: "Project details & metadata",   Icon: (p) => <CheckCircleIcon {...p} /> },
  { id: 2, label: "Boundary",    short: "Define plantation zone",        Icon: (p) => <MapPinIcon {...p} />      },
  { id: 3, label: "Blockchain",  short: "Sign & register on-chain",      Icon: (p) => <ChainIcon {...p} />       },
];

export function WizardStepper({ current = 2 }) {
  return (
    <div className="flex items-stretch rounded-xl overflow-hidden border border-[#D6CDBF] bg-[#F9F6F0] shadow-sm">
      {STEPS.map((step, idx) => {
        const done   = step.id < current;
        const active = step.id === current;
        const upcoming = step.id > current;

        return (
          <div key={step.id} className="flex-1 flex items-stretch">
            {/* Step segment */}
            <div
              className={`
                flex-1 flex items-center gap-3 px-5 py-4 relative
                ${active   ? "bg-[#EFE8DC]"  : "bg-[#F9F6F0]"}
                ${done     ? "opacity-100"   : ""}
                ${upcoming ? "opacity-60"    : ""}
              `}
            >
              {/* Step number / check */}
              <div
                className={`
                  shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                  ${done     ? "bg-[#008080] text-white"                          : ""}
                  ${active   ? "bg-[#A3431F] text-white ring-4 ring-[#A3431F]/20" : ""}
                  ${upcoming ? "bg-[#D6CDBF] text-[#8C7B68]"                      : ""}
                `}
              >
                {done ? <CheckCircleIcon size={15} /> : step.id}
              </div>

              <div className="min-w-0">
                <p
                  className={`text-[0.78rem] font-bold leading-none mb-0.5 truncate
                    ${done ? "text-[#008080]" : active ? "text-[#A3431F]" : "text-[#8C7B68]"}
                  `}
                >
                  {step.label}
                </p>
                <p className="text-[#8C7B68] text-[0.62rem] truncate">{step.short}</p>
              </div>

              {/* Active indicator bar at bottom */}
              {active && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#A3431F] rounded-t" />
              )}
            </div>

            {/* Divider between segments */}
            {idx < STEPS.length - 1 && (
              <div className="w-px self-stretch bg-[#D6CDBF] shrink-0" />
            )}
          </div>
        );
      })}
    </div>
  );
}
