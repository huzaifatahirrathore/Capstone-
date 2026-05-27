import axios from "axios"
import { sendGet, sendPost } from "./generic"
import { getNodeBackendUrl } from "../constants/Urls"

/**
 * POST /compare — sends before + after as multipart/form-data.
 * Backend runs the Python ML pipeline and returns a composite JPEG blob.
 * Returns a blob object URL string on success, or { status: "Error" } on failure.
 */
export const compareImagesApi = async (beforeFile, afterFile) => {
    const formData = new FormData()
    formData.append("before", beforeFile)
    formData.append("after", afterFile)

    try {
        const response = await axios.post(
            `${getNodeBackendUrl()}compare`,
            formData,
            { responseType: "blob" }
        )
        return URL.createObjectURL(response.data)
    } catch (err) {
        const msg = err.response?.data?.error || err.message || "Compare failed"
        return { status: "Error", errorMessage: msg }
    }
}

export const getAnalysisResultApi   = (analysisId) => sendGet(`analysis/${analysisId}`)
export const getProjectAnalysesApi  = (projectId)  => sendGet(`analysis?projectId=${projectId}`)
