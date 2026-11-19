# Shared settings — CHECK these against your VM before the first run.
# Values come from restore-bg-policy.sh used in the Array experiments.
CLI=cli
ORDERER=orderer.orderer.com:7050
CHANNEL=appchannel
CC_NAME=bgac-contention
CC_VERSION=1.0
ORG1_ENV="CORE_PEER_ADDRESS=peer0.hospital1.com:7051 CORE_PEER_LOCALMSPID=HospitalMSP1 CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/peer/hospital1.com/users/Admin@hospital1.com/msp"
# Endorsement policy written into the paper. Org2's MSP ID is ASSUMED to be
# HospitalMSP2 — verify with:  docker exec peer0.hospital2.com env | grep MSPID
CC_POLICY="OR('HospitalMSP1.member','HospitalMSP2.member')"  # .member, not .peer (Fabric 1.4.12 lesson)
