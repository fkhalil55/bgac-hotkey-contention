#!/usr/bin/env bash
# Installs and instantiates bgac-contention next to fabric-realty (Fabric 1.4).
# Take a VM snapshot BEFORE running this. fabric-realty is not touched.
set -euo pipefail
cd "$(dirname "$0")"; source ./env.sh
echo "== MSP IDs on running peers (check CC_POLICY in env.sh) =="
for c in $(docker ps --format '{{.Names}}' | grep -E '^peer'); do echo -n "$c: "; docker exec "$c" env | grep CORE_PEER_LOCALMSPID || true; done
echo "== currently instantiated chaincodes (note fabric-realty's policy for the Array paper) =="
docker exec $CLI bash -c "$ORG1_ENV peer chaincode list --instantiated -C $CHANNEL"
echo "== removing cached chaincode images (Fabric 1.4 reuses an image by name+version, not by code) =="
docker rm -f $(docker ps -aq --filter "name=$CC_NAME") 2>/dev/null || true
docker rmi -f $(docker images -q "dev-*$CC_NAME*") 2>/dev/null || true
echo "== cli GOPATH (must be /opt/gopath) =="; docker exec $CLI bash -c "go env GOPATH"
docker exec $CLI mkdir -p /opt/gopath/src/github.com/bgac-contention
docker cp ../chaincode/bgac-contention/contention.go $CLI:/opt/gopath/src/github.com/bgac-contention/contention.go
docker exec $CLI bash -c "$ORG1_ENV peer chaincode install -n $CC_NAME -v $CC_VERSION -l golang -p github.com/bgac-contention"
docker exec $CLI bash -c "$ORG1_ENV peer chaincode instantiate -o $ORDERER -C $CHANNEL -n $CC_NAME -v $CC_VERSION -c '{\"Args\":[]}' -P \"$CC_POLICY\""
sleep 10
echo "== smoke test =="
docker exec $CLI bash -c "$ORG1_ENV peer chaincode invoke -o $ORDERER -C $CHANNEL -n $CC_NAME -c '{\"Args\":[\"request\",\"single\",\"smoke-a0\",\"1\",\"5\",\"0\",\"smoke\"]}'"
sleep 5
docker exec $CLI bash -c "$ORG1_ENV peer chaincode query -C $CHANNEL -n $CC_NAME -c '{\"Args\":[\"exportLog\",\"smoke\"]}'"
