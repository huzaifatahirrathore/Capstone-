import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TopNav } from "../components/TopNav";
import { useProjectsStore } from "../store/projectsStore";
import { WizardStepper } from "../components/WizardStepper";
import { BasicInfoForm } from "../components/BasicInfoForm";
import { ProjectPreviewCard } from "../components/ProjectPreviewCard";
import { BoundaryMapCard } from "../components/BoundaryMapCard";
import { ConfirmationCard } from "../components/ConfirmationCard";

const EMPTY_FORM = {
  name: "",
  region: "",
  sponsor: "",
  status: "Active",
  hectares: "",
  goalPct: 0,
  thumb: "",
  verified: false,
};

const EMPTY_POINT = () => ({ id: Date.now(), lat: "", lng: "", label: "" });

const STEP_META = {
  1: { title: "Basic Info", sub: "Enter project details and metadata." },
  2: {
    title: "Define Plantation Boundary",
    sub: "Enter GPS coordinates to define the project zone.",
  },
  3: {
    title: "Blockchain Registration",
    sub: "Review and sign the project on-chain.",
  },
};

export default function NewProjectWizardPage() {
  const navigate = useNavigate();
  const { createProject } = useProjectsStore();
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(EMPTY_FORM);
  const [points, setPoints] = useState([
    EMPTY_POINT(),
    EMPTY_POINT(),
    EMPTY_POINT(),
  ]);

  const meta = STEP_META[step];

  return (
    <div className="flex flex-col h-screen bg-[#EFE8DC] overflow-hidden font-sans">
      <TopNav subtitle="Enterprise" title="New Plantation Project" />

      <div className="flex-1 overflow-y-auto px-8 py-6 flex flex-col gap-5 min-h-0">
        <WizardStepper current={step} />

        <div>
          <h1 className="text-[#2C2420] text-xl font-bold tracking-tight leading-none">
            {meta.title}
          </h1>
          <p className="text-[#8C7B68] text-sm mt-1.5">{meta.sub}</p>
        </div>

        <div className="flex gap-5 flex-1 min-h-0">
          {step === 1 && (
            <>
              <BasicInfoForm form={form} onChange={setForm} />
              <ProjectPreviewCard form={form} onContinue={() => setStep(2)} />
            </>
          )}

          {step === 2 && (
            <>
              <BoundaryMapCard points={points} onChange={setPoints} />
              <ConfirmationCard
                onBack={() => setStep(1)}
                onContinue={async () => {
                  await createProject({ ...form, boundary: points });
                  setStep(3);
                }}
              />
            </>
          )}

          {step === 3 && (
            <div className="flex-1 bg-[#F9F6F0] rounded-2xl border border-[#D6CDBF] flex items-center justify-center shadow-sm">
              <div className="text-center space-y-3 px-8">
                <div className="w-14 h-14 rounded-full bg-[#008080]/10 flex items-center justify-center mx-auto">
                  <svg
                    viewBox="0 0 24 24"
                    width="28"
                    height="28"
                    fill="none"
                    stroke="#008080"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                  </svg>
                </div>
                <p className="text-[#2C2420] text-base font-bold">
                  Blockchain Registration
                </p>
                <p className="text-[#8C7B68] text-sm max-w-xs leading-relaxed">
                  This step will connect to the on-chain registry and sign the
                  project record.
                </p>
                <div className="flex flex-col items-center gap-2 mt-2">
                  <button
                    onClick={() => navigate("/dashboard")}
                    className="bg-[#008080] hover:bg-[#006666] text-white text-sm font-semibold px-6 py-2.5 rounded-xl transition-colors"
                  >
                    Go to Dashboard
                  </button>
                  <button
                    onClick={() => setStep(2)}
                    className="text-[#A3431F] text-sm font-semibold underline underline-offset-2"
                  >
                    ← Back to Boundary
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
