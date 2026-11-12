import { http } from '@/utils/request'

// Account management API
export const accountApi = {
  // Get the account list with validation
  getValidAccounts() {
    return http.get('/getValidAccounts')
  },

  // Get the account list without validation (fast load)
  getAccounts() {
    return http.get('/getAccounts')
  },

  // Add an account
  addAccount(data) {
    return http.post('/account', data)
  },

  // Update an account
  updateAccount(data) {
    return http.post('/updateUserinfo', data)
  },

  // Delete an account
  deleteAccount(id) {
    return http.get(`/deleteAccount?id=${id}`)
  }
}