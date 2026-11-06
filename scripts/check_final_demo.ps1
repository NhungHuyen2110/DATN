# Read-only smoke test. Start Backend :8001 and AI :8000 before running.
$ErrorActionPreference = 'Continue'
$backend = 'http://127.0.0.1:8001'
$ai = 'http://127.0.0.1:8000'

function Test-Url($label, $url, $timeout = 20) {
  try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout
    if ($response.StatusCode -eq 200) {
      Write-Host "[PASS] $label : HTTP 200" -ForegroundColor Green
      return $true
    }
    Write-Host "[FAIL] $label : HTTP $($response.StatusCode)" -ForegroundColor Red
  } catch {
    Write-Host "[FAIL] $label : $($_.Exception.Message)" -ForegroundColor Red
  }
  return $false
}

Write-Host '=== LUMIERE FINAL DEMO - READ-ONLY CHECK ===' -ForegroundColor Cyan
Test-Url 'Backend health / PostgreSQL' "$backend/health" | Out-Null
Test-Url 'Website' "$backend/index.html" | Out-Null
Test-Url 'Customer contact page' "$backend/pages/contact.html" | Out-Null
Test-Url 'Admin dashboard' "$backend/pages/admin/dashboard.html" | Out-Null
Test-Url 'Admin contacts page' "$backend/pages/admin/contacts.html" | Out-Null
Test-Url 'Public products API' "$backend/products?page=1&page_size=1" | Out-Null
Test-Url 'Payment and shipping capabilities' "$backend/checkout/payment-methods" | Out-Null

try {
  $openapi = Invoke-RestMethod -Uri "$backend/openapi.json" -TimeoutSec 15
  $paths = @('/contact','/admin/contact-messages','/admin/categories','/admin/brands',
    '/admin/reports/purchase-behavior','/orders/{id}/payments/vnpay',
    '/payments/vnpay/ipn','/payments/vnpay/return')
  foreach ($path in $paths) {
    if ($openapi.paths.PSObject.Properties.Name -contains $path) {
      Write-Host "[PASS] Route registered: $path" -ForegroundColor Green
    } else {
      Write-Host "[FAIL] Route missing: $path" -ForegroundColor Red
    }
  }
} catch {
  Write-Host "[FAIL] Could not read Backend OpenAPI" -ForegroundColor Red
}

Test-Url 'AI OpenAPI' "$ai/openapi.json" 20 | Out-Null
Write-Host ''
Write-Host 'No orders or database rows were created by this script.'
Write-Host 'RAG, Hybrid V2, Admin CRUD, customer checkout and VNPay require manual functional tests.'
