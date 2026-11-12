import axios from 'axios'
import { ElMessage } from 'element-plus'

// Create the axios instance
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
request.interceptors.request.use(
  (config) => {
    // Tokens or other auth info can be added here
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
request.interceptors.response.use(
  (response) => {
    const { data } = response
    
    // Handle the response according to the backend API convention
    if (data.code === 200 || data.success) {
      return data
    } else {
      ElMessage.error(data.msg || data.message || 'Request failed')
      return Promise.reject(new Error(data.msg || data.message || 'Request failed'))
    }
  },
  (error) => {
    console.error('Response error:', error)
    
    // Handle HTTP error status codes
    if (error.response) {
      const { status } = error.response
      switch (status) {
        case 401:
          ElMessage.error('Unauthorized, please log in again')
          // A redirect to the login page can be handled here
          break
        case 403:
          ElMessage.error('Access denied')
          break
        case 404:
          ElMessage.error('Request URL not found')
          break
        case 500:
          ElMessage.error('Internal server error')
          break
        default:
          ElMessage.error('Network error')
      }
    } else {
      ElMessage.error('Network connection failed')
    }
    
    return Promise.reject(error)
  }
)

// Wrappers for the common request methods
export const http = {
  get(url, params) {
    return request.get(url, { params })
  },
  
  post(url, data, config = {}) {
    return request.post(url, data, config)
  },
  
  put(url, data, config = {}) {
    return request.put(url, data, config)
  },
  
  delete(url, params) {
    return request.delete(url, { params })
  },
  
  upload(url, formData, onUploadProgress) {
    return request.post(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress
    })
  }
}

export default request