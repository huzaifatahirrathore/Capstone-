import { create } from "zustand"
import {
    getProjectsApi,
    getProjectApi,
    createProjectApi,
    updateProjectApi,
    deleteProjectApi,
} from "../api/Projects"
import { PROJECTS } from "../data/plantationProjects"

export const useProjectsStore = create((set, get) => ({
    projects:        PROJECTS,   // seeded with mock data until API responds
    selectedProject: null,
    loading:         false,
    error:           null,

    fetchProjects: async (filters = {}) => {
        set({ loading: true, error: null })
        const res = await getProjectsApi(filters)
        if (res?.status === "Error") {
            // keep existing data on error so UI doesn't blank out
            set({ loading: false, error: res.errorMessage })
            return
        }
        // API returns an array; fall back to mock data if empty/null
        const list = Array.isArray(res) && res.length > 0 ? res : PROJECTS
        set({ projects: list, loading: false })
    },

    fetchProject: async (id) => {
        set({ loading: true, error: null })
        const res = await getProjectApi(id)
        if (res?.status !== "Error") {
            set({ selectedProject: res, loading: false })
        } else {
            set({ loading: false, error: res.errorMessage })
        }
    },

    createProject: async (data) => {
        set({ loading: true, error: null })
        const res = await createProjectApi(data)
        if (res?.status === "Error") {
            set({ loading: false, error: res.errorMessage })
            return null
        }
        // Optimistically add to list
        const created = res?.id ? res : { ...data, id: Date.now() }
        set((state) => ({
            projects: [created, ...state.projects],
            loading: false,
        }))
        return created
    },

    updateProject: async (id, data) => {
        const res = await updateProjectApi(id, data)
        if (res?.status !== "Error") {
            set((state) => ({
                projects: state.projects.map((p) => (p.id === id ? { ...p, ...data } : p)),
            }))
        }
        return res
    },

    deleteProject: async (id) => {
        await deleteProjectApi(id)
        set((state) => ({
            projects: state.projects.filter((p) => p.id !== id),
        }))
    },

    setSelectedProject: (project) => set({ selectedProject: project }),
    clearError:         ()        => set({ error: null }),
}))
