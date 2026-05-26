import { sendGet, sendPost, sendPut, sendDelete, uploadFile } from "./generic"

export const getProjectsApi = (params = {}) => {
    const query = new URLSearchParams()
    if (params.region)  query.set("region",  params.region)
    if (params.sponsor) query.set("sponsor", params.sponsor)
    if (params.status)  query.set("status",  params.status)
    if (params.search)  query.set("search",  params.search)
    const qs = query.toString()
    return sendGet(`projects${qs ? `?${qs}` : ""}`)
}

export const getProjectApi = (id) =>
    sendGet(`projects/${id}`)

export const createProjectApi = (data) =>
    sendPost("projects", data)

export const updateProjectApi = (id, data) =>
    sendPut(`projects/${id}`, data)

export const deleteProjectApi = (id) =>
    sendDelete(`projects/${id}`)

export const uploadProjectThumbnailApi = (id, file) =>
    uploadFile(`projects/${id}/thumbnail`, file)
