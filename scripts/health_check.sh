#!/bin/bash
# Health check for all SIGINT containers
echo "Checking container health..."
echo ""

check() {
    local name="$1"
    local url="$2"
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "✅ $name — healthy"
    else
        echo "❌ $name — unreachable"
    fi
}

check "Database" "http://localhost:5432"
check "Backend API" "http://localhost:4000/health"
check "Middleware" "http://localhost:5555/health"
check "Frontend" "http://localhost:3000"

echo ""
echo "Container statuses:"
docker compose ps
