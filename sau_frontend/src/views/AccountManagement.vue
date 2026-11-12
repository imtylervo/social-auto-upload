<template>
  <div class="account-management">
    <div class="page-header">
      <h1>Account Management</h1>
    </div>
    
    <div class="account-tabs">
      <el-tabs v-model="activeTab" class="account-tabs-nav">
        <el-tab-pane label="All" name="all">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="Search by name or account"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">Add Account</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">Refreshing</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredAccounts.length > 0" class="account-list">
              <el-table :data="filteredAccounts" style="width: 100%">
                <el-table-column label="Avatar" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="Name" width="180" />
                <el-table-column prop="platform" label="Platform">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="Status">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Actions">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">Edit</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">Download Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">Upload Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">Delete</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="No accounts yet" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="Kuaishou" name="kuaishou">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="Search by name or account"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">Add Account</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">Refreshing</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredKuaishouAccounts.length > 0" class="account-list">
              <el-table :data="filteredKuaishouAccounts" style="width: 100%">
                <el-table-column label="Avatar" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="Name" width="180" />
                <el-table-column prop="platform" label="Platform">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="Status">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Actions">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">Edit</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">Download Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">Upload Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">Delete</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="No Kuaishou accounts yet" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="Douyin" name="douyin">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="Search by name or account"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">Add Account</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">Refreshing</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredDouyinAccounts.length > 0" class="account-list">
              <el-table :data="filteredDouyinAccounts" style="width: 100%">
                <el-table-column label="Avatar" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="Name" width="180" />
                <el-table-column prop="platform" label="Platform">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="Status">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Actions">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">Edit</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">Download Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">Upload Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">Delete</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="No Douyin accounts yet" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="WeChat Channels" name="channels">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="Search by name or account"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">Add Account</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">Refreshing</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredChannelsAccounts.length > 0" class="account-list">
              <el-table :data="filteredChannelsAccounts" style="width: 100%">
                <el-table-column label="Avatar" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="Name" width="180" />
                <el-table-column prop="platform" label="Platform">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="Status">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Actions">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">Edit</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">Download Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">Upload Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">Delete</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="No WeChat Channels accounts yet" />
            </div>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="Xiaohongshu" name="xiaohongshu">
          <div class="account-list-container">
            <div class="account-search">
              <el-input
                v-model="searchKeyword"
                placeholder="Search by name or account"
                prefix-icon="Search"
                clearable
                @clear="handleSearch"
                @input="handleSearch"
              />
              <div class="action-buttons">
                <el-button type="primary" @click="handleAddAccount">Add Account</el-button>
                <el-button type="info" @click="fetchAccounts" :loading="false">
                  <el-icon :class="{ 'is-loading': appStore.isAccountRefreshing }"><Refresh /></el-icon>
                  <span v-if="appStore.isAccountRefreshing">Refreshing</span>
                </el-button>
              </div>
            </div>
            
            <div v-if="filteredXiaohongshuAccounts.length > 0" class="account-list">
              <el-table :data="filteredXiaohongshuAccounts" style="width: 100%">
                <el-table-column label="Avatar" width="80">
                  <template #default="scope">
                    <el-avatar :src="getDefaultAvatar(scope.row.name)" :size="40" />
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="Name" width="180" />
                <el-table-column prop="platform" label="Platform">
                  <template #default="scope">
                    <el-tag
                      :type="getPlatformTagType(scope.row.platform)"
                      effect="plain"
                    >
                      {{ scope.row.platform }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="Status">
                  <template #default="scope">
                    <el-tag
                      :type="getStatusTagType(scope.row.status)"
                      effect="plain"
                      :class="{'clickable-status': isStatusClickable(scope.row.status)}"
                      @click="handleStatusClick(scope.row)"
                    >
                      <el-icon :class="scope.row.status === '验证中' ? 'is-loading' : ''" v-if="scope.row.status === '验证中'">
                        <Loading />
                      </el-icon>
                      {{ scope.row.status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="Actions">
                  <template #default="scope">
                    <el-button size="small" @click="handleEdit(scope.row)">Edit</el-button>
                    <el-button size="small" type="primary" :icon="Download" @click="handleDownloadCookie(scope.row)">Download Cookie</el-button>
                    <el-button size="small" type="info" :icon="Upload" @click="handleUploadCookie(scope.row)">Upload Cookie</el-button>
                    <el-button size="small" type="danger" @click="handleDelete(scope.row)">Delete</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <div v-else class="empty-data">
              <el-empty description="No Xiaohongshu accounts yet" />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
    
    <!-- Add/edit account dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? 'Add Account' : 'Edit Account'"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="!sseConnecting"
      :show-close="!sseConnecting"
    >
      <el-form :model="accountForm" label-width="80px" :rules="rules" ref="accountFormRef">
        <el-form-item label="Platform" prop="platform">
          <el-select 
            v-model="accountForm.platform" 
            placeholder="Select a platform" 
            style="width: 100%"
            :disabled="dialogType === 'edit' || sseConnecting"
          >
            <el-option label="快手" value="快手" />
            <el-option label="抖音" value="抖音" />
            <el-option label="视频号" value="视频号" />
            <el-option label="小红书" value="小红书" />
          </el-select>
        </el-form-item>
        <el-form-item label="Name" prop="name">
          <el-input 
            v-model="accountForm.name" 
            placeholder="Enter the account name" 
            :disabled="sseConnecting"
          />
        </el-form-item>
        
        <!-- QR code area -->
        <div v-if="sseConnecting" class="qrcode-container">
          <div v-if="qrCodeData && !loginStatus" class="qrcode-wrapper">
            <p class="qrcode-tip">Scan the QR code with the platform app to log in</p>
            <img :src="qrCodeData" alt="Login QR code" class="qrcode-image" />
          </div>
          <div v-else-if="!qrCodeData && !loginStatus" class="loading-wrapper">
            <el-icon class="is-loading"><Refresh /></el-icon>
            <span>Requesting...</span>
          </div>
          <div v-else-if="loginStatus === '200'" class="success-wrapper">
            <el-icon><CircleCheckFilled /></el-icon>
            <span>Added successfully</span>
          </div>
          <div v-else-if="loginStatus === '500'" class="error-wrapper">
            <el-icon><CircleCloseFilled /></el-icon>
            <span>Failed to add, please try again later</span>
          </div>
        </div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">Cancel</el-button>
          <el-button 
            type="primary" 
            @click="submitAccountForm" 
            :loading="sseConnecting" 
            :disabled="sseConnecting"
          >
            {{ sseConnecting ? 'Requesting' : 'Confirm' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { Refresh, CircleCheckFilled, CircleCloseFilled, Download, Upload, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { accountApi } from '@/api/account'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'
import { http } from '@/utils/request'

// Account store
const accountStore = useAccountStore()
// App store
const appStore = useAppStore()

// Currently active tab
const activeTab = ref('all')

// Search keyword
const searchKeyword = ref('')

// Fetch account data (fast, no validation)
const fetchAccountsQuick = async () => {
  try {
    const res = await accountApi.getAccounts()
    if (res.code === 200 && res.data) {
      // Temporarily set the status of all accounts to "验证中" (verifying)
      const accountsWithPendingStatus = res.data.map(account => {
        const updatedAccount = [...account];
        updatedAccount[4] = -1; // -1 is the temporary "verifying" status
        return updatedAccount;
      });
      accountStore.setAccounts(accountsWithPendingStatus);
    }
  } catch (error) {
    console.error('Fast account data fetch failed:', error)
  }
}

// Fetch account data (with validation)
const fetchAccounts = async () => {
  if (appStore.isAccountRefreshing) return

  appStore.setAccountRefreshing(true)

  try {
    const res = await accountApi.getValidAccounts()
    if (res.code === 200 && res.data) {
      accountStore.setAccounts(res.data)
      ElMessage.success('Account data loaded')
      // Mark as visited
      if (appStore.isFirstTimeAccountManagement) {
        appStore.setAccountManagementVisited()
      }
    } else {
      ElMessage.error('Failed to fetch account data')
    }
  } catch (error) {
    console.error('Failed to fetch account data:', error)
    ElMessage.error('Failed to fetch account data')
  } finally {
    appStore.setAccountRefreshing(false)
  }
}

// Validate all accounts in the background (uses setTimeout so the UI is not blocked)
const validateAllAccountsInBackground = async () => {
  // setTimeout moves the validation to the next event loop tick so the UI is not blocked
  setTimeout(async () => {
    try {
      const res = await accountApi.getValidAccounts()
      if (res.code === 200 && res.data) {
        accountStore.setAccounts(res.data)
      }
    } catch (error) {
      console.error('Background account validation failed:', error)
    }
  }, 0)
}

// Fetch account data when the page loads
onMounted(() => {
  // Fetch the account list fast (no validation) and show it right away
  fetchAccountsQuick()

  // Validate all accounts in the background
  setTimeout(() => {
    validateAllAccountsInBackground()
  }, 100) // Short delay so the user sees the fast-loaded list first
})

// Tag type for a platform
const getPlatformTagType = (platform) => {
  const typeMap = {
    '快手': 'success',
    '抖音': 'danger',
    '视频号': 'warning',
    '小红书': 'info'
  }
  return typeMap[platform] || 'info'
}

// Whether a status is clickable (the "异常" (invalid) status is)
const isStatusClickable = (status) => {
  return status === '异常'; // only "异常" (invalid) is clickable, "验证中" (verifying) is not
}

// Tag type for a status
const getStatusTagType = (status) => {
  if (status === '验证中') {
    return 'info'; // verifying: gray
  } else if (status === '正常') {
    return 'success'; // valid: green
  } else {
    return 'danger'; // invalid: red
  }
}

// Handle a click on the status
const handleStatusClick = (row) => {
  if (isStatusClickable(row.status)) {
    // Start the re-login flow
    handleReLogin(row)
  }
}

// Filtered account list
const filteredAccounts = computed(() => {
  if (!searchKeyword.value) return accountStore.accounts
  return accountStore.accounts.filter(account =>
    account.name.includes(searchKeyword.value)
  )
})

// Account lists filtered by platform
const filteredKuaishouAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '快手')
})

const filteredDouyinAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '抖音')
})

const filteredChannelsAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '视频号')
})

const filteredXiaohongshuAccounts = computed(() => {
  return filteredAccounts.value.filter(account => account.platform === '小红书')
})

// Search handler
const handleSearch = () => {
  // The search logic lives in the computed properties
}

// Dialog state
const dialogVisible = ref(false)
const dialogType = ref('add') // 'add' or 'edit'
const accountFormRef = ref(null)

// Account form
const accountForm = reactive({
  id: null,
  name: '',
  platform: '',
  status: '正常'
})

// Form validation rules
const rules = {
  platform: [{ required: true, message: 'Select a platform', trigger: 'change' }],
  name: [{ required: true, message: 'Enter the account name', trigger: 'blur' }]
}

// SSE connection state
const sseConnecting = ref(false)
const qrCodeData = ref('')
const loginStatus = ref('')

// Add an account
const handleAddAccount = () => {
  dialogType.value = 'add'
  Object.assign(accountForm, {
    id: null,
    name: '',
    platform: '',
    status: '正常'
  })
  // Reset the SSE state
  sseConnecting.value = false
  qrCodeData.value = ''
  loginStatus.value = ''
  dialogVisible.value = true
}

// Edit an account
const handleEdit = (row) => {
  dialogType.value = 'edit'
  Object.assign(accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status
  })
  dialogVisible.value = true
}

// Delete an account
const handleDelete = (row) => {
  ElMessageBox.confirm(
    `Delete account ${row.name}?`,
    'Warning',
    {
      confirmButtonText: 'OK',
      cancelButtonText: 'Cancel',
      type: 'warning',
    }
  )
    .then(async () => {
      try {
        // Call the API to delete the account
        const response = await accountApi.deleteAccount(row.id)

        if (response.code === 200) {
          // Remove the account from the store
          accountStore.deleteAccount(row.id)
          ElMessage({
            type: 'success',
            message: 'Deleted',
          })
        } else {
          ElMessage.error(response.msg || 'Delete failed')
        }
      } catch (error) {
        console.error('Failed to delete account:', error)
        ElMessage.error('Failed to delete account')
      }
    })
    .catch(() => {
      // Delete cancelled
    })
}

// Download the cookie file
const handleDownloadCookie = (row) => {
  // Get the cookie file from the backend
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
  const downloadUrl = `${baseUrl}/downloadCookie?filePath=${encodeURIComponent(row.filePath)}`

  // Create a hidden link to trigger the download
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = `${row.name}_cookie.json`
  link.target = '_blank'
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// Upload a cookie file
const handleUploadCookie = (row) => {
  // Create a hidden file input
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.style.display = 'none'
  document.body.appendChild(input)

  input.onchange = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    // Check the file type
    if (!file.name.endsWith('.json')) {
      ElMessage.error('Select a cookie file in JSON format')
      document.body.removeChild(input)
      return
    }

    try {
      // Build the FormData object
      const formData = new FormData()
      formData.append('file', file)
      formData.append('id', row.id)
      formData.append('platform', row.platform)

      // Send the upload through the shared http wrapper
      const result = await http.upload('/uploadCookie', formData)

      ElMessage.success('Cookie file uploaded')
      // Refresh the account list to show the update
      fetchAccounts()
    } catch (error) {
      ElMessage.error('Cookie file upload failed')
    } finally {
      document.body.removeChild(input)
    }
  }

  input.click()
}

// Log an account in again
const handleReLogin = (row) => {
  // Fill in the form
  dialogType.value = 'edit'
  Object.assign(accountForm, {
    id: row.id,
    name: row.name,
    platform: row.platform,
    status: row.status
  })

  // Reset the SSE state
  sseConnecting.value = false
  qrCodeData.value = ''
  loginStatus.value = ''

  // Show the dialog
  dialogVisible.value = true

  // Start the login flow right away
  setTimeout(() => {
    connectSSE(row.platform, row.name)
  }, 300)
}

// Default avatar
const getDefaultAvatar = (name) => {
  // A simple default avatar; the color can vary with the user name
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=random`
}

// SSE EventSource object
let eventSource = null

// Close the SSE connection
const closeSSEConnection = () => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

// Open the SSE connection
const connectSSE = (platform, name) => {
  // Close any existing connection
  closeSSEConnection()

  // Set the connection state
  sseConnecting.value = true
  qrCodeData.value = ''
  loginStatus.value = ''

  // Platform type number
  const platformTypeMap = {
    '小红书': '1',
    '视频号': '2',
    '抖音': '3',
    '快手': '4'
  }

  const type = platformTypeMap[platform] || '1'

  // Create the SSE connection
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'
  const url = `${baseUrl}/login?type=${type}&id=${encodeURIComponent(name)}`

  eventSource = new EventSource(url)

  // Listen for messages
  eventSource.onmessage = (event) => {
    const data = event.data

    // No QR code yet and the data is long: treat it as the QR code
    if (!qrCodeData.value && data.length > 100) {
      try {
        if (data.startsWith('data:image')) {
          qrCodeData.value = data
        } else {
          qrCodeData.value = `data:image/png;base64,${data}`
        }
      } catch (error) {
        // Error while handling the QR code data
      }
    }
    // A status code was received
    else if (data === '200' || data === '500') {
      loginStatus.value = data

      // Login succeeded
      if (data === '200') {
        setTimeout(() => {
          // Close the connection
          closeSSEConnection()

          // After 1 second, close the dialog and start the refresh
          setTimeout(() => {
            dialogVisible.value = false
            sseConnecting.value = false

            // Show a different message for a re-login
            ElMessage.success(dialogType.value === 'edit' ? 'Logged in again' : 'Account added')

            // Show the "updating account info" message
            ElMessage({
              type: 'info',
              message: 'Syncing account info...',
              duration: 0
            })

            // Trigger the refresh
            fetchAccounts().then(() => {
              // Close the message when the refresh is done
              ElMessage.closeAll()
              ElMessage.success('Account info updated')
            })
          }, 1000)
        }, 1000)
      } else {
        // Login failed, close the connection
        closeSSEConnection()

        // Reset the state after 2 seconds so the user can retry
        setTimeout(() => {
          sseConnecting.value = false
          qrCodeData.value = ''
          loginStatus.value = ''
        }, 2000)
      }
    }
  }

  // Listen for errors
  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error)
    ElMessage.error('Could not connect to the server, please try again later')
    closeSSEConnection()
    sseConnecting.value = false
  }
}

// Submit the account form
const submitAccountForm = () => {
  accountFormRef.value.validate(async (valid) => {
    if (valid) {
      if (dialogType.value === 'add') {
        // Open the SSE connection
        connectSSE(accountForm.platform, accountForm.name)
      } else {
        // Edit the account
        try {
          // Convert the platform name to its type number
          const platformTypeMap = {
            '小红书': 1,
            '视频号': 2,
            '抖音': 3,
            '快手': 4
          };
          const type = platformTypeMap[accountForm.platform] || 1;

          const res = await accountApi.updateAccount({
            id: accountForm.id,
            type: type,
            userName: accountForm.name
          })
          if (res.code === 200) {
            // Update the account in the store
            const updatedAccount = {
              id: accountForm.id,
              name: accountForm.name,
              platform: accountForm.platform,
              status: accountForm.status // Keep the existing status
            };
            accountStore.updateAccount(accountForm.id, updatedAccount)
            ElMessage.success('Updated')
            dialogVisible.value = false
            // Refresh the account list
            fetchAccounts()
          } else {
            ElMessage.error(res.msg || 'Failed to update account')
          }
        } catch (error) {
          console.error('Failed to update account:', error)
          ElMessage.error('Failed to update account')
        }
      }
    } else {
      return false
    }
  })
}

// Close the SSE connection before the component unmounts
onBeforeUnmount(() => {
  closeSSEConnection()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.account-management {
  .page-header {
    margin-bottom: 20px;
    
    h1 {
      font-size: 24px;
      color: $text-primary;
      margin: 0;
    }
  }
  
  .account-tabs {
    background-color: #fff;
    border-radius: 4px;
    box-shadow: $box-shadow-light;
    
    .account-tabs-nav {
      padding: 20px;
    }
  }
  
  .account-list-container {
    .account-search {
      display: flex;
      justify-content: space-between;
      margin-bottom: 20px;
      
      .el-input {
        width: 300px;
      }
      
      .action-buttons {
        display: flex;
        gap: 10px;
        
        .el-icon.is-loading {
          animation: rotate 1s linear infinite;
        }
      }
    }
    
    .account-list {
      margin-bottom: 20px;
    }
    
    .empty-data {
      padding: 40px 0;
    }
  }
  
  // QR code container styles
  .clickable-status {
    cursor: pointer;
    transition: all 0.3s;

    &:hover {
      transform: scale(1.05);
      box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
    }
  }

  .qrcode-container {
    margin-top: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 250px;
    
    .qrcode-wrapper {
      text-align: center;
      
      .qrcode-tip {
        margin-bottom: 15px;
        color: #606266;
      }
      
      .qrcode-image {
        max-width: 200px;
        max-height: 200px;
        border: 1px solid #ebeef5;
        background-color: black;
      }
    }
    
    .loading-wrapper, .success-wrapper, .error-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 10px;
      
      .el-icon {
        font-size: 48px;
        
        &.is-loading {
          animation: rotate 1s linear infinite;
        }
      }
      
      span {
        font-size: 16px;
      }
    }
    
    .success-wrapper .el-icon {
      color: #67c23a;
    }
    
    .error-wrapper .el-icon {
      color: #f56c6c;
    }
  }
}
</style>