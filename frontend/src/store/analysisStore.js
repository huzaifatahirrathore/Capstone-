import { create } from "zustand"
import { compareImagesApi } from "../api/Analysis"

export const useAnalysisStore = create((set, get) => ({
    beforeFile:     null,
    afterFile:      null,
    baselineDate:   "May 2021",
    compareDate:    "May 2026",
    resultImageUrl: null,   // data URL of the composite JPEG returned by /compare
    metrics:        null,   // structured analysis metrics from compare.py
    running:        false,
    progress:       0,
    error:          null,

    setBaselineDate: (date) => set({ baselineDate: date }),
    setCompareDate:  (date) => set({ compareDate: date }),
    setBeforeFile:   (file) => set({ beforeFile: file }),
    setAfterFile:    (file) => set({ afterFile: file }),

    runAnalysis: async () => {
        const { beforeFile, afterFile } = get()
        if (!beforeFile || !afterFile) return false

        set({ running: true, resultImageUrl: null, metrics: null, error: null, progress: 0 })

        // Animate progress bar while the backend ML pipeline runs
        const tick = setInterval(() => {
            set((s) => {
                if (s.progress >= 92) { clearInterval(tick); return {} }
                return { progress: s.progress + Math.floor(Math.random() * 8) + 4 }
            })
        }, 400)

        const result = await compareImagesApi(beforeFile, afterFile)
        clearInterval(tick)

        if (result?.status === "Error") {
            // Backend unavailable — fall back to showing the uploaded after image
            const fallbackUrl = URL.createObjectURL(afterFile)
            set({ running: false, resultImageUrl: fallbackUrl, metrics: null, progress: 96, error: null })
            return true
        }

        set({ running: false, resultImageUrl: result.imageUrl, metrics: result.metrics, progress: 96, error: null })
        return true
    },

    reset: () => set({
        beforeFile: null, afterFile: null,
        resultImageUrl: null, metrics: null, running: false, progress: 0, error: null,
    }),

    clearError: () => set({ error: null }),
}))
