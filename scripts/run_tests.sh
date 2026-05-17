#!/bin/bash
# SIGINT System — Master Test Runner
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}=== SIGINT System Test Suite ===${NC}"
echo ""

PASS=0
FAIL=0

run_test() {
    local name="$1"
    local cmd="$2"
    echo -e "${YELLOW}[TEST] ${name}${NC}"
    if eval "$cmd" 2>&1; then
        echo -e "${GREEN}[PASS] ${name}${NC}"
        ((PASS++))
    else
        echo -e "${RED}[FAIL] ${name}${NC}"
        ((FAIL++))
    fi
    echo ""
}

# 1. Build all containers
echo -e "${YELLOW}=== Building Containers ===${NC}"
docker compose build --parallel

# 2. Start stack
echo -e "${YELLOW}=== Starting Stack ===${NC}"
docker compose up -d
sleep 10

# 3. Health checks
run_test "Database Health" "docker compose exec -T db pg_isready -U sigint -d sigint_db"
run_test "Backend Health" "curl -sf http://localhost:4000/health | grep -q 'healthy'"
run_test "Middleware Health" "curl -sf http://localhost:5555/health | grep -q 'healthy'"
run_test "Frontend Reachable" "curl -sf http://localhost:3000 | grep -q 'SIGINT'"

# 4. Database schema tests
run_test "DB Tables Exist" "docker compose exec -T db psql -U sigint -d sigint_db -c '\dt' | grep -q 'networks'"
run_test "DB Seed Data" "docker compose exec -T db psql -U sigint -d sigint_db -c 'SELECT COUNT(*) FROM networks;' | grep -q '3'"
run_test "DB Views Exist" "docker compose exec -T db psql -U sigint -d sigint_db -c 'SELECT * FROM v_topology LIMIT 1;'"

# 5. Python tests
run_test "Python Unit Tests" "docker compose exec -T middleware pytest tests/ -v --tb=short"

# 6. Node.js tests
run_test "Node.js Unit Tests" "docker compose exec -T backend npm test"

# 7. API integration tests
run_test "POST Signal" "curl -sf -X POST http://localhost:4000/api/signals -H 'Content-Type: application/json' -d '{\"frequency\":460.1,\"snr_db\":20,\"protocol_guess\":\"DMR\"}' | grep -q 'frequency'"
run_test "GET Signals" "curl -sf http://localhost:4000/api/signals | grep -q 'data'"
run_test "GET Topology" "curl -sf http://localhost:4000/api/topology | grep -q 'nodes'"
run_test "GET SDR Devices" "curl -sf http://localhost:4000/api/sdr | grep -q 'data'"

# 8. Mock data integration
run_test "Mock Stream Test" "docker compose exec -T middleware python mocks/mock_sdr_stream.py --mode=test --duration=10 --backend=http://backend:4000"

# Verify data was inserted
run_test "Signals Populated" "docker compose exec -T db psql -U sigint -d sigint_db -c 'SELECT COUNT(*) FROM signal_logs;' | grep -v '^\-\-' | grep -v 'count' | tr -d ' ' | grep -v '^$' | head -1 | awk '{if(\$1>0) exit 0; else exit 1}'"

echo ""
echo -e "${YELLOW}=== Results ===${NC}"
echo -e "${GREEN}Passed: ${PASS}${NC}"
echo -e "${RED}Failed: ${FAIL}${NC}"

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}SOME TESTS FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ALL TESTS PASSED ✓${NC}"
    exit 0
fi
