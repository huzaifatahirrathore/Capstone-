import { sendGet, sendPost, uploadFile, uploadFiles } from "./generic"

export const uploadAnalysisImageApi = (projectId, file, type) => {
    const formUrl = `analysis/upload?projectId=${projectId}&type=${type}`
    return uploadFile(formUrl, file)
}

export const uploadAnalysisImagesApi = (projectId, files) =>
    uploadFiles(`analysis/upload?projectId=${projectId}`, files)

export const runAnalysisApi = (payload) =>
    sendPost("analysis/run", payload)
    // payload: { projectId, beforeImageId, afterImageId, baselineDate, compareDate }

export const getAnalysisResultApi = (analysisId) =>
    sendGet(`analysis/${analysisId}`)

export const getProjectAnalysesApi = (projectId) =>
    sendGet(`analysis?projectId=${projectId}`)
