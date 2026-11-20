targetScope = 'resourceGroup'

@description('Environment name (e.g. prod, dev)')
param env string = 'prod'

@description('Azure region for resources')
param location string = 'uaenorth'

@description('Azure region for PostgreSQL only (demo: northeurope, because Burstable Postgres is not offered to the demo subscription in UAE North; see infra/README.md)')
param postgresLocation string = location

@description('Resource tags')
param tags object = {
  project: 'brilliant-demo'
  env: env
  expires: '2026-11-29'
}

// Secure parameters with NO defaults
@secure()
@description('JWT secret key (minimum 32 characters)')
param jwtSecret string

@secure()
@description('PostgreSQL administrator password')
param postgresAdminPassword string

@secure()
@description('Application database user password')
param appDbPassword string

@secure()
@description('Demo user account password')
param demoUserPassword string

// Container registry parameters
@description('Container registry server (default: ghcr.io)')
param containerRegistryServer string = 'ghcr.io'

@description('Container registry username')
param containerRegistryUsername string = ''

@secure()
@description('Container registry password or token (empty if public registry)')
param containerRegistryPassword string

// Email intake parameters (R13 stretch)
@description('Enable email intake via Azure Logic App (default false)')
param enableEmailIntake bool = false

@secure()
@description('API key for email intake Logic App (empty if enableEmailIntake is false)')
param intakeKey string = ''

@description('Optional intake key hash for email intake (empty = not configured)')
param intakeKeyHash string = ''

@description('Allowed sender emails or domains for email intake (comma-separated, empty = allow all)')
param intakeSenderAllowlist string = ''

// Container images
@description('Web container image')
param webImage string = 'ghcr.io/prabud0401/brilliant-procurement-ai/web:latest'

@description('API container image')
param apiImage string = 'ghcr.io/prabud0401/brilliant-procurement-ai/api:latest'

@description('Worker container image')
param workerImage string = 'ghcr.io/prabud0401/brilliant-procurement-ai/worker:latest'

// AI service endpoints (from G1 ai.bicep deployment)
@description('Azure OpenAI endpoint')
param azureOpenAiEndpoint string = ''

@description('Azure OpenAI chat deployment name')
param azureOpenAiDeployment string = 'gpt-5-mini'

@description('Azure OpenAI embedding deployment name')
param azureOpenAiEmbeddingDeployment string = 'text-embedding-3-small'

@description('Azure Document Intelligence endpoint')
param azureDocIntelEndpoint string = ''

@description('AI provider mode (mock, replay, live)')
@allowed([
  'mock'
  'replay'
  'live'
])
param aiProvider string = 'replay'

// Resource names per design 9.2: <type>-pda-<env>-uaen
var logAnalyticsWorkspaceName = 'log-pda-${env}-uaen'
var appInsightsName = 'appi-pda-${env}-uaen'
var managedIdentityName = 'id-pda-${env}-uaen'
var keyVaultName = 'kv-pda-${env}-uaen'
var storageAccountName = 'stpda${replace(env, '-', '')}uaen'
var postgresServerName = 'psql-pda-${env}-uaen'

@description('PostgreSQL administrator login username')
param postgresAdminLogin string = 'pdaadmin'

var containerAppsEnvironmentName = 'cae-pda-${env}-uaen'
var webAppName = 'ca-web-pda-${env}-uaen'
var apiAppName = 'ca-api-pda-${env}-uaen'
var workerAppName = 'ca-worker-pda-${env}-uaen'
var migrateJobName = 'migrate'

// 1. Managed Identity
module identity 'modules/identity.bicep' = {
  name: 'identityDeployment'
  params: {
    env: env
    location: location
    tags: tags
    managedIdentityName: managedIdentityName
  }
}

// 2. Monitoring (Log Analytics + Application Insights)
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    env: env
    location: location
    tags: tags
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    appInsightsName: appInsightsName
  }
}

// 3. PostgreSQL Flexible Server
module database 'modules/database.bicep' = {
  name: 'databaseDeployment'
  params: {
    env: env
    location: postgresLocation
    tags: tags
    postgresServerName: postgresServerName
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
  }
}

// Construct database URLs for Key Vault
var databaseUrl = 'postgresql+psycopg://app_user:${appDbPassword}@${database.outputs.fullyQualifiedDomainName}:5432/pda?sslmode=require'
var databaseUrlMigrator = 'postgresql+psycopg://${postgresAdminLogin}:${postgresAdminPassword}@${database.outputs.fullyQualifiedDomainName}:5432/pda?sslmode=require'

// 4. Key Vault (RBAC mode, soft delete on, purge protection OFF)
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    env: env
    location: location
    tags: tags
    keyVaultName: keyVaultName
    managedIdentityPrincipalId: identity.outputs.managedIdentityPrincipalId
    jwtSecret: jwtSecret
    postgresAdminPassword: postgresAdminPassword
    appDbPassword: appDbPassword
    demoUserPassword: demoUserPassword
    databaseUrl: databaseUrl
    databaseUrlMigrator: databaseUrlMigrator
    containerRegistryPassword: containerRegistryPassword
    intakeKeyHash: intakeKeyHash
  }
}

// 5. Storage Account (TLS 1.2, private documents container, MI role assignment)
module storage 'modules/storage.bicep' = {
  name: 'storageDeployment'
  params: {
    env: env
    location: location
    tags: tags
    storageAccountName: storageAccountName
    managedIdentityPrincipalId: identity.outputs.managedIdentityPrincipalId
  }
}

// 6. Container Apps Environment, Apps (web, api, worker), and Job (migrate)
module containerApps 'modules/containerapps.bicep' = {
  name: 'containerAppsDeployment'
  params: {
    env: env
    location: location
    tags: tags
    containerAppsEnvironmentName: containerAppsEnvironmentName
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: monitoring.outputs.logAnalyticsSharedKey
    managedIdentityId: identity.outputs.managedIdentityId
    keyVaultUri: keyVault.outputs.keyVaultUri
    containerRegistryServer: containerRegistryServer
    containerRegistryUsername: containerRegistryUsername
    containerRegistryPassword: containerRegistryPassword
    webImage: webImage
    apiImage: apiImage
    workerImage: workerImage
    webAppName: webAppName
    apiAppName: apiAppName
    workerAppName: workerAppName
    migrateJobName: migrateJobName
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiDeployment: azureOpenAiDeployment
    azureOpenAiEmbeddingDeployment: azureOpenAiEmbeddingDeployment
    azureDocIntelEndpoint: azureDocIntelEndpoint
    aiProvider: aiProvider
    blobAccountUrl: storage.outputs.primaryBlobEndpoint
    azureClientId: identity.outputs.managedIdentityClientId
    intakeSenderAllowlist: intakeSenderAllowlist
  }
}

var validatedIntakeKey = (enableEmailIntake && empty(intakeKey)) ? fail('intakeKey must not be empty when enableEmailIntake is true') : intakeKey

// 7. Email Intake Logic App (Stretch, Gate G2)
module logicApp 'logicapp/logicapp.bicep' = if (enableEmailIntake) {
  name: 'logicAppDeployment'
  params: {
    env: env
    location: location
    tags: tags
    apiBaseUrl: 'https://${containerApps.outputs.apiAppFqdn}'
    intakeKey: validatedIntakeKey
    enabled: enableEmailIntake
  }
}

// Outputs
output webAppFqdn string = containerApps.outputs.webAppFqdn
output webAppUrl string = 'https://${containerApps.outputs.webAppFqdn}'
output apiAppName string = containerApps.outputs.apiAppName
output apiAppFqdn string = containerApps.outputs.apiAppFqdn
output workerAppName string = containerApps.outputs.workerAppName
output migrateJobName string = containerApps.outputs.migrateJobName
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output postgresServerFqdn string = database.outputs.fullyQualifiedDomainName
output storageAccountName string = storage.outputs.storageAccountName
output managedIdentityId string = identity.outputs.managedIdentityId
output managedIdentityPrincipalId string = identity.outputs.managedIdentityPrincipalId
output logAnalyticsWorkspaceName string = monitoring.outputs.logAnalyticsWorkspaceName
output appInsightsName string = monitoring.outputs.appInsightsName
output logicAppName string = logicApp.?outputs.logicAppName ?? ''
output outlookConnectionName string = logicApp.?outputs.outlookConnectionName ?? ''
