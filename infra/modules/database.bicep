@description('Environment name')
param env string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('PostgreSQL Flexible Server name')
param postgresServerName string = 'psql-pda-${env}-uaen'

@description('Administrator login username')
param administratorLogin string = 'pdaadmin'

@secure()
@description('Administrator login password')
param administratorLoginPassword string

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: postgresServerName
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource pdaDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgresServer
  name: 'pda'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource azureExtensions 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-12-01-preview' = {
  parent: postgresServer
  name: 'azure.extensions'
  properties: {
    value: 'VECTOR,PGCRYPTO,UUID-OSSP'
    source: 'user-override'
  }
}

resource allowAzureServicesFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgresServer
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output postgresServerId string = postgresServer.id
output postgresServerName string = postgresServer.name
output fullyQualifiedDomainName string = postgresServer.properties.fullyQualifiedDomainName
output databaseName string = pdaDatabase.name
output administratorLogin string = administratorLogin
