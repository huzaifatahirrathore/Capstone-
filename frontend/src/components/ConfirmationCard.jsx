import { ArrowRightIcon, ArrowLeftIcon, CheckCircleIcon } from "../common/Icons";

const ZONE_STATS = [
  { label: "Vertices",     value: "10"          },
  { label: "Perimeter",    value: "~318 km"      },
  { label: "Area",         value: "52.7 M ha"    },
  { label: "CRS",          value: "EPSG:4326"    },
  { label: "Projection",   value: "WGS 84"       },
  { label: "Coordinates",  value: "GeoJSON"      },
];

export function ConfirmationCard({ onBack, onContinue }) {
  return (
    <div className="w-72 shrink-0 bg-[#F9F6F0] rounded-2xl border border-[#D6CDBF] shadow-sm flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-[#E5DDD0]">
        <p className="text-[#2C2420] text-sm font-bold mb-0.5">Zone Boundary</p>
        <p className="text-[#8C7B68] text-[0.68rem] leading-relaxed">
          Draw or input the plantation boundary area on the map, then confirm below.
        </p>
      </div>

      {/* Stats */}
      <div className="flex-1 px-5 py-4 space-y-3 overflow-y-auto">
        <p className="text-[#8C7B68] text-[0.62rem] font-bold uppercase tracking-widest">Zone Metadata</p>
        <div className="bg-white rounded-xl border border-[#E5DDD0] divide-y divide-[#F0EBE3]">
          {ZONE_STATS.map(({ label, value }) => (
            <div key={label} className="flex items-center justify-between px-4 py-2.5">
              <span className="text-[#8C7B68] text-[0.68rem]">{label}</span>
              <span className="text-[#2C2420] text-[0.72rem] font-semibold">{value}</span>
            </div>
          ))}
        </div>

        {/* Validation checks */}
        <p className="text-[#8C7B68] text-[0.62rem] font-bold uppercase tracking-widest pt-1">Validation</p>
        <div className="space-y-2">
          {[
            { label: "Polygon is closed",       ok: true  },
            { label: "No self-intersections",   ok: true  },
            { label: "Minimum area met",         ok: true  },
            { label: "GPS coordinates verified", ok: false },
          ].map(({ label, ok }) => (
            <div key={label} className="flex items-center gap-2.5">
              <span
                className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0
                  ${ok ? "bg-[#008080]/15 text-[#008080]" : "bg-amber-100 text-amber-500"}`}
              >
                {ok
                  ? <CheckCircleIcon size={10} />
                  : <span className="text-[0.55rem] font-black">!</span>
                }
              </span>
              <span className={`text-[0.68rem] ${ok ? "text-[#4A6B65]" : "text-amber-700"}`}>
                {label}
              </span>
            </div>
          ))}
        </div>

        {/* GeoJSON preview */}
        <p className="text-[#8C7B68] text-[0.62rem] font-bold uppercase tracking-widest pt-1">GeoJSON Preview</p>
        <pre className="bg-[#2C2D30] text-[#00E6E6] text-[0.58rem] rounded-lg px-3 py-2.5 overflow-x-auto leading-relaxed font-mono">
{`{
  "type": "Polygon",
  "coordinates": [[
    [-0.98, 44.95],
    [-1.42, 44.72],
    [-1.68, 44.18],
    [-0.55, 43.89],
    [ 0.31, 44.42],
    [-0.98, 44.95]
  ]]
}`}
        </pre>
      </div>

      {/* Actions */}
      <div className="shrink-0 px-5 py-4 border-t border-[#E5DDD0] space-y-2.5">
        <button
          onClick={onContinue}
          className="w-full bg-[#008080] hover:bg-[#006666] text-white text-[0.78rem] font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors duration-200 shadow-sm"
        >
          Save &amp; Continue
          <ArrowRightIcon size={14} />
        </button>
        <button
          onClick={onBack}
          className="w-full bg-transparent border border-[#D6CDBF] text-[#5C4A38] text-[0.75rem] font-medium py-2.5 rounded-xl flex items-center justify-center gap-2 hover:bg-[#EDE6DB] transition-colors duration-200"
        >
          <ArrowLeftIcon size={14} />
          Back to Basic Info
        </button>
      </div>
    </div>
  );
}
