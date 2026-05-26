/* Polygon vertices as % of the image container — drawn to look like detected tree clusters */
const CLUSTERS = [
  {
    /* Main large reforested zone */
    points: "32,28 41,22 52,20 61,25 66,35 63,47 55,55 44,58 34,54 27,44 27,34",
    label: { x: "46", y: "40", text: "Zone A · 3.1 ha" },
  },
  {
    /* Secondary cluster */
    points: "68,42 76,38 82,42 82,52 76,57 68,53",
    label: { x: "75", y: "49", text: "Zone B · 0.8 ha" },
  },
  {
    /* Small tertiary cluster */
    points: "20,60 27,57 33,61 31,68 22,68",
    label: { x: "26", y: "64", text: "Zone C · 0.3 ha" },
  },
];

/* Scan-line animation overlay */
function ScanOverlay() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden rounded-xl">
      {/* Horizontal scan line */}
      <div
        className="absolute left-0 right-0 h-px"
        style={{
          background: "linear-gradient(90deg, transparent 0%, #00E6E6 40%, #00E6E6 60%, transparent 100%)",
          boxShadow: "0 0 12px 2px #00E6E6",
          animation: "scanline 3s linear infinite",
          top: "60%",
          opacity: 0.5,
        }}
      />
      {/* Vignette corners */}
      <div className="absolute inset-0 rounded-xl" style={{
        background: "radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(44,45,48,0.55) 100%)"
      }} />
    </div>
  );
}

export function CanopyViewport({ imageUrl }) {
  const src = imageUrl || "https://images.unsplash.com/photo-1448375240586-882707db888b?w=1200&q=85";

  return (
    <div className="bg-[#37393D] rounded-2xl border border-[#404348] overflow-hidden">
      {/* Viewport header bar */}
      <div className="px-5 py-3 border-b border-[#404348] flex items-center justify-between bg-[#2C2D30]">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-[#00E6E6] shadow-[0_0_8px_#00E6E6] animate-pulse" />
          <span className="text-white text-sm font-bold">AI Output · Canopy Analysis</span>
          <span className="text-[#4B5563] text-[0.65rem]">Aquitaine — May 2026</span>
        </div>
        <div className="flex items-center gap-2">
          {["RGB", "NDVI", "Thermal"].map((mode, i) => (
            <button
              key={mode}
              className={`text-[0.62rem] font-bold px-2.5 py-1 rounded-md transition-colors ${i === 0 ? "bg-[#008080] text-white" : "text-[#6B7280] hover:text-[#9CA3AF] hover:bg-[#37393D]"}`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Image + overlay container */}
      <div className="relative" style={{ paddingBottom: "45%" }}>
        {/* Satellite image */}
        <img
          src={src}
          alt="Satellite canopy analysis"
          className="absolute inset-0 w-full h-full object-cover"
          draggable={false}
        />

        {/* Dark overlay tint */}
        <div className="absolute inset-0 bg-[#0a1a1a]/30" />

        {/* SVG polygon overlay */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ filter: "drop-shadow(0 0 6px #00E6E6)" }}
        >
          {CLUSTERS.map((cluster, i) => (
            <g key={i}>
              {/* Fill */}
              <polygon
                points={cluster.points}
                fill="#00E6E6"
                fillOpacity="0.12"
              />
              {/* Bright border */}
              <polygon
                points={cluster.points}
                fill="none"
                stroke="#00E6E6"
                strokeWidth="0.4"
                strokeLinejoin="round"
              />
              {/* Outer glow ring */}
              <polygon
                points={cluster.points}
                fill="none"
                stroke="#00E6E6"
                strokeWidth="0.9"
                strokeOpacity="0.25"
                strokeLinejoin="round"
              />
            </g>
          ))}

          {/* Vertex dots on main cluster */}
          {CLUSTERS[0].points.split(" ").map((pt, i) => {
            const [x, y] = pt.split(",");
            return (
              <circle key={i} cx={x} cy={y} r="0.6" fill="#00E6E6" fillOpacity="0.9" />
            );
          })}
        </svg>

        {/* Cluster labels */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
          {CLUSTERS.map((c, i) => (
            <g key={i}>
              <rect
                x={parseFloat(c.label.x) - 8}
                y={parseFloat(c.label.y) - 3.5}
                width={i === 0 ? 22 : i === 1 ? 20 : 18}
                height="6"
                rx="1.5"
                fill="#0d2424"
                fillOpacity="0.85"
              />
              <text
                x={c.label.x}
                y={c.label.y}
                textAnchor="middle"
                fontSize="2.4"
                fontWeight="700"
                fill="#00E6E6"
                fontFamily="monospace"
              >
                {c.label.text}
              </text>
            </g>
          ))}
        </svg>

        {/* Scan line overlay */}
        <ScanOverlay />

        {/* Corner grid marks (HUD feel) */}
        {[
          "top-2 left-2 border-t-2 border-l-2",
          "top-2 right-2 border-t-2 border-r-2",
          "bottom-2 left-2 border-b-2 border-l-2",
          "bottom-2 right-2 border-b-2 border-r-2",
        ].map((cls, i) => (
          <div key={i} className={`absolute w-5 h-5 border-[#00E6E6]/60 ${cls}`} />
        ))}

        {/* Coordinate stamp */}
        <div className="absolute bottom-3 left-4 text-[#00E6E6]/60 font-mono text-[0.55rem] space-y-0.5">
          <p>44.8378°N  -0.5792°W</p>
          <p>GSD: 1.2 m/px · Band: RGB+NIR</p>
        </div>

        {/* Scale bar */}
        <div className="absolute bottom-3 right-4 flex flex-col items-end gap-1">
          <div className="flex items-center gap-1">
            <div className="h-px w-10 bg-white/50" />
            <span className="text-white/50 text-[0.55rem] font-mono">1 km</span>
          </div>
        </div>
      </div>

      {/* Style for scan line */}
      <style>{`
        @keyframes scanline {
          0%   { top: 10%; opacity: 0; }
          5%   { opacity: 0.5; }
          90%  { opacity: 0.5; }
          100% { top: 90%; opacity: 0; }
        }
      `}</style>
    </div>
  );
}
