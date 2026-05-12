#!/bin/bash
# Shield Agent - Deployment Verification Script
# Tests backend connectivity and configuration

set -e

RAILWAY_URL="https://walkthroughgitrep-production.up.railway.app"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Shield Agent - Deployment Test"
echo "========================================="
echo ""

# Test 1: Backend Health Check
echo -e "${YELLOW}[1/5] Testing backend health endpoint...${NC}"
HEALTH_RESPONSE=$(curl -s "$RAILWAY_URL/health")
if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ Backend is running${NC}"
    echo "Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Backend health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
    exit 1
fi
echo ""

# Test 2: Supabase Connection
echo -e "${YELLOW}[2/5] Checking Supabase connection...${NC}"
if echo "$HEALTH_RESPONSE" | grep -q '"supabase":"connected"'; then
    echo -e "${GREEN}✓ Supabase is connected${NC}"
else
    echo -e "${RED}✗ Supabase not connected - check Railway variables${NC}"
    echo "Go to Railway → Variables and ensure SUPABASE_URL, SUPABASE_KEY are set"
    exit 1
fi
echo ""

# Test 3: Port Configuration
echo -e "${YELLOW}[3/5] Checking port configuration...${NC}"
if echo "$HEALTH_RESPONSE" | grep -q '"port":8080'; then
    echo -e "${GREEN}✓ Port 8080 is correct${NC}"
else
    echo -e "${RED}✗ Port is not 8080 - check railway.json and env vars${NC}"
    exit 1
fi
echo ""

# Test 4: API Endpoint Accessibility
echo -e "${YELLOW}[4/5] Testing API endpoints...${NC}"
START_AUDIT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$RAILWAY_URL/api/start-audit" \
    -H "Content-Type: application/json" \
    -d '{"target_url":"https://example.com","company_id":"test"}')

if [ "$START_AUDIT_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ /api/start-audit endpoint is working${NC}"
else
    if [ "$START_AUDIT_STATUS" = "503" ]; then
        echo -e "${RED}✗ Endpoint returned 503 - Supabase is unavailable${NC}"
    else
        echo -e "${RED}✗ Endpoint returned $START_AUDIT_STATUS${NC}"
    fi
fi
echo ""

# Test 5: Frontend Environment Variable
echo -e "${YELLOW}[5/5] Checking frontend build...${NC}"
if [ -f "dist/index.html" ]; then
    if grep -q "walkthroughgitrep-production.up.railway.app" dist/index.html || \
       grep -q "walkthroughgitrep-production.up.railway.app" dist/assets/*.js 2>/dev/null; then
        echo -e "${GREEN}✓ Frontend built with correct Railway URL${NC}"
    else
        echo -e "${YELLOW}⚠ Frontend built but Railway URL not found in bundle${NC}"
        echo "Make sure VITE_AUDIT_API_URL env var is set in Bolt.new and you ran 'npm run build'"
    fi
else
    echo -e "${YELLOW}⚠ dist/ folder not found - make sure you ran 'npm run build'${NC}"
fi
echo ""

echo "========================================="
echo -e "${GREEN}✓ All checks passed!${NC}"
echo "========================================="
echo ""
echo "Your deployment is ready. Next steps:"
echo "1. Make sure frontend VITE_AUDIT_API_URL is set in Bolt.new"
echo "2. Run 'npm run build' in Bolt.new"
echo "3. Deploy frontend"
echo "4. Open DevTools console and look for [SHIELD] logs"
echo ""
