import { useState, useMemo } from "react";
import {
  PROJECTS,
  REGIONS,
  SPONSORS,
  STATUSES,
} from "../data/plantationProjects";
import { FranceMap } from "../components/FrenchMap";
import { ProjectCard } from "../components/ProjectCard";
import {
  SearchIcon,
  BellIcon,
  LayersIcon,
  SettingsIcon,
  MapPinIcon,
  ChevronIcon,
} from "../common/Icons";
import { FilterSelect } from "../common/FilterSelect";
import { ProgressBar } from "../common/ProgressBar";

export default function PlantationProjectsPage() {
  const [regionFilter, setRegionFilter] = useState("All Regions");
  const [sponsorFilter, setSponsorFilter] = useState("All Sponsors");
  const [statusFilter, setStatusFilter] = useState("All Statuses");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  const filtered = useMemo(() => {
    return PROJECTS.filter((p) => {
      if (regionFilter !== "All Regions" && p.region !== regionFilter)
        return false;
      if (sponsorFilter !== "All Sponsors" && p.sponsor !== sponsorFilter)
        return false;
      if (statusFilter !== "All Statuses" && p.status !== statusFilter)
        return false;
      if (search && !p.name.toLowerCase().includes(search.toLowerCase()))
        return false;
      return true;
    });
  }, [regionFilter, sponsorFilter, statusFilter, search]);

  const selected = PROJECTS.find((p) => p.id === selectedId) ?? null;
  const activeRegions = filtered.map((p) => p.region);

  return (
    <div className="flex flex-col h-screen bg-[#EFE8DC] overflow-hidden font-sans">
      <header className="shrink-0 h-14 bg-[#A3431F] flex items-center justify-between px-6 z-30 shadow-md">
        <div className="flex items-center gap-2.5">
          <svg viewBox="0 0 24 26" width="22" height="22" fill="none">
            <line
              x1="12"
              y1="26"
              x2="12"
              y2="16"
              stroke="#EFE8DC"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <circle cx="12" cy="16" r="2" fill="#00E6E6" />
            <line
              x1="12"
              y1="16"
              x2="5"
              y2="10"
              stroke="#EFE8DC"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
            <line
              x1="12"
              y1="16"
              x2="19"
              y2="10"
              stroke="#EFE8DC"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
            <line
              x1="12"
              y1="16"
              x2="12"
              y2="7"
              stroke="#EFE8DC"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
            <circle cx="5" cy="10" r="1.4" fill="#EFE8DC" fillOpacity="0.8" />
            <circle cx="19" cy="10" r="1.4" fill="#EFE8DC" fillOpacity="0.8" />
            <circle cx="12" cy="7" r="1.4" fill="#EFE8DC" fillOpacity="0.8" />
          </svg>
          <span className="text-[#EFE8DC] font-bold text-lg tracking-wide select-none">
            EcoLedger
          </span>
          <span className="hidden sm:block h-4 w-px bg-[#EFE8DC]/25 mx-1" />
          <span className="hidden sm:block text-[#EFE8DC]/50 text-xs tracking-widest uppercase font-medium select-none">
            Enterprise
          </span>
        </div>

        <div className="flex items-center gap-3">
          <button className="text-[#EFE8DC]/65 hover:text-[#EFE8DC] transition-colors p-1.5 rounded-lg hover:bg-white/10">
            <SearchIcon />
          </button>
          <button className="relative text-[#EFE8DC]/65 hover:text-[#EFE8DC] transition-colors p-1.5 rounded-lg hover:bg-white/10">
            <BellIcon />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-[#00E6E6] rounded-full" />
          </button>
          <div className="w-8 h-8 rounded-full bg-[#EFE8DC]/20 border-2 border-[#EFE8DC]/35 flex items-center justify-center text-[#EFE8DC] text-xs font-bold select-none">
            UI
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-[420px] shrink-0 flex flex-col bg-[#EFE8DC] border-r border-[#D6CDBF] overflow-hidden">
          <div className="shrink-0 px-5 pt-5 pb-4 border-b border-[#D6CDBF] bg-[#EFE8DC]">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-[#2C2420] text-base font-bold tracking-tight">
                  Plantation Projects
                </h2>
                <p className="text-[#8C7B68] text-[0.68rem] mt-0.5">
                  {filtered.length} of {PROJECTS.length} projects
                </p>
              </div>
              <button className="flex items-center gap-1.5 text-[#A3431F] text-[0.7rem] font-semibold bg-[#A3431F]/10 px-3 py-1.5 rounded-lg hover:bg-[#A3431F]/20 transition-colors">
                <LayersIcon />
                Export
              </button>
            </div>

            <div className="relative mb-3">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A3431F]/60">
                <SearchIcon />
              </span>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search projects…"
                className="w-full bg-white border border-[#D6CDBF] rounded-lg pl-8 pr-3 py-2 text-[0.78rem] text-[#2C2420] placeholder:text-[#C4B8A8] outline-none focus:border-[#A3431F] transition-colors"
              />
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2 flex-wrap">
              <FilterSelect
                value={regionFilter}
                onChange={setRegionFilter}
                options={REGIONS}
              />
              <FilterSelect
                value={sponsorFilter}
                onChange={setSponsorFilter}
                options={SPONSORS}
              />
              <FilterSelect
                value={statusFilter}
                onChange={setStatusFilter}
                options={STATUSES}
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-[#B0A090]">
                <MapPinIcon />
                <p className="mt-3 text-sm font-medium">
                  No projects match filters
                </p>
              </div>
            ) : (
              filtered.map((p) => (
                <ProjectCard
                  key={p.id}
                  project={p}
                  selected={selectedId === p.id}
                  onClick={() =>
                    setSelectedId((prev) => (prev === p.id ? null : p.id))
                  }
                />
              ))
            )}
          </div>
        </aside>

        <main className="flex-1 relative overflow-hidden bg-[#EAF3F1]">
          <div className="absolute top-4 left-4 z-20 flex flex-col gap-2">
            <button className="w-9 h-9 bg-white rounded-lg shadow flex items-center justify-center text-[#5C7C78] hover:bg-[#F0FAF8] transition-colors border border-[#C8DDD8]">
              <span className="text-lg font-light leading-none">+</span>
            </button>
            <button className="w-9 h-9 bg-white rounded-lg shadow flex items-center justify-center text-[#5C7C78] hover:bg-[#F0FAF8] transition-colors border border-[#C8DDD8]">
              <span className="text-lg font-light leading-none">−</span>
            </button>
            <div className="w-px h-3 bg-[#C8DDD8] mx-auto" />
            <button className="w-9 h-9 bg-white rounded-lg shadow flex items-center justify-center text-[#5C7C78] hover:bg-[#F0FAF8] transition-colors border border-[#C8DDD8]">
              <LayersIcon />
            </button>
            <button className="w-9 h-9 bg-white rounded-lg shadow flex items-center justify-center text-[#5C7C78] hover:bg-[#F0FAF8] transition-colors border border-[#C8DDD8]">
              <SettingsIcon />
            </button>
          </div>

          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20">
            <div className="bg-white/80 backdrop-blur-sm px-4 py-1.5 rounded-full shadow-sm border border-[#C8DDD8] flex items-center gap-2">
              <MapPinIcon />
              <span className="text-[#3D6B65] text-[0.72rem] font-semibold tracking-wide">
                France — Plantation Zones
              </span>
            </div>
          </div>

          <div className="absolute inset-0 flex items-center justify-center p-8">
            <FranceMap
              activeRegions={activeRegions}
              onRegionClick={(name) => {
                const match = PROJECTS.find((p) => p.region === name);
                if (match)
                  setSelectedId((prev) =>
                    prev === match.id ? null : match.id,
                  );
              }}
              selectedRegion={selected?.region ?? null}
            />
          </div>

          <div className="absolute bottom-5 right-5 z-20 bg-white/90 backdrop-blur-sm rounded-xl shadow-sm border border-[#C8DDD8] px-4 py-3 space-y-2 min-w-[160px]">
            <p className="text-[#5C7C78] text-[0.62rem] font-bold uppercase tracking-widest mb-1">
              Legend
            </p>
            {[
              { color: "#008080", opacity: "85%", label: "Active Zone" },
              { color: "#008080", opacity: "38%", label: "Tracked Zone" },
              { color: "#D6E8E4", opacity: "100%", label: "Inactive" },
            ].map(({ color, opacity, label }) => (
              <div key={label} className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-sm border border-[#C8DDD8]"
                  style={{ background: color, opacity }}
                />
                <span className="text-[#5C4A38] text-[0.68rem]">{label}</span>
              </div>
            ))}
          </div>

          {selected && (
            <div className="absolute top-16 right-5 z-20 bg-white rounded-xl shadow-lg border border-[#C8DDD8] p-4 w-64 animate-fade-in">
              <div className="flex items-start justify-between mb-2">
                <p className="text-[#2C2420] text-sm font-bold leading-snug">
                  {selected.name}
                </p>
                <button
                  onClick={() => setSelectedId(null)}
                  className="text-[#B0A090] hover:text-[#5C4A38] text-lg leading-none ml-2 mt-0.5"
                >
                  ×
                </button>
              </div>
              <p className="text-[#8C7B68] text-[0.7rem] mb-3">
                {selected.region} · {selected.sponsor}
              </p>
              <div className="space-y-1 mb-3">
                <div className="flex justify-between text-[0.68rem]">
                  <span className="text-[#8C7B68]">Area</span>
                  <span className="font-semibold text-[#2C2420]">
                    {selected.hectares} ha
                  </span>
                </div>
                <div className="flex justify-between text-[0.68rem]">
                  <span className="text-[#8C7B68]">Goal Achievement</span>
                  <span className="font-bold text-[#008080]">
                    {selected.goalPct}%
                  </span>
                </div>
              </div>
              <ProgressBar pct={selected.goalPct} />
              {selected.verified && (
                <div className="mt-3 pt-3 border-t border-[#EDE6DB]">
                  <span className="inline-flex items-center gap-1.5 bg-[#008080]/10 text-[#008080] text-[0.62rem] font-semibold px-3 py-1 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#008080]" />
                    Blockchain Verified
                  </span>
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
