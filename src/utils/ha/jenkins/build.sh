#!/bin/bash

set -e
BUILD_START_TIME=$(date +%s)
BASE_DIR=$(realpath "$(dirname $0)/..")
PROG_NAME=$(basename $0)
DIST=$(realpath $BASE_DIR/dist)
BUILD_NUMBER=0
GIT_VER=

echo $BASE_DIR

usage() {
    echo """usage: $PROG_NAME """ 1>&2;
    exit 1;
}

while getopts ":g:v:b:p:k:c:st" o; do
    case "${o}" in
        v)
            VER=${OPTARG}
            ;;
        g)
            GIT_VER=${OPTARG}
            ;;
        b)
            BUILD_NUMBER=${OPTARG}
            ;;
        *)
            usage
            ;;
    esac
done

cd $BASE_DIR
[ -z $"$GIT_VER" ] && GIT_VER="$(git rev-parse --short HEAD)" \
        || GIT_VER="${GIT_VER}_$(git rev-parse --short HEAD)"
[ -z "$VER" ] && VER=$(cat $BASE_DIR/VERSION)

echo "Using VERSION=${VER} GIT_VER=${GIT_VER} "

############################## Copy DIR #############################

# Create fresh one to accomodate all packages.
DIST="$BASE_DIR/dist"
mkdir -p $DIST/ha
cp -rf $BASE_DIR/src/* $DIST/ha/

############################### TAR and RPM #########################

rm -rf ${DIST}/rpmbuild/
mkdir -p ${DIST}/rpmbuild/SOURCES
cd $DIST
tar -czf ${DIST}/rpmbuild/SOURCES/eos-hac-${VER}.tar.gz ha

TOPDIR=$(realpath ${DIST}/rpmbuild)
echo rpmbuild --define "version $VER" --define "dist $GIT_VER" --define "_build_number ${BUILD_NUMBER}" --define "_topdir $TOPDIR" -bb $BASE_DIR/jenkins/hac.spec
rpmbuild --define "version $VER" --define "dist $GIT_VER" --define "_build_number ${BUILD_NUMBER}" --define "_topdir $TOPDIR" -bb $BASE_DIR/jenkins/hac.spec
    
############################ CLEANUP BUILD DIR #################################

# Remove temporary directory
\rm -rf ${DIST}/ha
BUILD_END_TIME=$(date +%s)

echo "RPMs ..."
find $BASE_DIR -name *.rpm

############################ CALCULATE TIME #################################

DIFF=$(( $BUILD_END_TIME - $BUILD_START_TIME ))
h=$(( DIFF / 3600 ))
m=$(( ( DIFF / 60 ) % 60 ))
s=$(( DIFF % 60 ))

printf "%02d:%02d:%02d\n" $h $m $s
echo "Build took %02d:%02d:%02d\n" $h $m $s
