@description('Environment name')
param env string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Key Vault name (3-24 alphanumeric and hyphens)')
param keyVaultName string = 'kv-pda-${env}-uaen'

@description('Principal ID of the user-assigned managed identity')
param managedIdentityPrincipalId string

@secure()
@description('JWT secret key')
param jwtSecret string

@secure()
@description('Postgres administrator password')
param postgresAdminPassword string

@secure()
@description('Application database password')
param appDbPassword string

@secure()
@description('Demo user password')
param demoUserPassword string

@secure()
@description('Database URL for application connection')
param databaseUrl string

@secure()
@description('Database URL for migration connection')
param databaseUrlMigrator string

@secure()
@description('Optional container registry password (empty if public registry)')
param containerRegistryPassword string

@description('Optional intake key hash for email intake')
param intakeKeyHash string = ''

// Built-in role: Key Vault Secrets User (4633458b-17de-408a-b874-0445c86b69e6)
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: false // OFF so teardown is clean
    publicNetworkAccess: 'Enabled'
  }
}

// Grant Managed Identity the Key Vault Secrets User role
resource roleAssignmentSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentityPrincipalId, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Secrets
resource secretJwt 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'jwt-secret'
  properties: {
    value: jwtSecret
  }
}

resource secretPostgresAdmin 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'postgres-admin-password'
  properties: {
    value: postgresAdminPassword
  }
}

resource secretAppDb 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'app-db-password'
  properties: {
    value: appDbPassword
  }
}

resource secretDemoUser 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'demo-user-password'
  properties: {
    value: demoUserPassword
  }
}

resource secretDatabaseUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: databaseUrl
  }
}

resource secretDatabaseUrlMigrator 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'database-url-migrator'
  properties: {
    value: databaseUrlMigrator
  }
}

resource secretRegistryPassword 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(containerRegistryPassword)) {
  parent: keyVault
  name: 'container-registry-password'
  properties: {
    value: containerRegistryPassword
  }
}

resource secretIntakeKeyHash 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'intake-key-hash'
  properties: {
    value: !empty(intakeKeyHash) ? intakeKeyHash : 'not-configured'
  }
}

output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
