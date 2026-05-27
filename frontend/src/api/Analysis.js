import axios from "axios"
import { sendGet, sendPost } from "./generic"
import { getNodeBackendUrl } from "../constants/Urls"

/**
 * POST /compare — sends before + after as multipart/form-data.
 * Returns { imageUrl: string, metrics: object } on success, or { status: "Error" } on failure.
 * imageUrl is a data URL (data:image/jpeg;base64,...) from the backend composite JPEG.
 */
export const compareImagesApi = async (beforeFile, afterFile) => {
    const formData = new FormData()
    formData.append("before", beforeFile)
    formData.append("after", afterFile)

    try {
        const response = await axios.post(`${getNodeBackendUrl()}compare`, formData)
        return {
            imageUrl: response.data.imageDataUrl,
            metrics:  response.data.metrics || null,
        }
    } catch (err) {
        const msg = err.response?.data?.error || err.message || "Compare failed"
        return { status: "Error", errorMessage: msg }
    }
}

export const getAnalysisResultApi   = (analysisId) => sendGet(`analysis/${analysisId}`)
export const getProjectAnalysesApi  = (projectId)  => sendGet(`analysis?projectId=${projectId}`)
