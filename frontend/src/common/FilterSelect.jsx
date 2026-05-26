import { ChevronIcon } from "./Icons";
export function FilterSelect({ value, onChange, options }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-white border border-[#D6CDBF] text-[#5C4A38] text-[0.7rem] font-medium pl-2.5 pr-6 py-1.5 rounded-md outline-none focus:border-[#A3431F] cursor-pointer"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
      <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[#A3431F]">
        <ChevronIcon />
      </span>
    </div>
  );
}
