@description('Location for all resources.')
param location string = resourceGroup().location

@description('location for Cosmos DB resources.')
param cosmosLocation string

@description('A prefix to add to the start of all resource names.')
param prefix string = 'macae'

@description('Tags to apply to all deployed resources')
param tags object = {}

@description('Your OpenAI API Key to use with public OpenAI API')
@secure()
param openaiApiKey string

var uniqueNameFormat = '${prefix}-{0}-${uniqueString(resourceGroup().id, prefix)}'

// Cosmos DB Account
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: format(uniqueNameFormat, 'cosmos')
  location: cosmosLocation
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: false
    locations: [
      {
        failoverPriority: 0
        locationName: cosmosLocation
      }
    ]
  }

  resource autogenDb 'sqlDatabases' = {
    name: 'autogen'
    properties: {
      resource: {
        id: 'autogen'
        createMode: 'Default'
      }
      options: {
        throughput: 400
      }
    }

    resource memoryContainer 'containers' = {
      name: 'memory'
      properties: {
        resource: {
          id: 'memory'
          partitionKey: {
            kind: 'Hash'
            version: 2
            paths: [
              '/session_id'
            ]
          }
        }
      }
    }
  }
}

// Log Analytics
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: format(uniqueNameFormat, 'logs')
  location: location
  tags: tags
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

// Container App Environment
resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: format(uniqueNameFormat, 'env')
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

// Container App (Backend)
resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: format(uniqueNameFormat, 'backend')
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
      secrets: [
        {
          name: 'openai-api-key'
          value: openaiApiKey
        }
      ]
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: 'lfpmeloni/finagent-backend:latest'
          resources: {
            cpu: 1
            memory: '2Gi'
          }
          env: [
            {
              name: 'OPENAI_API_TYPE'
              value: 'openai'
            }
            {
              name: 'OPENAI_API_KEY'
              secretRef: 'openai-api-key'
            }
            {
              name: 'OPENAI_API_BASE'
              value: 'https://api.openai.com/v1'
            }
            {
              name: 'OPENAI_API_MODEL'
              value: 'gpt-4o'
            }
            {
              name: 'OPENAI_API_VERSION'
              value: '2024-04-01-preview'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: 'https://api.openai.com/v1'
            }
            {
              name: 'COSMOSDB_DATABASE'
              value: cosmos::autogenDb.name
            }
            {
              name: 'COSMOSDB_CONTAINER'
              value: cosmos::autogenDb::memoryContainer.name
            }
            {
              name: 'COSMOSDB_ENDPOINT'
              value: cosmos.properties.documentEndpoint
            }
          ]
        }
      ]
    }
  }
}

output COSMOSDB_ENDPOINT string = cosmos.properties.documentEndpoint
output COSMOSDB_DATABASE string = cosmos::autogenDb.name
output COSMOSDB_CONTAINER string = cosmos::autogenDb::memoryContainer.name
output CONTAINER_APP_URL string = backend.properties.configuration.ingress.fqdn
