export function MetricWidget({ icon: Icon, label, value, sub, variant = "default" }) {
  const variants = {
    default:    { card: "bg-[#37393D] border-[#404348]",  label: "text-[#9CA3AF]", value: "text-white"    },
    teal:       { card: "bg-[#37393D] border-[#404348]",  label: "text-[#9CA3AF]", value: "text-[#00E6E6]" },
    confidence: {
      card:  "bg-[#00E6E6]/10 border-[#00E6E6]/30",
      label: "text-[#00E6E6]/70",
      value: "text-[#00E6E6]",
    },
  };
  const s = variants[variant] ?? variants.default;

  return (
    <div className={`rounded-xl border p-4 flex flex-col gap-2 ${s.card}`}>
      <div className="flex items-center justify-between">
        <span className={`text-[0.65rem] font-bold uppercase tracking-widest ${s.label}`}>{label}</span>
        {Icon && (
          <span className={variant === "confidence" ? "text-[#00E6E6]" : "text-[#4B5563]"}>
            <Icon size={15} />
          </span>
        )}
      </div>
      <p className={`text-2xl font-black leading-none tracking-tight ${s.value}`}>
        {value}
      </p>
      {sub && (
        <p className={`text-[0.65rem] ${variant === "confidence" ? "text-[#00E6E6]/60" : "text-[#6B7280]"}`}>
          {sub}
        </p>
      )}
    </div>
  );
}
