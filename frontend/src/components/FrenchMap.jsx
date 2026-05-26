const REGION_PATHS = {
  Aquitaine: {
    d: "M 195 340 L 175 330 L 160 340 L 155 360 L 165 385 L 185 395 L 205 390 L 220 375 L 225 355 L 215 340 Z",
    label: { x: 188, y: 365 },
  },
  Brittany: {
    d: "M 80 175 L 60 168 L 45 175 L 40 190 L 48 205 L 68 210 L 88 205 L 98 192 L 95 178 Z",
    label: { x: 69, y: 191 },
  },
  Normandy: {
    d: "M 145 135 L 125 128 L 108 135 L 105 152 L 115 165 L 135 168 L 155 162 L 162 148 L 158 135 Z",
    label: { x: 133, y: 150 },
  },
  "Centre-Val de Loire": {
    d: "M 190 225 L 168 215 L 150 222 L 148 242 L 158 260 L 178 265 L 200 260 L 210 244 L 205 228 Z",
    label: { x: 178, y: 242 },
  },
  Alsace: {
    d: "M 320 165 L 308 158 L 298 165 L 297 182 L 306 194 L 320 197 L 332 192 L 337 178 L 332 166 Z",
    label: { x: 317, y: 178 },
  },
  Provence: {
    d: "M 290 360 L 268 350 L 252 358 L 250 378 L 262 395 L 284 400 L 305 394 L 315 378 L 308 360 Z",
    label: { x: 282, y: 378 },
  },
  Occitanie: {
    d: "M 230 340 L 208 328 L 192 336 L 190 358 L 203 376 L 226 380 L 248 373 L 256 354 L 246 336 Z",
    label: { x: 222, y: 356 },
  },
};

export function FranceMap({ activeRegions, onRegionClick, selectedRegion }) {
  return (
    <svg
      viewBox="0 0 440 460"
      className="w-full h-full"
      style={{ maxHeight: "100%" }}
    >
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

      {Object.entries(REGION_PATHS).map(([name, { d, label }]) => {
        const isActive = activeRegions.includes(name);
        const isSelected = selectedRegion === name;
        return (
          <g
            key={name}
            onClick={() => isActive && onRegionClick(name)}
            className={isActive ? "cursor-pointer" : ""}
          >
            <path
              d={d}
              fill={isActive ? (isSelected ? "#008080" : "#008080") : "#D6E8E4"}
              fillOpacity={isActive ? (isSelected ? 0.85 : 0.38) : 0.5}
              stroke={isActive ? "#008080" : "#B8CEC9"}
              strokeWidth={isSelected ? 2 : 1}
              className={
                isActive
                  ? "transition-all duration-200 hover:fill-opacity-70"
                  : ""
              }
            />
            {isActive && (
              <text
                x={label.x}
                y={label.y}
                textAnchor="middle"
                fontSize="7"
                fontWeight="600"
                fill={isSelected ? "#fff" : "#006060"}
                className="select-none pointer-events-none"
              >
                {name.length > 12 ? name.slice(0, 10) + "…" : name}
              </text>
            )}
          </g>
        );
      })}

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
          y="-5"
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
          y2="-3"
          stroke="#008080"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </g>

      <g transform="translate(22, 430)">
        <line
          x1="0"
          y1="0"
          x2="60"
          y2="0"
          stroke="#8CAAA6"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <line x1="0" y1="-4" x2="0" y2="4" stroke="#8CAAA6" strokeWidth="1.5" />
        <line
          x1="60"
          y1="-4"
          x2="60"
          y2="4"
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
