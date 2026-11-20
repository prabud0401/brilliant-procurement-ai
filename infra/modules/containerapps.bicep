@description('Environment name')
param env string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Container Apps Environment name')
param containerAppsEnvironmentName string = 'cae-pda-${env}-uaen'

@description('Log Analytics workspace customer ID')
param logAnalyticsCustomerId string

@secure()
@description('Log Analytics primary shared key')
param logAnalyticsSharedKey string

@description('User-assigned managed identity resource ID')
param managedIdentityId string

@description('Key Vault URI')
param keyVaultUri string

@description('Container registry server (e.g. ghcr.io)')
param containerRegistryServer string = 'ghcr.io'

@description('Container registry username')
param containerRegistryUsername string = ''

@secure()
@description('Container registry password or token (empty if public registry)')
param containerRegistryPassword string

@description('Blob storage account URL')
param blobAccountUrl string = ''

@description('Azure Managed Identity client ID')
param azureClientId string = ''

@description('Web container image')
param webImage string = 'ghcr.io/prabud0401/brilliant-procurement-ai/web:latest'

@description('API container image')
param apiImage string = 'ghcr.io/prabud0401/brilliant-procurement-ai/api:latest'

@description('Worker container image')
param workerImage string = 'ghcr.io/prabud0401/brilliant-procurement-ai/worker:latest'

@description('Web app name')
param webAppName string = 'ca-web-pda-${env}-uaen'

@description('API app name')
param apiAppName string = 'ca-api-pda-${env}-uaen'

@description('Worker app name')
param workerAppName string = 'ca-worker-pda-${env}-uaen'

@description('Migration job name')
param migrateJobName string = 'migrate'

@description('Application Insights connection string')
param appInsightsConnectionString string = ''

@description('Azure OpenAI endpoint')
param azureOpenAiEndpoint string = ''

@description('Azure OpenAI deployment name')
param azureOpenAiDeployment string = 'gpt-4o-mini'

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

var baseSecrets = [
  {
    name: 'jwt-secret'
    keyVaultUrl: '${keyVaultUri}secrets/jwt-secret'
    identity: managedIdentityId
  }
  {
    name: 'database-url'
    keyVaultUrl: '${keyVaultUri}secrets/database-url'
    identity: managedIdentityId
  }
  {
    name: 'database-url-migrator'
    keyVaultUrl: '${keyVaultUri}secrets/database-url-migrator'
    identity: managedIdentityId
  }
  {
    name: 'demo-user-password'
    keyVaultUrl: '${keyVaultUri}secrets/demo-user-password'
    identity: managedIdentityId
  }
  {
    name: 'app-db-password'
    keyVaultUrl: '${keyVaultUri}secrets/app-db-password'
    identity: managedIdentityId
  }
]

var registrySecrets = (!empty(containerRegistryUsername) && !empty(containerRegistryPassword))
  ? [
      {
        name: 'registry-password'
        keyVaultUrl: '${keyVaultUri}secrets/container-registry-password'
        identity: managedIdentityId
      }
    ]
  : []

var allSecrets = concat(baseSecrets, registrySecrets)

var registries = (!empty(containerRegistryUsername) && !empty(containerRegistryPassword))
  ? [
      {
        server: containerRegistryServer
        username: containerRegistryUsername
        passwordSecretRef: 'registry-password'
      }
    ]
  : []

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// API Container App (Internal ingress, min 0, max 1)
resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      secrets: allSecrets
      registries: registries
      ingress: {
        external: false // Internal ingress
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'APP_ENV'
              value: env
            }
            {
              name: 'API_PORT'
              value: '8000'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'DATABASE_URL_MIGRATOR'
              secretRef: 'database-url-migrator'
            }
            {
              name: 'JWT_SECRET'
              secretRef: 'jwt-secret'
            }
            {
              name: 'JWT_ISSUER'
              value: 'brilliant-procurement-ai'
            }
            {
              name: 'DEMO_USER_PASSWORD'
              secretRef: 'demo-user-password'
            }
            {
              name: 'BLOB_ACCOUNT_URL'
              value: blobAccountUrl
            }
            {
              name: 'BLOB_CONTAINER'
              value: 'documents'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: azureClientId
            }
            {
              name: 'AI_PROVIDER'
              value: aiProvider
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAiEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAiDeployment
            }
            {
              name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
              value: azureOpenAiEmbeddingDeployment
            }
            {
              name: 'AZURE_DOCINTEL_ENDPOINT'
              value: azureDocIntelEndpoint
            }
            {
              name: 'INTEGRATIONS_MODE'
              value: 'mock'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/readyz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// Worker Container App (No ingress, min 1, max 1)
resource workerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: workerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      secrets: allSecrets
      registries: registries
      ingress: null // No ingress
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: workerImage
          command: [
            'python'
            '-m'
            'app.worker_main'
          ]
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'APP_ENV'
              value: env
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'DATABASE_URL_MIGRATOR'
              secretRef: 'database-url-migrator'
            }
            {
              name: 'JWT_SECRET'
              secretRef: 'jwt-secret'
            }
            {
              name: 'JWT_ISSUER'
              value: 'brilliant-procurement-ai'
            }
            {
              name: 'DEMO_USER_PASSWORD'
              secretRef: 'demo-user-password'
            }
            {
              name: 'BLOB_ACCOUNT_URL'
              value: blobAccountUrl
            }
            {
              name: 'BLOB_CONTAINER'
              value: 'documents'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: azureClientId
            }
            {
              name: 'AI_PROVIDER'
              value: aiProvider
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAiEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAiDeployment
            }
            {
              name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT'
              value: azureOpenAiEmbeddingDeployment
            }
            {
              name: 'AZURE_DOCINTEL_ENDPOINT'
              value: azureDocIntelEndpoint
            }
            {
              name: 'INTEGRATIONS_MODE'
              value: 'mock'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

// Web Container App (External ingress, min 0, max 1)
resource webApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: webAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      secrets: allSecrets
      registries: registries
      ingress: {
        external: true // External ingress
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          env: [
            {
              name: 'API_BASE_URL'
              value: 'https://${apiApp.properties.configuration.ingress.fqdn}'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 3000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/readyz'
                port: 3000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

// Container Apps Job: migrate (manual trigger)
resource migrateJob 'Microsoft.App/jobs@2024-03-01' = {
  name: migrateJobName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 600
      replicaRetryLimit: 0
      secrets: allSecrets
      registries: registries
    }
    template: {
      containers: [
        {
          name: 'migrate'
          image: apiImage
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
          command: [
            '/bin/sh'
            '-c'
            'set -e && alembic upgrade head && python -m app.core.bootstrap && python -m seed.load'
          ]
          env: [
            {
              name: 'APP_ENV'
              value: env
            }
            {
              name: 'APP_DB_PASSWORD'
              secretRef: 'app-db-password'
            }
            {
              name: 'DATABASE_URL'
              secretRef: 'database-url'
            }
            {
              name: 'DATABASE_URL_MIGRATOR'
              secretRef: 'database-url-migrator'
            }
            {
              name: 'JWT_SECRET'
              secretRef: 'jwt-secret'
            }
            {
              name: 'JWT_ISSUER'
              value: 'brilliant-procurement-ai'
            }
            {
              name: 'DEMO_USER_PASSWORD'
              secretRef: 'demo-user-password'
            }
            {
              name: 'BLOB_ACCOUNT_URL'
              value: blobAccountUrl
            }
            {
              name: 'BLOB_CONTAINER'
              value: 'documents'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: azureClientId
            }
            {
              name: 'INTEGRATIONS_MODE'
              value: 'mock'
            }
          ]
        }
      ]
    }
  }
}

output containerAppsEnvironmentId string = containerAppsEnv.id
output webAppName string = webApp.name
output webAppFqdn string = webApp.properties.configuration.ingress.fqdn
output apiAppName string = apiApp.name
output apiAppFqdn string = apiApp.properties.configuration.ingress.fqdn
output workerAppName string = workerApp.name
output migrateJobName string = migrateJob.name
