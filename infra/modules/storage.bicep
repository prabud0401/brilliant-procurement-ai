@description('Environment name')
param env string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Storage account name (3-24 lowercase alphanumeric)')
param storageAccountName string = 'stpda${replace(env, '-', '')}uaen'

@description('Principal ID of user-assigned managed identity')
param managedIdentityPrincipalId string

// Built-in role: Storage Blob Data Contributor (ba92f5b4-2d11-453d-a403-e96b0029c9fe)
var storageBlobDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
)

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: false // Entra ID / Managed Identity only
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

resource documentsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'documents'
  properties: {
    publicAccess: 'None'
  }
}

resource roleAssignmentBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentityPrincipalId, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output primaryBlobEndpoint string = storageAccount.properties.primaryEndpoints.blob
output containerName string = documentsContainer.name
