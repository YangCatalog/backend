BACKEND=$(pwd)
SAVE_FILE_DIR="$VAR"/all_modules
YANG_MODELS_DIR="$VAR"/nonietf/yangmodels/yang

# Prepare /var/yang directory structure
mkdir -p "$TMP_DIR"
mkdir -p "$VAR"/ytrees
mkdir -p "$SAVE_FILE_DIR"
mkdir -p "$YANG_MODELS_DIR"

# Create files in tmp dir
touch "$TMP_DIR"/normal.json "$TMP_DIR"/prepare.json

# Clone YangModels/yang repository if it's not already present
if [[ ! -d "$YANG_MODELS_DIR"/vendor/huawei ]]
then
    git clone --depth 1 https://github.com/YangModels/yang.git "$YANG_MODELS_DIR"
    cd "$YANG_MODELS_DIR" || exit 1
    git submodule update --init vendor/huawei
fi

# Prepare files and directory structure for test_groupings.py
mkdir -p "$TEST_REPO"/standard/ietf/RFC
touch "$TEST_REPO"/standard/ietf/README.md
cp "$YANG_MODELS_DIR"/standard/ietf/RFC/ietf-interfaces.yang "$TEST_REPO"/standard/ietf/RFC/.
cp "$BACKEND"/tests/resources/request-data.json "$TMP_DIR"/test/.

# Create directories which match YangModels/yang/vendor/cisco structure, then copy certain files to these directories
mkdir -p "$TEST_REPO"/vendor/cisco/xr/701/
mkdir -p "$TEST_REPO"/vendor/cisco/xr/702/
mkdir -p "$TEST_REPO"/vendor/cisco/nx/9.2-1
mkdir -p "$TEST_REPO"/vendor/cisco/xe/16101
mkdir -p "$TEST_REPO"/standard/ietf/RFC/empty
cp "$BACKEND"/tests/resources/capabilities-ncs5k.xml "$TEST_REPO"/vendor/cisco/xr/701/
cp "$YANG_MODELS_DIR"/vendor/cisco/xr/701/platform-metadata.json "$TEST_REPO"/vendor/cisco/xr/701/
cp "$YANG_MODELS_DIR"/vendor/cisco/xr/701/*.yang "$TEST_REPO"/vendor/cisco/xr/701/
cp "$YANG_MODELS_DIR"/vendor/cisco/xr/702/capabilities-ncs5k.xml "$TEST_REPO"/vendor/cisco/xr/702/
cp "$YANG_MODELS_DIR"/vendor/cisco/nx/9.2-1/netconf-capabilities.xml "$TEST_REPO"/vendor/cisco/nx/9.2-1/
cp "$YANG_MODELS_DIR"/vendor/cisco/xe/16101/capability-asr1k.xml "$TEST_REPO"/vendor/cisco/xe/16101/
cp "$YANG_MODELS_DIR"/standard/ietf/RFC/ietf-yang-types@2013-07-15.yang "$TEST_REPO"/standard/ietf/RFC
cp "$YANG_MODELS_DIR"/standard/ietf/RFC/ietf-yang-types@2010-09-24.yang "$TEST_REPO"/standard/ietf/RFC

# Prepare Huawei directory for ietf-yang-lib based tests
YANG_MODELS_HUAWEI_DIR="$YANG_MODELS_DIR"/vendor/huawei/network-router/8.20.0/ne5000e
mkdir -p "$TEST_REPO"/vendor/huawei/network-router/8.20.0/ne5000e
cp "$YANG_MODELS_HUAWEI_DIR"/ietf*.yang "$TEST_REPO"/vendor/huawei/network-router/8.20.0/ne5000e/
cp "$YANG_MODELS_HUAWEI_DIR"/huawei-aaa*.yang "$TEST_REPO"/vendor/huawei/network-router/8.20.0/ne5000e/

for dependency in huawei-pub-type huawei-hwtacacs huawei-extension huawei-network-instance huawei-radius-client
do
    cp "$YANG_MODELS_HUAWEI_DIR"/$dependency.yang "$TEST_REPO"/vendor/huawei/network-router/8.20.0/ne5000e/
done

cp "$BACKEND"/tests/resources/platform-metadata.json "$TEST_REPO"/vendor/huawei/network-router/8.20.0/ne5000e/
cp "$BACKEND"/tests/resources/ietf-yang-library.xml "$TEST_REPO"/vendor/huawei/network-router/8.20.0/ne5000e/

# Prepare directory structure need for test_util.py
mkdir -p "$TMP_DIR"/util-tests
cp "$YANG_MODELS_DIR"/standard/ietf/RFC/ietf-yang-types.yang "$TMP_DIR"/util-tests/
cp "$YANG_MODELS_DIR"/standard/ietf/RFC/ietf-yang-types@2010-09-24.yang "$TMP_DIR"/util-tests/

# Prepare directory structure need for test_resolveExpiration.py
# Copy all RFC modules into /var/yang/all_modules directory
cp "$YANG_MODELS_DIR"/standard/ietf/RFC/*@*.yang "$SAVE_FILE_DIR"
cp "$BACKEND"/tests/resources/all_modules/* "$SAVE_FILE_DIR"