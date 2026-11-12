import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAccountStore = defineStore('account', () => {
  // All account info
  const accounts = ref([])
  
  // Platform type map (the Chinese names are compared in the views, keep them)
  const platformTypes = {
    1: '小红书',
    2: '视频号',
    3: '抖音',
    4: '快手'
  }
  
  // Set the account list
  const setAccounts = (accountsData) => {
    // Convert the backend data format to the one the frontend uses
    accounts.value = accountsData.map(item => {
      return {
        id: item[0],
        type: item[1],
        filePath: item[2],
        name: item[3],
        status: item[4] === -1 ? '验证中' : (item[4] === 1 ? '正常' : '异常'),
        platform: platformTypes[item[1]] || '未知'
      }
    })
  }
  
  // Add an account
  const addAccount = (account) => {
    accounts.value.push(account)
  }
  
  // Update an account
  const updateAccount = (id, updatedAccount) => {
    const index = accounts.value.findIndex(acc => acc.id === id)
    if (index !== -1) {
      accounts.value[index] = { ...accounts.value[index], ...updatedAccount }
    }
  }
  
  // Delete an account
  const deleteAccount = (id) => {
    accounts.value = accounts.value.filter(acc => acc.id !== id)
  }
  
  // Get the accounts of a platform
  const getAccountsByPlatform = (platform) => {
    return accounts.value.filter(acc => acc.platform === platform)
  }
  
  return {
    accounts,
    setAccounts,
    addAccount,
    updateAccount,
    deleteAccount,
    getAccountsByPlatform
  }
})