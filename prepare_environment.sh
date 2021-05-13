export PYTHONPATH=$PYTHONPATH:$(pwd)
export BACKEND=$(pwd)
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
# Prepare files and folder structure for capability.py tests
# Create folders which match YangModels/yang cisco vendor structure, then copy certain files to these folders
mkdir -p $BACKEND/tests/resources/tmp/capability-tests/temp/YangModels/yang/master/standard/ietf/RFC
cp $YANG_MODELS_DIR/standard/ietf/RFC/ietf-interfaces.yang $BACKEND/tests/resources/tmp/capability-tests/temp/YangModels/yang/master/standard/ietf/RFC/.
cp $BACKEND/tests/resources/tmp/prepare-sdo.json $BACKEND/tests/resources/tmp/capability-tests/.
mkdir -p $BACKEND/tests/resources/tmp/master/vendor/cisco/xr/701/
mkdir -p $BACKEND/tests/resources/tmp/master/vendor/cisco/xr/702/
mkdir -p $BACKEND/tests/resources/tmp/master/vendor/cisco/nx/9.2-1
mkdir -p $BACKEND/tests/resources/tmp/master/vendor/cisco/xe/16101
mkdir -p $TMP_DIR/temp/standard/ietf/RFC/empty
cp $BACKEND/tests/resources/capabilities-ncs5k.xml $BACKEND/tests/resources/tmp/master/vendor/cisco/xr/701/
cp $YANG_MODELS_DIR/vendor/cisco/xr/701/platform-metadata.json $BACKEND/tests/resources/tmp/master/vendor/cisco/xr/701/
cp $YANG_MODELS_DIR/vendor/cisco/xr/701/*.yang $BACKEND/tests/resources/tmp/master/vendor/cisco/xr/701/
cp $YANG_MODELS_DIR/vendor/cisco/xr/702/capabilities-ncs5k.xml $BACKEND/tests/resources/tmp/master/vendor/cisco/xr/702/
cp $YANG_MODELS_DIR/vendor/cisco/nx/9.2-1/netconf-capabilities.xml $BACKEND/tests/resources/tmp/master/vendor/cisco/nx/9.2-1/
cp $YANG_MODELS_DIR/vendor/cisco/xe/16101/capability-asr1k.xml $BACKEND/tests/resources/tmp/master/vendor/cisco/xe/16101/
cp $YANG_MODELS_DIR/standard/ietf/RFC/ietf-yang-types@2013-07-15.yang $BACKEND/tests/resources/tmp/temp/standard/ietf/RFC
# Prepare Huawei dir for ietf-yang-lib based tests
export YANG_MODELS_HUAWEI_DIR=$YANG_MODELS_DIR/vendor/huawei/network-router/8.20.0
mkdir -p $BACKEND/tests/resources/tmp/master/vendor/huawei/network-router/8.20.0
cp $BACKEND/tests/resources/platform-metadata.json $BACKEND/tests/resources/tmp/master/vendor/huawei/network-router/8.20.0/
cp $BACKEND/tests/resources/ietf-yang-library.xml $BACKEND/tests/resources/tmp/master/vendor/huawei/network-router/8.20.0/
cp $YANG_MODELS_HUAWEI_DIR/* $BACKEND/tests/resources/tmp/master/vendor/huawei/network-router/8.20.0/
cp $YANG_MODELS_DIR/standard/ietf/RFC/ietf-yang-library@2016-06-21.yang $BACKEND/tests/resources/tmp/master/vendor/huawei/network-router/8.20.0/
# Prepare directory structure need for test_util.py
export UTILITY_RESOURCES=$BACKEND/utility/tests/resources
mkdir -p $UTILITY_RESOURCES/modules
cp $YANG_MODELS_DIR/standard/ietf/RFC/ietf-yang-types.yang $UTILITY_RESOURCES/modules/
touch $UTILITY_RESOURCES/modules/ietf-yang-types@2010-09-24.yang
cd $BACKEND
# Prepare directory structure need for resolveExpiration.py
# TODO: Adjust existing tests to use directory structure in /var/yang if this will work in TravisCI
export var=/var/yang
sudo mkdir -p $var
sudo chown -R $(whoami):$(whoami) $var
mkdir -p $var/tmp
# Create logs directory and log files
export LOGS_DIR=$var/logs
mkdir -p $LOGS_DIR/jobs
touch $var/logs/jobs/resolveExpiration.log
touch $LOGS_DIR/healthcheck.log $LOGS_DIR/parseAndPopulate.log $LOGS_DIR/yang.log
