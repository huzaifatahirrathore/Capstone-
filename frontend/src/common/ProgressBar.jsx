export function ProgressBar({ pct }) {
  return (
    <div className="w-full h-1.5 bg-[#E5DDD0] rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${pct}%`,
          background:
            pct === 100
              ? "#008080"
              : `linear-gradient(90deg, #A3431F ${100 - pct}%, #008080 100%)`,
        }}
      />
    </div>
  );
}
