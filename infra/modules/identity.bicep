@description('Environment name')
param env string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Managed identity name')
param managedIdentityName string = 'id-pda-${env}-uaen'

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
  tags: tags
}

output managedIdentityId string = managedIdentity.id
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId
output managedIdentityName string = managedIdentity.name
