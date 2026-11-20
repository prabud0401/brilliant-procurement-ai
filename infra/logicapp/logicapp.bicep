@description('Environment name')
param env string

@description('Azure region for resources')
param location string = 'uaenorth'

@description('Resource tags')
param tags object

@description('Base URL of the PDA API backend (e.g. https://ca-api-pda-prod-uaen.azurecontainerapps.io)')
param apiBaseUrl string

@secure()
@description('Secret API key for authenticating HTTP POST requests to the intake endpoint')
param intakeKey string

@description('Whether the Logic App workflow is enabled')
param enabled bool = true

@description('Maximum attachment size in bytes (default 4 MB)')
param maxAttachmentSizeBytes int = 4194304

var outlookConnectionName = 'outlook-pda-${env}-uaen'
var logicAppName = 'logic-pda-${env}-uaen'

// 1. Outlook.com API connection (manual one-time interactive OAuth sign-in at Gate G2)
resource outlookConnection 'Microsoft.Web/connections@2016-06-01' = {
  name: outlookConnectionName
  location: location
  tags: tags
  properties: {
    displayName: 'Outlook.com Connection'
    api: {
      id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'outlook')
    }
  }
}

// 2. Consumption Logic App workflow
resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: logicAppName
  location: location
  tags: tags
  properties: {
    state: enabled ? 'Enabled' : 'Disabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        '$connections': {
          defaultValue: {}
          type: 'Object'
        }
      }
      triggers: {
        'When_a_new_email_arrives_(V2)': {
          type: 'ApiConnection'
          inputs: {
            host: {
              connection: {
                name: '@parameters(\'$connections\')[\'outlook\'][\'connectionId\']'
              }
            }
            method: 'get'
            path: '/v2/Mail/OnNewEmail'
            queries: {
              hasAttachments: true
              includeAttachments: true
            }
          }
          recurrence: {
            frequency: 'Minute'
            interval: 5
          }
        }
      }
      actions: {
        For_each_attachment: {
          type: 'Foreach'
          foreach: '@triggerBody()?[\'attachments\']'
          actions: {
            Condition_allowed_attachment: {
              type: 'If'
              expression: {
                and: [
                  {
                    or: [
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'contentType\'])'
                          'application/pdf'
                        ]
                      }
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'contentType\'])'
                          'image/png'
                        ]
                      }
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'contentType\'])'
                          'image/jpeg'
                        ]
                      }
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'name\'])'
                          '.pdf'
                        ]
                      }
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'name\'])'
                          '.png'
                        ]
                      }
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'name\'])'
                          '.jpg'
                        ]
                      }
                      {
                        contains: [
                          '@toLower(items(\'For_each_attachment\')?[\'name\'])'
                          '.jpeg'
                        ]
                      }
                    ]
                  }
                  {
                    lessOrEquals: [
                      '@items(\'For_each_attachment\')?[\'size\']'
                      maxAttachmentSizeBytes
                    ]
                  }
                ]
              }
              actions: {
                HTTP_POST_to_API: {
                  type: 'Http'
                  inputs: {
                    method: 'POST'
                    uri: '${apiBaseUrl}/api/v1/intake/email'
                    headers: {
                      'X-Intake-Key': intakeKey
                    }
                    body: {
                      '$multipart': [
                        {
                          headers: {
                            'Content-Disposition': 'form-data; name="file"; filename="@{items(\'For_each_attachment\')?[\'name\']}"'
                            'Content-Type': '@{items(\'For_each_attachment\')?[\'contentType\']}'
                          }
                          body: '@items(\'For_each_attachment\')?[\'contentBytes\']'
                        }
                        {
                          headers: {
                            'Content-Disposition': 'form-data; name="sender"'
                          }
                          body: '@triggerBody()?[\'from\']'
                        }
                        {
                          headers: {
                            'Content-Disposition': 'form-data; name="subject"'
                          }
                          body: '@triggerBody()?[\'subject\']'
                        }
                        {
                          headers: {
                            'Content-Disposition': 'form-data; name="received_at"'
                          }
                          body: '@triggerBody()?[\'receivedDateTime\']'
                        }
                        {
                          headers: {
                            'Content-Disposition': 'form-data; name="message_id"'
                          }
                          body: '@triggerBody()?[\'id\']'
                        }
                      ]
                    }
                    runtimeConfiguration: {
                      secureData: {
                        properties: [
                          'inputs'
                          'outputs'
                        ]
                      }
                    }
                  }
                  runAfter: {}
                }
              }
              runAfter: {}
            }
          }
          runAfter: {}
        }
      }
    }
    parameters: {
      '$connections': {
        value: {
          outlook: {
            connectionId: outlookConnection.id
            connectionName: 'outlook'
            id: subscriptionResourceId('Microsoft.Web/locations/managedApis', location, 'outlook')
          }
        }
      }
    }
  }
}

output logicAppName string = logicApp.name
output outlookConnectionName string = outlookConnection.name
