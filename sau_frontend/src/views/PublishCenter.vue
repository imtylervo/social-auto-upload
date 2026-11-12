<template>
  <div class="publish-center">
    <!-- Tab management area -->
    <div class="tab-management">
      <div class="tab-header">
        <div class="tab-list">
          <div 
            v-for="tab in tabs" 
            :key="tab.name"
            :class="['tab-item', { active: activeTab === tab.name }]"
            @click="activeTab = tab.name"
          >
            <span>{{ tab.label }}</span>
            <el-icon 
              v-if="tabs.length > 1"
              class="close-icon" 
              @click.stop="removeTab(tab.name)"
            >
              <Close />
            </el-icon>
          </div>
        </div>
        <div class="tab-actions">
          <el-button 
            type="primary" 
            size="small" 
            @click="addTab"
            class="add-tab-btn"
          >
            <el-icon><Plus /></el-icon>
            Add Tab
          </el-button>
          <el-button 
            type="success" 
            size="small" 
            @click="batchPublish"
            :loading="batchPublishing"
            class="batch-publish-btn"
          >
            Batch Publish
          </el-button>
        </div>
      </div>
    </div>

    <!-- Content area -->
    <div class="publish-content">
      <div class="tab-content-wrapper">
        <div 
          v-for="tab in tabs" 
          :key="tab.name"
          v-show="activeTab === tab.name"
          class="tab-content"
        >
          <!-- Publish status notice -->
          <div v-if="tab.publishStatus" class="publish-status">
            <el-alert
              :title="tab.publishStatus.message"
              :type="tab.publishStatus.type"
              :closable="false"
              show-icon
            />
          </div>

          <!-- Video upload area -->
          <div class="upload-section">
            <h3>Video</h3>
            <div class="upload-options">
              <el-button type="primary" @click="showUploadOptions(tab)" class="upload-btn">
                <el-icon><Upload /></el-icon>
                Upload Video
              </el-button>
            </div>
            
            <!-- Uploaded file list -->
            <div v-if="tab.fileList.length > 0" class="uploaded-files">
              <h4>Uploaded files:</h4>
              <div class="file-list">
                <div v-for="(file, index) in tab.fileList" :key="index" class="file-item">
                  <el-link :href="file.url" target="_blank" type="primary">{{ file.name }}</el-link>
                  <span class="file-size">{{ (file.size / 1024 / 1024).toFixed(2) }}MB</span>
                  <el-button type="danger" size="small" @click="removeFile(tab, index)">Delete</el-button>
                </div>
              </div>
            </div>
          </div>

          <!-- Upload options dialog -->
          <el-dialog
            v-model="uploadOptionsVisible"
            title="Choose Upload Method"
            width="400px"
            class="upload-options-dialog"
          >
            <div class="upload-options-content">
              <el-button type="primary" @click="selectLocalUpload" class="option-btn">
                <el-icon><Upload /></el-icon>
                Local Upload
              </el-button>
              <el-button type="success" @click="selectMaterialLibrary" class="option-btn">
                <el-icon><Folder /></el-icon>
                Material Library
              </el-button>
            </div>
          </el-dialog>

          <!-- Local upload dialog -->
          <el-dialog
            v-model="localUploadVisible"
            title="Local Upload"
            width="600px"
            class="local-upload-dialog"
          >
            <el-upload
              class="video-upload"
              drag
              :auto-upload="true"
              :action="`${apiBaseUrl}/upload`"
              :on-success="(response, file) => handleUploadSuccess(response, file, currentUploadTab)"
              :on-error="handleUploadError"
              multiple
              accept="video/*"
              :headers="authHeaders"
            >
              <el-icon class="el-icon--upload"><Upload /></el-icon>
              <div class="el-upload__text">
                Drop video files here, or <em>click to upload</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  Supports MP4, AVI and other video formats. Multiple files allowed.
                </div>
              </template>
            </el-upload>
          </el-dialog>

          <!-- Batch publish progress dialog -->
          <el-dialog
            v-model="batchPublishDialogVisible"
            title="Batch Publish Progress"
            width="500px"
            :close-on-click-modal="false"
            :close-on-press-escape="false"
            :show-close="false"
          >
            <div class="publish-progress">
              <el-progress 
                :percentage="publishProgress"
                :status="publishProgress === 100 ? 'success' : ''"
              />
              <div v-if="currentPublishingTab" class="current-publishing">
                Publishing: {{ currentPublishingTab.label }}
              </div>
              
              <!-- Publish results -->
              <div class="publish-results" v-if="publishResults.length > 0">
                <div 
                  v-for="(result, index) in publishResults" 
                  :key="index"
                  :class="['result-item', result.status]"
                >
                  <el-icon v-if="result.status === 'success'"><Check /></el-icon>
                  <el-icon v-else-if="result.status === 'error'"><Close /></el-icon>
                  <el-icon v-else><InfoFilled /></el-icon>
                  <span class="label">{{ result.label }}</span>
                  <span class="message">{{ result.message }}</span>
                </div>
              </div>
            </div>
            
            <template #footer>
              <div class="dialog-footer">
                <el-button 
                  @click="cancelBatchPublish" 
                  :disabled="publishProgress === 100"
                >
                  Cancel Publishing
                </el-button>
                <el-button 
                  type="primary" 
                  @click="batchPublishDialogVisible = false"
                  v-if="publishProgress === 100"
                >
                  Close
                </el-button>
              </div>
            </template>
          </el-dialog>

          <!-- Material library dialog -->
          <el-dialog
            v-model="materialLibraryVisible"
            title="Select Materials"
            width="800px"
            class="material-library-dialog"
          >
            <div class="material-library-content">
              <el-checkbox-group v-model="selectedMaterials">
                <div class="material-list">
                  <div
                    v-for="material in materials"
                    :key="material.id"
                    class="material-item"
                  >
                    <el-checkbox :label="material.id" class="material-checkbox">
                      <div class="material-info">
                        <div class="material-name">{{ material.filename }}</div>
                        <div class="material-details">
                          <span class="file-size">{{ material.filesize }}MB</span>
                          <span class="upload-time">{{ material.upload_time }}</span>
                        </div>
                      </div>
                    </el-checkbox>
                  </div>
                </div>
              </el-checkbox-group>
            </div>
            <template #footer>
              <div class="dialog-footer">
                <el-button @click="materialLibraryVisible = false">Cancel</el-button>
                <el-button type="primary" @click="confirmMaterialSelection">OK</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- Account selection -->
          <div class="account-section">
            <h3>Accounts</h3>
            <div class="account-display">
              <div class="selected-accounts">
                <el-tag
                  v-for="(account, index) in tab.selectedAccounts"
                  :key="index"
                  closable
                  @close="removeAccount(tab, index)"
                  class="account-tag"
                >
                  {{ getAccountDisplayName(account) }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openAccountDialog(tab)"
                class="select-account-btn"
              >
                Select Accounts
              </el-button>
            </div>
          </div>

          <!-- Account selection dialog -->
          <el-dialog
            v-model="accountDialogVisible"
            title="Select Accounts"
            width="600px"
            class="account-dialog"
          >
            <div class="account-dialog-content">
              <el-checkbox-group v-model="tempSelectedAccounts">
                <div class="account-list">
                  <el-checkbox
                    v-for="account in availableAccounts"
                    :key="account.id"
                    :label="account.id"
                    class="account-item"
                  >
                    <div class="account-info">
                      <span class="account-name">{{ account.name }}</span>                      
                    </div>
                  </el-checkbox>
                </div>
              </el-checkbox-group>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="accountDialogVisible = false">Cancel</el-button>
                <el-button type="primary" @click="confirmAccountSelection">OK</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- Platform selection -->
          <div class="platform-section">
            <h3>Platform</h3>
            <el-radio-group v-model="tab.selectedPlatform" class="platform-radios">
              <el-radio 
                v-for="platform in platforms" 
                :key="platform.key"
                :label="platform.key"
                class="platform-radio"
              >
                {{ platform.name }}
              </el-radio>
            </el-radio-group>
          </div>

          <!-- Original content declaration -->
          <div class="original-section">
            <el-checkbox
              v-model="tab.isOriginal"
              label="Declare as original"
              class="original-checkbox"
            />
          </div>

          <!-- Draft option (WeChat Channels only) -->
          <div v-if="tab.selectedPlatform === 2" class="draft-section">
            <el-checkbox
              v-model="tab.isDraft"
              label="WeChat Channels: save as draft only (publish from phone)"
              class="draft-checkbox"
            />
          </div>

          <!-- Tags (Douyin only) -->
          <div v-if="tab.selectedPlatform === 3" class="product-section">
            <h3>Product Link</h3>
            <el-input
              v-model="tab.productTitle"
              type="text"
              :rows="1"
              placeholder="Enter the product name"
              maxlength="200"
              class="product-name-input"
            />
            <el-input
              v-model="tab.productLink"
              type="text"
              :rows="1"
              placeholder="Enter the product link"
              maxlength="200"
              class="product-link-input"
            />
          </div>

          <!-- Title input -->
          <div class="title-section">
            <h3>Title</h3>
            <el-input
              v-model="tab.title"
              type="textarea"
              :rows="3"
              placeholder="Enter a title"
              maxlength="100"
              show-word-limit
              class="title-input"
            />
          </div>

          <!-- Topic input -->
          <div class="topic-section">
            <h3>Topics</h3>
            <div class="topic-display">
              <div class="selected-topics">
                <el-tag
                  v-for="(topic, index) in tab.selectedTopics"
                  :key="index"
                  closable
                  @close="removeTopic(tab, index)"
                  class="topic-tag"
                >
                  #{{ topic }}
                </el-tag>
              </div>
              <el-button 
                type="primary" 
                plain 
                @click="openTopicDialog(tab)"
                class="select-topic-btn"
              >
                Add Topic
              </el-button>
            </div>
          </div>

          <!-- Add topic dialog -->
          <el-dialog
            v-model="topicDialogVisible"
            title="Add Topic"
            width="600px"
            class="topic-dialog"
          >
            <div class="topic-dialog-content">
              <!-- Custom topic input -->
              <div class="custom-topic-input">
                <el-input
                  v-model="customTopic"
                  placeholder="Enter a custom topic"
                  class="custom-input"
                >
                  <template #prepend>#</template>
                </el-input>
                <el-button type="primary" @click="addCustomTopic">Add</el-button>
              </div>

              <!-- Recommended topics -->
              <div class="recommended-topics">
                <h4>Recommended Topics</h4>
                <div class="topic-grid">
                  <el-button
                    v-for="topic in recommendedTopics"
                    :key="topic"
                    :type="currentTab?.selectedTopics?.includes(topic) ? 'primary' : 'default'"
                    @click="toggleRecommendedTopic(topic)"
                    class="topic-btn"
                  >
                    {{ topic }}
                  </el-button>
                </div>
              </div>
            </div>

            <template #footer>
              <div class="dialog-footer">
                <el-button @click="topicDialogVisible = false">Cancel</el-button>
                <el-button type="primary" @click="confirmTopicSelection">OK</el-button>
              </div>
            </template>
          </el-dialog>

          <!-- Scheduled publishing -->
          <div class="schedule-section">
            <h3>Scheduled Publishing</h3>
            <div class="schedule-controls">
              <el-switch
                v-model="tab.scheduleEnabled"
                active-text="Scheduled"
                inactive-text="Publish now"
              />
              <div v-if="tab.scheduleEnabled" class="schedule-settings">
                <div class="schedule-item">
                  <span class="label">Videos per day:</span>
                  <el-select v-model="tab.videosPerDay" placeholder="Select a count">
                    <el-option
                      v-for="num in 55"
                      :key="num"
                      :label="num"
                      :value="num"
                    />
                  </el-select>
                </div>
                <div class="schedule-item">
                  <span class="label">Daily publish times:</span>
                  <el-time-select
                    v-for="(time, index) in tab.dailyTimes"
                    :key="index"
                    v-model="tab.dailyTimes[index]"
                    start="00:00"
                    step="00:30"
                    end="23:30"
                    placeholder="Select a time"
                  />
                  <el-button
                    v-if="tab.dailyTimes.length < tab.videosPerDay"
                    type="primary"
                    size="small"
                    @click="tab.dailyTimes.push('10:00')"
                  >
                    Add Time
                  </el-button>
                </div>
                <div class="schedule-item">
                  <span class="label">Start day:</span>
                  <el-select v-model="tab.startDays" placeholder="Select the start day">
                    <el-option :label="'Tomorrow'" :value="0" />
                    <el-option :label="'Day after tomorrow'" :value="1" />
                  </el-select>
                </div>
              </div>
            </div>
          </div>

          <!-- Action buttons -->
          <div class="action-buttons">
            <el-button size="small" @click="cancelPublish(tab)">Cancel</el-button>
            <el-button
              size="small"
              type="primary"
              @click="confirmPublish(tab)"
              :loading="tab.publishing || false"
            >
              {{ tab.publishing ? 'Publishing...' : 'Publish' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { Upload, Plus, Close, Folder } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAccountStore } from '@/stores/account'
import { useAppStore } from '@/stores/app'
import { materialApi } from '@/api/material'
import { http } from '@/utils/request'

// API base URL
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5409'

// Authorization headers
const authHeaders = computed(() => ({
  'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
}))

// Currently active tab
const activeTab = ref('tab1')

// Tab counter
let tabCounter = 1

// App store
const appStore = useAppStore()

// Upload state
const uploadOptionsVisible = ref(false)
const localUploadVisible = ref(false)
const materialLibraryVisible = ref(false)
const currentUploadTab = ref(null)
const selectedMaterials = ref([])
const materials = computed(() => appStore.materials)

// Batch publish state
const batchPublishing = ref(false)
const batchPublishMessage = ref('')
const batchPublishType = ref('info')

// Platform list - key is the backend type field
const platforms = [
  { key: 3, name: 'Douyin' },
  { key: 4, name: 'Kuaishou' },
  { key: 2, name: 'WeChat Channels' },
  { key: 1, name: 'Xiaohongshu' }
]

const defaultTabInit = {
  name: 'tab1',
  label: 'Publish 1',
  fileList: [], // File names returned by the backend
  displayFileList: [], // File list for display
  selectedAccounts: [], // Selected account IDs
  selectedPlatform: 1, // Selected platform (single choice)
  title: '',
  productLink: '', // Product link
  productTitle: '', // Product name
  selectedTopics: [], // Topic list (without #)
  scheduleEnabled: false, // Scheduled publishing on/off
  videosPerDay: 1, // Number of videos published per day
  dailyTimes: ['10:00'], // Publish times of each day
  startDays: 0, // Start day counted from today: 0 = tomorrow, 1 = the day after tomorrow
  publishStatus: null, // Publish status, with message and type
  publishing: false, // Publishing flag, drives the button loading state
  isDraft: false, // Save as draft; shown for WeChat Channels only
  isOriginal: false // Mark as original
}

// helper to create a fresh deep-copied tab from defaultTabInit
const makeNewTab = () => {
  // prefer structuredClone when available (newer browsers/node), fallback to JSON
  try {
    return typeof structuredClone === 'function' ? structuredClone(defaultTabInit) : JSON.parse(JSON.stringify(defaultTabInit))
  } catch (e) {
    return JSON.parse(JSON.stringify(defaultTabInit))
  }
}

// Tab data - one tab by default (use deep copy to avoid shared refs)
const tabs = reactive([
  makeNewTab()
])

// Account state
const accountDialogVisible = ref(false)
const tempSelectedAccounts = ref([])
const currentTab = ref(null)

// Account store
const accountStore = useAccountStore()

// Accounts available for the selected platform (the Chinese names match acc.platform from the account store)
const availableAccounts = computed(() => {
  const platformMap = {
    3: '抖音',
    2: '视频号',
    1: '小红书',
    4: '快手'
  }
  const currentPlatform = currentTab.value ? platformMap[currentTab.value.selectedPlatform] : null
  return currentPlatform ? accountStore.accounts.filter(acc => acc.platform === currentPlatform) : []
})

// Topic state
const topicDialogVisible = ref(false)
const customTopic = ref('')

// Recommended topics (kept in Chinese: they are sent to the platforms as tags)
const recommendedTopics = [
  '游戏', '电影', '音乐', '美食', '旅行', '文化',
  '科技', '生活', '娱乐', '体育', '教育', '艺术',
  '健康', '时尚', '美妆', '摄影', '宠物', '汽车'
]

// Add a new tab
const addTab = () => {
  tabCounter++
  const newTab = makeNewTab()
  newTab.name = `tab${tabCounter}`
  newTab.label = `Publish ${tabCounter}`
  tabs.push(newTab)
  activeTab.value = newTab.name
}

// Remove a tab
const removeTab = (tabName) => {
  const index = tabs.findIndex(tab => tab.name === tabName)
  if (index > -1) {
    tabs.splice(index, 1)
    // If the removed tab was the active one, switch to the first tab
    if (activeTab.value === tabName && tabs.length > 0) {
      activeTab.value = tabs[0].name
    }
  }
}

// Handle a successful file upload
const handleUploadSuccess = (response, file, tab) => {
  if (response.code === 200) {
    // Get the file path
    const filePath = response.data.path || response.data
    // Extract the file name from the path
    const filename = filePath.split('/').pop()
    
    // Save the file info (path and other details) to fileList
    const fileInfo = {
      name: file.name,
      url: materialApi.getMaterialPreviewUrl(filename), // Build the preview URL with getMaterialPreviewUrl
      path: filePath,
      size: file.size,
      type: file.type
    }
    
    // Add to the file list
    tab.fileList.push(fileInfo)
    
    // Update the display list
    tab.displayFileList = [...tab.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
    
    ElMessage.success('File uploaded')
  } else {
    ElMessage.error(response.msg || 'Upload failed')
  }
}

// Handle a failed file upload
const handleUploadError = (error) => {
  ElMessage.error('File upload failed')
}

// Remove an uploaded file
const removeFile = (tab, index) => {
  // Remove it from the file list
  tab.fileList.splice(index, 1)
  
  // Update the display list
  tab.displayFileList = [...tab.fileList.map(item => ({
    name: item.name,
    url: item.url
  }))]
  
  ElMessage.success('File removed')
}

// Topic methods
// Open the add topic dialog
const openTopicDialog = (tab) => {
  currentTab.value = tab
  topicDialogVisible.value = true
}

// Add a custom topic
const addCustomTopic = () => {
  if (!customTopic.value.trim()) {
    ElMessage.warning('Enter a topic')
    return
  }
  if (currentTab.value && !currentTab.value.selectedTopics.includes(customTopic.value.trim())) {
    currentTab.value.selectedTopics.push(customTopic.value.trim())
    customTopic.value = ''
    ElMessage.success('Topic added')
  } else {
    ElMessage.warning('Topic already exists')
  }
}

// Toggle a recommended topic
const toggleRecommendedTopic = (topic) => {
  if (!currentTab.value) return
  
  const index = currentTab.value.selectedTopics.indexOf(topic)
  if (index > -1) {
    currentTab.value.selectedTopics.splice(index, 1)
  } else {
    currentTab.value.selectedTopics.push(topic)
  }
}

// Remove a topic
const removeTopic = (tab, index) => {
  tab.selectedTopics.splice(index, 1)
}

// Confirm the topics
const confirmTopicSelection = () => {
  topicDialogVisible.value = false
  customTopic.value = ''
  currentTab.value = null
  ElMessage.success('Topics added')
}

// Account selection methods
// Open the account selection dialog
const openAccountDialog = (tab) => {
  currentTab.value = tab
  tempSelectedAccounts.value = [...tab.selectedAccounts]
  accountDialogVisible.value = true
}

// Confirm the account selection
const confirmAccountSelection = () => {
  if (currentTab.value) {
    currentTab.value.selectedAccounts = [...tempSelectedAccounts.value]
  }
  accountDialogVisible.value = false
  currentTab.value = null
  ElMessage.success('Accounts selected')
}

// Remove a selected account
const removeAccount = (tab, index) => {
  tab.selectedAccounts.splice(index, 1)
}

// Display name of an account
const getAccountDisplayName = (accountId) => {
  const account = accountStore.accounts.find(acc => acc.id === accountId)
  return account ? account.name : accountId
}

// Cancel publishing
const cancelPublish = (tab) => {
  ElMessage.info('Publishing cancelled')
}

// Confirm and publish
const confirmPublish = async (tab) => {
  // Prevent double clicks
  if (tab.publishing) {
    throw new Error('Publishing in progress, please wait...')
  }

  tab.publishing = true // Mark publishing as in progress

  // Validate the data
  if (tab.fileList.length === 0) {
    ElMessage.error('Upload a video file first')
    tab.publishing = false
    throw new Error('Upload a video file first')
  }
  if (!tab.title.trim()) {
    ElMessage.error('Enter a title')
    tab.publishing = false
    throw new Error('Enter a title')
  }
  if (!tab.selectedPlatform) {
    ElMessage.error('Select a platform to publish to')
    tab.publishing = false
    throw new Error('Select a platform to publish to')
  }
  if (tab.selectedAccounts.length === 0) {
    ElMessage.error('Select the accounts to publish with')
    tab.publishing = false
    throw new Error('Select the accounts to publish with')
  }

  // Build the publish payload in the backend API format
  const publishData = {
    type: tab.selectedPlatform,
    title: tab.title,
    tags: tab.selectedTopics, // Topic list without #
    fileList: tab.fileList.map(file => file.path), // Send only the file paths
    accountList: tab.selectedAccounts.map(accountId => {
      const account = accountStore.accounts.find(acc => acc.id === accountId)
      return account ? account.filePath : accountId
    }), // Send the cookie file paths of the accounts
    enableTimer: tab.scheduleEnabled ? 1 : 0,
    videosPerDay: tab.scheduleEnabled ? tab.videosPerDay || 1 : 1,
    dailyTimes: tab.scheduleEnabled ? tab.dailyTimes || ['10:00'] : ['10:00'],
    startDays: tab.scheduleEnabled ? tab.startDays || 0 : 0,
    category: tab.isOriginal ? 1 : 0, // 1 = original, 0 = not original
    productLink: tab.productLink.trim() || '',
    productTitle: tab.productTitle.trim() || '',
    isDraft: tab.isDraft
  }

  // Call the backend publish API (through the shared http wrapper)
  try {
    const data = await http.post('/postVideo', publishData)
    tab.publishStatus = {
      message: 'Published',
      type: 'success'
    }
    // Clear the data of the current tab
    tab.fileList = []
    tab.displayFileList = []
    tab.title = ''
    tab.selectedTopics = []
    tab.selectedAccounts = []
    tab.scheduleEnabled = false
  } catch (error) {
    console.error('Publish error:', error)
    tab.publishStatus = {
      message: `Publish failed: ${error.message || 'check your network connection'}`,
      type: 'error'
    }
    throw error
  } finally {
    tab.publishing = false
  }
}

// Show the upload options
const showUploadOptions = (tab) => {
  currentUploadTab.value = tab
  uploadOptionsVisible.value = true
}

// Choose local upload
const selectLocalUpload = () => {
  uploadOptionsVisible.value = false
  localUploadVisible.value = true
}

// Choose the material library
const selectMaterialLibrary = async () => {
  uploadOptionsVisible.value = false
  
  // If the material library is empty, fetch the materials first
  if (materials.value.length === 0) {
    try {
      const response = await materialApi.getAllMaterials()
      if (response.code === 200) {
        appStore.setMaterials(response.data)
      } else {
        ElMessage.error('Failed to fetch the material list')
        return
      }
    } catch (error) {
      console.error('Error fetching the material list:', error)
      ElMessage.error('Failed to fetch the material list')
      return
    }
  }
  
  selectedMaterials.value = []
  materialLibraryVisible.value = true
}

// Confirm the material selection
const confirmMaterialSelection = () => {
  if (selectedMaterials.value.length === 0) {
    ElMessage.warning('Select at least one material')
    return
  }
  
  if (currentUploadTab.value) {
    // Add the selected materials to the file list of the current tab
    selectedMaterials.value.forEach(materialId => {
      const material = materials.value.find(m => m.id === materialId)
      if (material) {
        const fileInfo = {
          name: material.filename,
          url: materialApi.getMaterialPreviewUrl(material.file_path.split('/').pop()),
          path: material.file_path,
          size: material.filesize * 1024 * 1024, // convert to bytes
          type: 'video/mp4'
        }
        
        // Check whether the same file is already there
        const exists = currentUploadTab.value.fileList.some(file => file.path === fileInfo.path)
        if (!exists) {
          currentUploadTab.value.fileList.push(fileInfo)
        }
      }
    })
    
    // Update the display list
    currentUploadTab.value.displayFileList = [...currentUploadTab.value.fileList.map(item => ({
      name: item.name,
      url: item.url
    }))]
  }
  
  const addedCount = selectedMaterials.value.length
  materialLibraryVisible.value = false
  selectedMaterials.value = []
  currentUploadTab.value = null
  ElMessage.success(`Added ${addedCount} material(s)`)
}

// Batch publish dialog state
const batchPublishDialogVisible = ref(false)
const currentPublishingTab = ref(null)
const publishProgress = ref(0)
const publishResults = ref([])
const isCancelled = ref(false)

// Cancel the batch publish
const cancelBatchPublish = () => {
  isCancelled.value = true
  ElMessage.info('Cancelling publishing...')
}

// Batch publish
const batchPublish = async () => {
  if (batchPublishing.value) return
  
  batchPublishing.value = true
  currentPublishingTab.value = null
  publishProgress.value = 0
  publishResults.value = []
  isCancelled.value = false
  batchPublishDialogVisible.value = true
  
  try {
    for (let i = 0; i < tabs.length; i++) {
      if (isCancelled.value) {
        publishResults.value.push({
          label: tabs[i].label,
          status: 'cancelled',
          message: 'Cancelled'
        })
        continue
      }

      const tab = tabs[i]
      currentPublishingTab.value = tab
      publishProgress.value = Math.floor((i / tabs.length) * 100)
      
      try {
        await confirmPublish(tab)
        publishResults.value.push({
          label: tab.label,
          status: 'success',
          message: 'Published'
        })
      } catch (error) {
        publishResults.value.push({
          label: tab.label,
          status: 'error',
          message: error.message
        })
        // Do not return yet, keep showing the publish results
      }
    }
    
    publishProgress.value = 100
    
    // Count the publish results
    const successCount = publishResults.value.filter(r => r.status === 'success').length
    const failCount = publishResults.value.filter(r => r.status === 'error').length
    const cancelCount = publishResults.value.filter(r => r.status === 'cancelled').length
    
    if (isCancelled.value) {
      ElMessage.warning(`Publishing cancelled: ${successCount} succeeded, ${failCount} failed, ${cancelCount} not run`)
    } else if (failCount > 0) {
      ElMessage.error(`Publishing done: ${successCount} succeeded, ${failCount} failed`)
    } else {
      ElMessage.success('All tabs published')
      setTimeout(() => {
        batchPublishDialogVisible.value = false
      }, 1000)
    }
    
  } catch (error) {
    console.error('Batch publish error:', error)
    ElMessage.error('Batch publish failed, please try again')
  } finally {
    batchPublishing.value = false
    isCancelled.value = false
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.publish-center {
  display: flex;
  flex-direction: column;
  height: 100%;
  
  // Tab management area
  .tab-management {
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
    padding: 15px 20px;
    
    .tab-header {
      display: flex;
      align-items: flex-start;
      gap: 15px;
      
      .tab-list {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        flex: 1;
        min-width: 0;
        
        .tab-item {
           display: flex;
           align-items: center;
           gap: 6px;
           padding: 6px 12px;
           background-color: #f5f7fa;
           border: 1px solid #dcdfe6;
           border-radius: 4px;
           cursor: pointer;
           transition: all 0.3s;
           font-size: 14px;
           height: 32px;
           
           &:hover {
             background-color: #ecf5ff;
             border-color: #b3d8ff;
           }
           
           &.active {
             background-color: #409eff;
             border-color: #409eff;
             color: #fff;
             
             .close-icon {
               color: #fff;
               
               &:hover {
                 background-color: rgba(255, 255, 255, 0.2);
               }
             }
           }
           
           .close-icon {
             padding: 2px;
             border-radius: 2px;
             cursor: pointer;
             transition: background-color 0.3s;
             font-size: 12px;
             
             &:hover {
               background-color: rgba(0, 0, 0, 0.1);
             }
           }
         }
       }
       
      .tab-actions {
        display: flex;
        gap: 10px;
        flex-shrink: 0;
        
        .add-tab-btn,
        .batch-publish-btn {
          display: flex;
          align-items: center;
          gap: 4px;
          height: 32px;
          padding: 6px 12px;
          font-size: 14px;
          white-space: nowrap;
        }
      }
    }
  }
  
  // Batch publish progress dialog styles
  .publish-progress {
    padding: 20px;
    
    .current-publishing {
      margin: 15px 0;
      text-align: center;
      color: #606266;
    }

    .publish-results {
      margin-top: 20px;
      border-top: 1px solid #EBEEF5;
      padding-top: 15px;
      max-height: 300px;
      overflow-y: auto;

      .result-item {
        display: flex;
        align-items: center;
        padding: 8px 0;
        color: #606266;

        .el-icon {
          margin-right: 8px;
        }

        .label {
          margin-right: 10px;
          font-weight: 500;
        }

        .message {
          color: #909399;
        }

        &.success {
          color: #67C23A;
        }

        &.error {
          color: #F56C6C;
        }

        &.cancelled {
          color: #909399;
        }
      }
    }
  }

  .dialog-footer {
    text-align: right;
  }
  
  // Content area
  .publish-content {
    flex: 1;
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;
    
    .tab-content-wrapper {
      display: flex;
      justify-content: center;
      
      .tab-content {
        width: 100%;
        max-width: 800px;
        
        h3 {
          font-size: 16px;
          font-weight: 500;
          color: $text-primary;
          margin: 0 0 10px 0;
        }
        
        .upload-section,
        .account-section,
        .platform-section,
        .title-section,
        .product-section,
        .topic-section,
        .schedule-section {
          margin-bottom: 30px;
        }

        .product-section {
          .product-name-input,
          .product-link-input {
            margin-bottom: 5px;
          }
        }
        
        .video-upload {
          width: 100%;
          
          :deep(.el-upload-dragger) {
            width: 100%;
            height: 180px;
          }
        }
        
        .account-input {
          max-width: 400px;
        }
        
        .platform-buttons {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
          
          .platform-btn {
            min-width: 80px;
          }
        }
        
        .title-input {
          max-width: 600px;
        }
        
        .topic-display {
          display: flex;
          flex-direction: column;
          gap: 12px;
          
          .selected-topics {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            min-height: 32px;
            
            .topic-tag {
              font-size: 14px;
            }
          }
          
          .select-topic-btn {
            align-self: flex-start;
          }
        }
        
        .schedule-controls {
          display: flex;
          flex-direction: column;
          gap: 15px;

          .schedule-settings {
            margin-top: 15px;
            padding: 15px;
            background-color: #f5f7fa;
            border-radius: 4px;

            .schedule-item {
              display: flex;
              align-items: center;
              margin-bottom: 15px;

              &:last-child {
                margin-bottom: 0;
              }

              .label {
                min-width: 120px;
                margin-right: 10px;
              }

              .el-time-select {
                margin-right: 10px;
              }

              .el-button {
                margin-left: 10px;
              }
            }
          }
        }
        
        .action-buttons {
          display: flex;
          justify-content: flex-end;
          gap: 10px;
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #ebeef5;
        }

        .draft-section {
          margin: 20px 0;

          .draft-checkbox {
            display: block;
            margin: 10px 0;
          }
        }

        .original-section {
          margin: 10px 0 20px;

          .original-checkbox {
            display: block;
            margin: 10px 0;
          }
        }
      }
    }
  }

  // Uploaded file list styles
  .uploaded-files {
    margin-top: 20px;
    
    h4 {
      font-size: 16px;
      font-weight: 500;
      margin-bottom: 12px;
      color: #303133;
    }
    
    .file-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      
      .file-item {
        display: flex;
        align-items: center;
        padding: 10px 15px;
        background-color: #f5f7fa;
        border-radius: 4px;
        
        .el-link {
          margin-right: 10px;
          max-width: 300px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        
        .file-size {
          color: #909399;
          font-size: 13px;
          margin-right: auto;
        }
      }
    }
  }
  
  // Add topic dialog styles
  .topic-dialog {
    .topic-dialog-content {
      .custom-topic-input {
        display: flex;
        gap: 12px;
        margin-bottom: 24px;
        
        .custom-input {
          flex: 1;
        }
      }
      
      .recommended-topics {
        h4 {
          margin: 0 0 16px 0;
          font-size: 16px;
          font-weight: 500;
          color: #303133;
        }
        
        .topic-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
          gap: 12px;
          
          .topic-btn {
            height: 36px;
            font-size: 14px;
            border-radius: 6px;
            min-width: 100px;
            padding: 0 12px;
            white-space: nowrap;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            
            &.el-button--primary {
              background-color: #409eff;
              border-color: #409eff;
              color: white;
            }
          }
        }
      }
    }
    
    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }
  }
}
</style>
