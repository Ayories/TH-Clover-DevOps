#!/usr/bin/env bash
# Create the monthly cost budget with email warnings. Run in AWS CloudShell.
# Usage: bash infrastructure/budget.sh <alert-email> [limit-usd]
set -euo pipefail
EMAIL="${1:?usage: budget.sh <alert-email> [limit-usd]}"
LIMIT="${2:-15}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"

notify() { # <ACTUAL|FORECASTED> <percent>
  printf '{"Notification":{"NotificationType":"%s","ComparisonOperator":"GREATER_THAN","Threshold":%s,"ThresholdType":"PERCENTAGE"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"%s"}]}' \
    "$1" "$2" "$EMAIL"
}

# IncludeCredit=false counts usage even while free-plan credits pay for it.
aws budgets create-budget --account-id "$ACCOUNT" \
  --budget "{\"BudgetName\":\"th-clover-monthly\",\"BudgetType\":\"COST\",\"TimeUnit\":\"MONTHLY\",\"BudgetLimit\":{\"Amount\":\"$LIMIT\",\"Unit\":\"USD\"},\"CostTypes\":{\"IncludeCredit\":false}}" \
  --notifications-with-subscribers "[$(notify ACTUAL 80),$(notify FORECASTED 100)]"

aws budgets describe-budget --account-id "$ACCOUNT" --budget-name th-clover-monthly \
  --query 'Budget.{Name:BudgetName,Limit:BudgetLimit.Amount,Unit:BudgetLimit.Unit,Period:TimeUnit}' --output table
