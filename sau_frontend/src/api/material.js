import { http } from '@/utils/request'

// Material management API
export const materialApi = {
  // Get all materials
  getAllMaterials: () => {
    return http.get('/getFiles')
  },
  
  // Upload a material
  uploadMaterial: (formData, onUploadProgress) => {
    // Use http.upload, which already sets the right Content-Type
    return http.upload('/uploadSave', formData, onUploadProgress)
  },
  
  // Delete a material
  deleteMaterial: (id) => {
    return http.get(`/deleteFile?id=${id}`)
  },
  
  // Download a material
  downloadMaterial: (filePath) => {
    return `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'}/download/${filePath}`
  },
  
  // Get the preview URL of a material
  getMaterialPreviewUrl: (filename) => {
    return `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'}/getFile?filename=${filename}`
  }
}