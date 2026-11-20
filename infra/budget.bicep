targetScope = 'subscription'

@description('Monthly budget amount in USD')
param amount int = 20

@description('Recipient email address for budget alert notifications')
param alertEmail string

@description('Budget name')
param budgetName string = 'budget-pda-monthly'

@description('Start date of the budget in YYYY-MM-01 format. Defaults to the first day of current month.')
param startDate string = '${utcNow('yyyy-MM')}-01'

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: budgetName
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      Actual_50_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [
          alertEmail
        ]
      }
      Actual_100_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [
          alertEmail
        ]
      }
    }
  }
}

output budgetId string = budget.id
output budgetName string = budget.name
