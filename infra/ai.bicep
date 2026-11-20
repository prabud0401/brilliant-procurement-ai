@description('Environment name (default: prod)')
param env string = 'prod'

@description('Azure region for deployment')
param location string = 'uaenorth'

@description('Resource tags')
param tags object = {
  project: 'brilliant-pda'
  env: env
  owner: 'prabudeva'
  expires: '2026-11-29'
}

@description('Azure OpenAI account name')
param openAiAccountName string = 'oai-pda-ai-uaen'

@description('Document Intelligence account name')
param documentIntelligenceAccountName string = 'di-pda-ai-uaen'

@description('Chat model name')
param chatModelName string = 'gpt-4o-mini'

@description('Chat model version')
param chatModelVersion string = '2024-07-18'

@description('Chat deployment SKU (GlobalStandard or Standard)')
param chatDeploymentSku string = 'GlobalStandard'

@description('Chat deployment capacity in thousands of TPM (e.g. 10 = 10k TPM)')
param chatDeploymentCapacity int = 10

@description('Embedding model name')
param embeddingModelName string = 'text-embedding-3-small'

@description('Embedding model version')
param embeddingModelVersion string = '1'

@description('Embedding deployment SKU (GlobalStandard or Standard)')
param embeddingDeploymentSku string = 'GlobalStandard'

@description('Embedding deployment capacity in thousands of TPM (e.g. 10 = 10k TPM)')
param embeddingDeploymentCapacity int = 10

@description('Principal ID of user-assigned managed identity to grant Cognitive Services User role (optional at G1)')
param managedIdentityPrincipalId string = ''

// Built-in role: Cognitive Services User (a97b65f3-24c7-4388-baec-2e87135dc908)
var cognitiveServicesUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

// Azure OpenAI account (S0)
resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiAccountName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiAccountName
    publicNetworkAccess: 'Enabled'
  }
}

// Chat deployment (gpt-4o-mini)
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: chatModelName
  sku: {
    name: chatDeploymentSku
    capacity: chatDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
  }
}

// Embedding deployment (text-embedding-3-small)
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAiAccount
  name: embeddingModelName
  sku: {
    name: embeddingDeploymentSku
    capacity: embeddingDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
  }
  dependsOn: [
    chatDeployment
  ]
}

// Document Intelligence account (F0)
resource documentIntelligenceAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: documentIntelligenceAccountName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  sku: {
    name: 'F0'
  }
  properties: {
    customSubDomainName: documentIntelligenceAccountName
    publicNetworkAccess: 'Enabled'
  }
}

// Optional role assignment for managed identity on Azure OpenAI
resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(managedIdentityPrincipalId)) {
  name: guid(openAiAccount.id, managedIdentityPrincipalId, 'CognitiveServicesUser')
  scope: openAiAccount
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Optional role assignment for managed identity on Document Intelligence
resource docIntelRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(managedIdentityPrincipalId)) {
  name: guid(documentIntelligenceAccount.id, managedIdentityPrincipalId, 'CognitiveServicesUser')
  scope: documentIntelligenceAccount
  properties: {
    roleDefinitionId: cognitiveServicesUserRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs endpoints only, never keys
output openAiEndpoint string = openAiAccount.properties.endpoint
output openAiId string = openAiAccount.id
output openAiName string = openAiAccount.name
output chatDeploymentName string = chatDeployment.name
output embeddingDeploymentName string = embeddingDeployment.name
output documentIntelligenceEndpoint string = documentIntelligenceAccount.properties.endpoint
output documentIntelligenceId string = documentIntelligenceAccount.id
output documentIntelligenceName string = documentIntelligenceAccount.name
