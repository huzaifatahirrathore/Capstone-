import { useState } from "react";
import { GpsIcon, ArrowRightIcon } from "../common/Icons";

function MapPreview({ points }) {
  /* Map lat/lng → SVG viewport (440×460) for the France bounding box:
     lat: 42 (bottom=420) → 51 (top=40),  lng: -5 (left=60) → 8 (right=400) */
  const toSvg = (lat, lng) => ({
    x: 60 + ((lng - -5) / 13) * 340,
    y: 420 - ((lat - 42) / 9) * 380,
  });

  const plotted = points
    .filter((p) => p.lat !== "" && p.lng !== "")
    .map((p) => ({ ...toSvg(parseFloat(p.lat), parseFloat(p.lng)), raw: p }));

  const polyPts = plotted.map((p) => `${p.x},${p.y}`).join(" ");

  return (
    <svg viewBox="0 0 440 460" className="w-full h-full">
      <path
        d="M 155 55 L 200 42 L 255 48 L 300 65 L 338 95 L 355 135 L 358 180
           L 348 215 L 355 250 L 348 285 L 330 318 L 310 345 L 295 375 L 280 405
           L 258 420 L 230 428 L 200 425 L 170 415 L 148 395 L 130 368 L 118 338
           L 110 305 L 105 268 L 108 232 L 100 198 L 92 165 L 88 130 L 100 100
           L 120 75 Z"
        fill="#E8F4F0"
        stroke="#C8DDD8"
        strokeWidth="1.5"
      />

      {[
        "80,175 60,168 45,175 40,190 48,205 68,210 88,205 98,192 95,178",
        "145,135 125,128 108,135 105,152 115,165 135,168 155,162 162,148 158,135",
        "190,225 168,215 150,222 148,242 158,260 178,265 200,260 210,244 205,228",
        "320,165 308,158 298,165 297,182 306,194 320,197 332,192 337,178 332,166",
        "290,360 268,350 252,358 250,378 262,395 284,400 305,394 315,378 308,360",
        "230,340 208,328 192,336 190,358 203,376 226,380 248,373 256,354 246,336",
        "195,340 175,330 160,340 155,360 165,385 185,395 205,390 220,375 225,355 215,340",
      ].map((pts, i) => (
        <polygon
          key={i}
          points={pts}
          fill="#D6E8E4"
          fillOpacity="0.55"
          stroke="#B8CEC9"
          strokeWidth="0.8"
        />
      ))}

      {plotted.length >= 3 && (
        <polygon
          points={polyPts}
          fill="#00E6E6"
          fillOpacity="0.22"
          stroke="#008080"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      )}

      {plotted.length === 2 && (
        <line
          x1={plotted[0].x}
          y1={plotted[0].y}
          x2={plotted[1].x}
          y2={plotted[1].y}
          stroke="#008080"
          strokeWidth="2"
          strokeDasharray="5 3"
        />
      )}

      {/* Point markers */}
      {plotted.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r="6" fill="#008080" fillOpacity="0.15" />
          <circle
            cx={p.x}
            cy={p.y}
            r="3.5"
            fill="white"
            stroke="#008080"
            strokeWidth="2"
          />
          <text
            x={p.x + 7}
            y={p.y + 4}
            fontSize="7.5"
            fontWeight="700"
            fill="#006060"
          >
            {i + 1}
          </text>
        </g>
      ))}

      {plotted.length === 0 && (
        <>
          <rect
            x="100"
            y="200"
            width="240"
            height="36"
            rx="8"
            fill="white"
            fillOpacity="0.7"
          />
          <text
            x="220"
            y="221"
            textAnchor="middle"
            fontSize="9"
            fill="#8CAAA6"
            fontWeight="500"
          >
            Add GPS coordinates to plot boundary
          </text>
        </>
      )}

      <g transform="translate(405,55)">
        <circle
          cx="0"
          cy="0"
          r="14"
          fill="white"
          stroke="#C8DDD8"
          strokeWidth="1"
        />
        <text
          x="0"
          y="-4"
          textAnchor="middle"
          fontSize="7"
          fontWeight="700"
          fill="#5C7C78"
        >
          N
        </text>
        <line
          x1="0"
          y1="1"
          x2="0"
          y2="-2"
          stroke="#008080"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </g>

      <g transform="translate(22,430)">
        <line
          x1="0"
          y1="0"
          x2="60"
          y2="0"
          stroke="#8CAAA6"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <line x1="0" y1="-3" x2="0" y2="3" stroke="#8CAAA6" strokeWidth="1.5" />
        <line
          x1="60"
          y1="-3"
          x2="60"
          y2="3"
          stroke="#8CAAA6"
          strokeWidth="1.5"
        />
        <text x="30" y="-6" textAnchor="middle" fontSize="7" fill="#8CAAA6">
          200 km
        </text>
      </g>
    </svg>
  );
}

const EMPTY_POINT = () => ({ id: Date.now(), lat: "", lng: "", label: "" });

export function BoundaryMapCard({ points, onChange }) {
  const addPoint = () => onChange([...points, EMPTY_POINT()]);

  const updatePoint = (id, field, val) =>
    onChange(points.map((p) => (p.id === id ? { ...p, [field]: val } : p)));

  const removePoint = (id) => onChange(points.filter((p) => p.id !== id));

  const validCount = points.filter((p) => p.lat !== "" && p.lng !== "").length;

  return (
    <div className="flex-1 bg-[#F9F6F0] rounded-2xl border border-[#D6CDBF] overflow-hidden flex flex-col shadow-sm min-h-0">
      <div className="shrink-0 px-5 py-3.5 border-b border-[#E5DDD0] flex items-center justify-between">
        <div>
          <p className="text-[#2C2420] text-sm font-bold">GPS Coordinates</p>
          <p className="text-[#8C7B68] text-[0.65rem]">
            Enter coordinate pairs to define the plantation boundary
          </p>
        </div>
        {validCount >= 3 && (
          <span className="inline-flex items-center gap-1.5 bg-[#008080]/10 text-[#008080] text-[0.62rem] font-semibold px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-[#008080] animate-pulse" />
            {validCount} points plotted
          </span>
        )}
      </div>

      <div className="flex-1 flex overflow-hidden min-h-0">
        <div className="w-72 shrink-0 flex flex-col border-r border-[#E5DDD0] overflow-hidden">
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            <div className="grid grid-cols-[1fr_1fr_auto] gap-2 px-1 mb-1">
              <span className="text-[#8C7B68] text-[0.6rem] font-bold uppercase tracking-wider">
                Latitude
              </span>
              <span className="text-[#8C7B68] text-[0.6rem] font-bold uppercase tracking-wider">
                Longitude
              </span>
              <span className="w-6" />
            </div>

            {points.map((pt, idx) => (
              <div key={pt.id} className="space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-[#008080] text-white text-[0.6rem] font-bold flex items-center justify-center shrink-0">
                    {idx + 1}
                  </span>
                  <input
                    value={pt.label}
                    onChange={(e) =>
                      updatePoint(pt.id, "label", e.target.value)
                    }
                    placeholder={`Point ${idx + 1} label (optional)`}
                    className="flex-1 bg-white border border-[#D6CDBF] rounded-lg px-2.5 py-1.5 text-[0.7rem] text-[#2C2420] placeholder:text-[#C4B8A8] outline-none focus:border-[#A3431F] transition-colors"
                  />
                  <button
                    onClick={() => removePoint(pt.id)}
                    className="w-6 h-6 rounded-md flex items-center justify-center text-[#C4B8A8] hover:text-red-400 hover:bg-red-50 transition-colors shrink-0"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      width="12"
                      height="12"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                    >
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 pl-7">
                  <div>
                    <input
                      value={pt.lat}
                      onChange={(e) =>
                        updatePoint(pt.id, "lat", e.target.value)
                      }
                      placeholder="44.8378"
                      className="w-full bg-white border border-[#D6CDBF] rounded-lg px-2.5 py-1.5 text-[0.7rem] text-[#2C2420] placeholder:text-[#C4B8A8] outline-none focus:border-[#008080] transition-colors font-mono"
                    />
                    <p className="text-[#B0A090] text-[0.58rem] mt-0.5 pl-0.5">
                      ° N
                    </p>
                  </div>
                  <div>
                    <input
                      value={pt.lng}
                      onChange={(e) =>
                        updatePoint(pt.id, "lng", e.target.value)
                      }
                      placeholder="-0.5792"
                      className="w-full bg-white border border-[#D6CDBF] rounded-lg px-2.5 py-1.5 text-[0.7rem] text-[#2C2420] placeholder:text-[#C4B8A8] outline-none focus:border-[#008080] transition-colors font-mono"
                    />
                    <p className="text-[#B0A090] text-[0.58rem] mt-0.5 pl-0.5">
                      ° W / E
                    </p>
                  </div>
                </div>
              </div>
            ))}

            <button
              onClick={addPoint}
              className="w-full flex items-center justify-center gap-2 border-2 border-dashed border-[#C8DDD8] text-[#5C7C78] text-[0.72rem] font-semibold py-2.5 rounded-xl hover:border-[#008080] hover:text-[#008080] hover:bg-[#EAF3F1] transition-all duration-150"
            >
              <GpsIcon size={13} />
              Add Coordinate Point
            </button>
          </div>

          <div className="shrink-0 px-4 py-3 border-t border-[#E5DDD0] bg-[#F9F6F0]">
            <p className="text-[#8C7B68] text-[0.62rem] leading-relaxed">
              Add at least{" "}
              <span className="font-semibold text-[#008080]">3 points</span> to
              form a closed polygon. Points are connected in order.
            </p>
          </div>
        </div>

        <div className="flex-1 bg-[#EAF3F1] flex items-center justify-center p-4 min-w-0">
          <MapPreview points={points} />
        </div>
      </div>
    </div>
  );
}
