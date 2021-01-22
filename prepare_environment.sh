export PYTHONPATH=$PYTHONPATH:$(pwd)
export BACKEND=$(pwd)
# Create logs directory and log files
export LOGS_DIR=$BACKEND/tests/resources/logs
mkdir -p $LOGS_DIR
touch $LOGS_DIR/healthcheck.log $LOGS_DIR/parseAndPopulate.log $LOGS_DIR/yang.log
# Create files in tmp dir
export TMP_DIR=$BACKEND/tests/resources/tmp
touch $TMP_DIR/normal.json $TMP_DIR/prepare.json
# Clone YangModels/yang repository
export YANG_MODELS_DIR=$BACKEND/tests/resources/yangmodels/yang
mkdir -p $YANG_MODELS_DIR
git clone --depth 1 https://github.com/YangModels/yang.git $YANG_MODELS_DIR
cd $YANG_MODELS_DIR
git submodule init
git submodule update
export BRANCH_HASH=$(git rev-parse HEAD)
# Prepare files and folder structure for capability.py tests
# Create folders which match YangModels/yang cisco vendor structure, then copy certain files to these folders
mkdir -p $BACKEND/tests/resources/tmp/capability-tests/temp/YangModels/yang/$BRANCH_HASH/standard/ietf/RFC
cp $YANG_MODELS_DIR/standard/ietf/RFC/ietf-interfaces.yang $BACKEND/tests/resources/tmp/capability-tests/temp/YangModels/yang/$BRANCH_HASH/standard/ietf/RFC/.
cp $BACKEND/tests/resources/tmp/prepare-sdo.json $BACKEND/tests/resources/tmp/capability-tests/.
mkdir -p $BACKEND/tests/resources/tmp/vendor/cisco/xr/701/
mkdir -p $BACKEND/tests/resources/tmp/vendor/cisco/xr/702/
mkdir -p $BACKEND/tests/resources/tmp/vendor/cisco/nx/9.2-1
mkdir -p $BACKEND/tests/resources/tmp/vendor/cisco/xe/16101
mkdir -p $BACKEND/tests/resources/tmp/vendor/huawei/network-router/8.9.10
cp $BACKEND/tests/resources/capabilities-ncs5k.xml $BACKEND/tests/resources/tmp/vendor/cisco/xr/701/
cp $BACKEND/tests/resources/platform-metadata.json $BACKEND/tests/resources/tmp/vendor/huawei/network-router/8.9.10/
cp $BACKEND/tests/resources/ietf-yang-library.xml $BACKEND/tests/resources/tmp/vendor/huawei/network-router/8.9.10/
cp $YANG_MODELS_DIR/vendor/cisco/xr/701/platform-metadata.json $BACKEND/tests/resources/tmp/vendor/cisco/xr/701/
cp $YANG_MODELS_DIR/vendor/cisco/xr/702/capabilities-ncs5k.xml $BACKEND/tests/resources/tmp/vendor/cisco/xr/702/
cp $YANG_MODELS_DIR/vendor/cisco/nx/9.2-1/netconf-capabilities.xml $BACKEND/tests/resources/tmp/vendor/cisco/nx/9.2-1/
cp $YANG_MODELS_DIR/vendor/cisco/xe/16101/capability-asr1k.xml $BACKEND/tests/resources/tmp/vendor/cisco/xe/16101/
cd $BACKEND
