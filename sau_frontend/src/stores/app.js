import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  // Whether this is the first visit to the account management page
  const isFirstTimeAccountManagement = ref(true)
  
  // Whether this is the first visit to the material management page
  const isFirstTimeMaterialManagement = ref(true)

  // Refresh state of the account management page
  const isAccountRefreshing = ref(false)

  // Material list data
  const materials = ref([])
  
  // Mark the account management page as visited
  const setAccountManagementVisited = () => {
    isFirstTimeAccountManagement.value = false
  }
  
  // Mark the material management page as visited
  const setMaterialManagementVisited = () => {
    isFirstTimeMaterialManagement.value = false
  }
  
  // Reset all visit states (on re-login or app refresh)
  const resetVisitStatus = () => {
    isFirstTimeAccountManagement.value = true
    isFirstTimeMaterialManagement.value = true
  }

  // Update the material list
  const setMaterials = (materialList) => {
    materials.value = materialList
  }

  // Add a new material
  const addMaterial = (material) => {
    materials.value.push(material)
  }

  // Delete a material
  const removeMaterial = (materialId) => {
    const index = materials.value.findIndex(m => m.id === materialId)
    if (index > -1) {
      materials.value.splice(index, 1)
    }
  }
  
  // Set the refresh state of the account management page
  const setAccountRefreshing = (status) => {
    isAccountRefreshing.value = status
  }

  return {
    isFirstTimeAccountManagement,
    isFirstTimeMaterialManagement,
    isAccountRefreshing,
    materials,
    setAccountManagementVisited,
    setMaterialManagementVisited,
    resetVisitStatus,
    setMaterials,
    addMaterial,
    removeMaterial,
    setAccountRefreshing
  }
})