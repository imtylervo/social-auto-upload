<template>
  <div class="material-management">
    <div class="page-header">
      <h1>Material Management</h1>
    </div>
    
    <div class="material-list-container">
      <div class="material-search">
        <el-input
          v-model="searchKeyword"
          placeholder="Search by file name"
          prefix-icon="Search"
          clearable
          @clear="handleSearch"
          @input="handleSearch"
        />
        <div class="action-buttons">
          <el-button type="primary" @click="handleUploadMaterial">Upload Material</el-button>
          <el-button type="info" @click="fetchMaterials" :loading="false">
            <el-icon :class="{ 'is-loading': isRefreshing }"><Refresh /></el-icon>
            <span v-if="isRefreshing">Refreshing</span>
          </el-button>
        </div>
      </div>
      
      <div v-if="filteredMaterials.length > 0" class="material-list">
        <el-table :data="filteredMaterials" style="width: 100%">
          <el-table-column prop="uuid" label="UUID" width="180" />
          <el-table-column prop="filename" label="File Name" width="300" />
          <el-table-column prop="filesize" label="File Size" width="120">
            <template #default="scope">
              {{ scope.row.filesize }} MB
            </template>
          </el-table-column>
          <el-table-column prop="upload_time" label="Uploaded At" width="180" />
          <el-table-column label="Actions">
            <template #default="scope">
              <el-button size="small" @click="handlePreview(scope.row)">Preview</el-button>
              <el-button size="small" type="danger" @click="handleDelete(scope.row)">Delete</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      
      <div v-else class="empty-data">
        <el-empty description="No materials yet" />
      </div>
    </div>
    
    <!-- Upload dialog -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="Upload Material"
      width="40%"
      @close="handleUploadDialogClose"
    >
      <div class="upload-form">
        <el-form label-width="80px">
          <el-form-item label="File name:">
            <el-input
              v-model="customFilename"
              placeholder="Optional (single file only)"
              :disabled="customFilenameDisabled"
              clearable
            />
          </el-form-item>
          <el-form-item label="Files">
            <el-upload
              class="upload-demo"
              drag
              multiple
              :auto-upload="false"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              :file-list="fileList"
            >
              <el-icon class="el-icon--upload"><Upload /></el-icon>
              <div class="el-upload__text">
                Drop files here, or <em>click to upload</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  Supports video, image and other files. Several files can be selected at once.
                </div>
              </template>
            </el-upload>
          </el-form-item>
          <el-form-item label="Upload list" v-if="fileList.length > 0">
            <div class="upload-file-list">
              <div v-for="file in fileList" :key="file.uid" class="upload-file-item">
                <span class="file-name">{{ file.name }}</span>
                <el-progress
                  :percentage="uploadProgress[file.uid]?.percentage || 0"
                  :text-inside="true"
                  :stroke-width="20"
                  style="width: 100%; margin-top: 5px;"
                >
                  <span>{{ uploadProgress[file.uid]?.speed || '' }}</span>
                </el-progress>
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="uploadDialogVisible = false">Cancel</el-button>
          <el-button type="primary" @click="submitUpload" :loading="isUploading">
            {{ isUploading ? 'Uploading' : 'Upload' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
    
    <!-- Preview dialog -->
    <el-dialog
      v-model="previewDialogVisible"
      title="Material Preview"
      width="50%"
      :top="'10vh'"
    >
      <div class="preview-container" v-if="currentMaterial">
        <div v-if="isVideoFile(currentMaterial.filename)" class="video-preview">
          <video controls style="max-width: 100%; max-height: 60vh;">
            <source :src="getPreviewUrl(currentMaterial.file_path)" type="video/mp4">
            Your browser does not support video playback
          </video>
        </div>
        <div v-else-if="isImageFile(currentMaterial.filename)" class="image-preview">
          <img :src="getPreviewUrl(currentMaterial.file_path)" style="max-width: 100%; max-height: 60vh;" />
        </div>
        <div v-else class="file-info">
          <p>File name: {{ currentMaterial.filename }}</p>
          <p>File size: {{ currentMaterial.filesize }} MB</p>
          <p>Uploaded at: {{ currentMaterial.upload_time }}</p>
          <el-button type="primary" @click="downloadFile(currentMaterial)">Download File</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { Refresh, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { materialApi } from '@/api/material'
import { useAppStore } from '@/stores/app'

// App store
const appStore = useAppStore()

// Search and state flags
const searchKeyword = ref('')
const isRefreshing = ref(false)
const isUploading = ref(false)

// Dialog flags
const uploadDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const currentMaterial = ref(null)

// File upload
const fileList = ref([])
const customFilename = ref('')
const customFilenameDisabled = computed(() => fileList.value.length > 1)
const uploadProgress = ref({}); // { [uid]: { percentage: 0, speed: '' } }


watch(fileList, (newList) => {
  if (newList.length <= 1) {
    // If you want to clear the custom name when going back to single file, uncomment below
    // customFilename.value = ''
  }
});


// Fetch the material list
const fetchMaterials = async () => {
  isRefreshing.value = true
  try {
    const response = await materialApi.getAllMaterials()
    
    if (response.code === 200) {
      appStore.setMaterials(response.data)
      ElMessage.success('Refreshed')
    } else {
      ElMessage.error('Failed to fetch the material list')
    }
  } catch (error) {
    console.error('Error fetching the material list:', error)
    ElMessage.error('Failed to fetch the material list')
  } finally {
    isRefreshing.value = false
  }
}

// Filter the materials
const filteredMaterials = computed(() => {
  if (!searchKeyword.value) return appStore.materials
  
  const keyword = searchKeyword.value.toLowerCase()
  return appStore.materials.filter(material => 
    material.filename.toLowerCase().includes(keyword)
  )
})

// Search handler
const handleSearch = () => {
  // The search logic lives in the computed property
}

// Upload materials
const handleUploadMaterial = () => {
  // Reset the variables
  fileList.value = []
  customFilename.value = ''
  uploadProgress.value = {};
  uploadDialogVisible.value = true
}

// Reset the variables when the upload dialog closes
const handleUploadDialogClose = () => {
  fileList.value = []
  customFilename.value = ''
  uploadProgress.value = {};
}

// File selection changed
const handleFileChange = (file, uploadFileList) => {
  fileList.value = uploadFileList;
  const newProgress = {};
  for (const f of uploadFileList) {
    newProgress[f.uid] = { percentage: 0, speed: '' };
  }
  uploadProgress.value = newProgress;
}

const handleFileRemove = (file, uploadFileList) => {
  fileList.value = uploadFileList;
  const newProgress = { ...uploadProgress.value };
  delete newProgress[file.uid];
  uploadProgress.value = newProgress;
}

// Submit the upload
const submitUpload = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('Select the files to upload')
    return
  }
  
  isUploading.value = true
  
  for (const file of fileList.value) {
    try {
      // Make sure the file object exists
      if (!file || !file.raw) {
        ElMessage.warning(`File ${file.name} is not a valid file object, skipped`)
        continue
      }
      
      const formData = new FormData()
      formData.append('file', file.raw)
      
      // The custom file name only applies when there is a single file
      if (fileList.value.length === 1 && customFilename.value.trim()) {
        formData.append('filename', customFilename.value.trim())
      }
      
      let lastLoaded = 0;
      let lastTime = Date.now();

      const response = await materialApi.uploadMaterial(formData, (progressEvent) => {
        const progressData = uploadProgress.value[file.uid];
        if (!progressData) return;

        const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        progressData.percentage = progress;

        const currentTime = Date.now();
        const timeDiff = (currentTime - lastTime) / 1000; // in seconds
        const loadedDiff = progressEvent.loaded - lastLoaded;

        if (timeDiff > 0.5) { // Update speed every 0.5 seconds
          const speed = loadedDiff / timeDiff; // bytes per second
          if (speed > 1024 * 1024) {
            progressData.speed = (speed / (1024 * 1024)).toFixed(2) + ' MB/s';
          } else {
            progressData.speed = (speed / 1024).toFixed(2) + ' KB/s';
          }
          lastLoaded = progressEvent.loaded;
          lastTime = currentTime;
        }
      })
      
      if (response.code === 200) {
        ElMessage.success(`File ${file.name} uploaded`)
        const progressData = uploadProgress.value[file.uid];
        if(progressData) progressData.speed = 'Done';
      } else {
        ElMessage.error(`File ${file.name} upload failed: ${response.msg || 'unknown error'}`)
      }
    } catch (error) {
      console.error(`Error uploading file ${file.name}:`, error)
      ElMessage.error(`File ${file.name} upload failed: ${error.message || 'unknown error'}`)
    }
  }
  
  isUploading.value = false
  // Keep dialog open to show results
  // uploadDialogVisible.value = false 
  await fetchMaterials()
}

// Preview a material
const handlePreview = async (material) => {
  currentMaterial.value = null
  previewDialogVisible.value = true
  ElMessage.info('Loading...')
  try {
    // Wait a moment so the dialog is open
    await new Promise(resolve => setTimeout(resolve, 100))
    currentMaterial.value = material
  } catch (error) {
    console.error('Error previewing material:', error)
    ElMessage.error('Preview failed to load')
    previewDialogVisible.value = false
  }
}

// Delete a material
const handleDelete = (material) => {
  ElMessageBox.confirm(
    `Delete material ${material.filename}?`,
    'Warning',
    {
      confirmButtonText: 'OK',
      cancelButtonText: 'Cancel',
      type: 'warning',
    }
  )
    .then(async () => {
      try {
        const response = await materialApi.deleteMaterial(material.id)
        
        if (response.code === 200) {
          appStore.removeMaterial(material.id)
          ElMessage.success('Deleted')
        } else {
          ElMessage.error(response.msg || 'Delete failed')
        }
      } catch (error) {
        console.error('Error deleting material:', error)
        ElMessage.error('Delete failed')
      }
    })
    .catch(() => {
      // Delete cancelled
    })
}

// Get the preview URL
const getPreviewUrl = (filePath) => {
  const filename = filePath.split('/').pop()
  return materialApi.getMaterialPreviewUrl(filename)
}

// Download a file
const downloadFile = (material) => {
  const url = materialApi.downloadMaterial(material.file_path)
  window.open(url, '_blank')
}

// File type checks
const isVideoFile = (filename) => {
  const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv']
  return videoExtensions.some(ext => filename.toLowerCase().endsWith(ext))
}

const isImageFile = (filename) => {
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
  return imageExtensions.some(ext => filename.toLowerCase().endsWith(ext))
}

// Fetch the material list when the component mounts
onMounted(() => {
  // Only fetch when the store has no data
  if (appStore.materials.length === 0) {
    fetchMaterials()
  }
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

.material-management {
  
  .page-header {
    margin-bottom: 20px;
    
    h1 {
      font-size: 24px;
      font-weight: 500;
      color: $text-primary;
      margin: 0;
    }
  }
  
  .material-list-container {
    background-color: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;
    
    .material-search {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      
      .el-input {
        width: 300px;
      }
      
      .action-buttons {
        display: flex;
        gap: 10px;
        
        .is-loading {
          animation: rotate 1s linear infinite;
        }
      }
    }
    
    .material-list {
      margin-top: 20px;
    }
    
    .empty-data {
      padding: 40px 0;
    }
  }
  
  .material-upload {
    width: 100%;
  }
  
  .preview-container {
    display: flex;
    justify-content: center;
    align-items: center;
    flex-direction: column;
    padding: 0 20px;
    
    .file-info {
      text-align: center;
      margin-top: 20px;
    }
  }
}

.upload-form {
  padding: 0 20px;
  
  .form-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 5px;
  }
  
  .upload-demo {
    width: 100%;
  }
}

.dialog-footer {
  padding: 0 20px;
  display: flex;
  justify-content: flex-end;
}

.upload-file-list {
  width: 100%;
}

.upload-file-item {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
}

.upload-file-item .file-name {
  font-size: 14px;
  color: #606266;
  margin-bottom: 5px;
  display: block;
}

/* Override the Element Plus dialog styles */
:deep(.el-dialog__body) {
  padding: 20px 0;
}

:deep(.el-dialog__header) {
  padding-left: 20px;
  padding-right: 20px;
  margin-right: 0;
}

:deep(.el-dialog__footer) {
  padding-top: 10px;
  padding-bottom: 15px;
}

/* Upload progress bar styles */
:deep(.el-progress__text) {
  color: #303133 !important; /* dark gray text, readable on any background */
  font-size: 12px;
}

:deep(.el-progress--line) {
  margin-bottom: 10px;
}

.upload-file-item {
  border: 1px solid #dcdfe6;
  border-radius: 6px; /* rounded corners */
  padding: 12px; /* more padding */
  margin-bottom: 12px; /* more margin */
  background-color: #fafafa; /* light background */
  transition: box-shadow 0.3s; /* transition */
}

.upload-file-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); /* hover effect */
}

.upload-file-item .file-name {
  font-size: 14px;
  color: #303133; /* dark gray text */
  margin-bottom: 8px; /* more bottom spacing */
  display: block;
  font-weight: 500;
}
</style>
