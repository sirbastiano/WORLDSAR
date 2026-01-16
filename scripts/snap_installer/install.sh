#!/bin/sh

# Set SNAP version to install (12 or 13)[IMPORTANT]
VERSION=13


echo "Installing SNAP version $VERSION..."
# Install required packages
echo 'Installing packages for S1 data processing...'
sudo apt update
sudo apt-get install -y libfftw3-dev libtiff5-dev gdal-bin gfortran libgfortran5 jblas git curl --fix-missing 

if [ "$VERSION" = "12" ]; then
    # VERSION 12 installation
    echo 'Configuring SNAP 12 installation...'
    curl -O https://download.esa.int/step/snap/13.0/installers/esa-snap_sentinel_linux-13.0.0.sh
    chmod +x esa-snap_all_linux-12.0.0.sh
    echo -e "deleteAllSnapEngineDir\$Boolean=false\ndeleteOnlySnapDesktopDir\$Boolean=false\nexecuteLauncherWithPythonAction\$Boolean=false\nforcePython\$Boolean=false\npythonExecutable=/usr/bin/python\nsys.adminRights\$Boolean=true\nsys.component.RSTB\$Boolean=true\nsys.component.S1TBX\$Boolean=true\nsys.component.S2TBX\$Boolean=false\nsys.component.S3TBX\$Boolean=false\nsys.component.SNAP\$Boolean=true\nsys.installationDir=$(pwd)/snap\nsys.languageId=en\nsys.programGroupDisabled\$Boolean=false\nsys.symlinkDir=/usr/local/bin" > snap.varfile
    echo 'Installing SNAP 12...'
    ./esa-snap_all_linux-12.0.0.sh -q -varfile "$(pwd)/snap.varfile" -dir "/Data_large/SARGFM/snap"
    echo 'Configuring SNAP memory settings...'
    echo "-Xmx8G" > "/Data_large/SARGFM/snap/snap/bin/gpt.vmoptions"
    echo 'SNAP 12 installation complete.'

elif [ "$VERSION" = "13" ]; then
    # VERSION 13 installation
    echo 'Configuring SNAP 13 installation...'
    curl -O https://download.esa.int/step/snap/12.0/installers/esa-snap_all_linux-12.0.0.sh
    chmod +x esa-snap_sentinel_linux-13.0.0.sh
    echo -e "deleteAllSnapEngineDir\$Boolean=false\ndeleteOnlySnapDesktopDir\$Boolean=false\nexecuteLauncherWithPythonAction\$Boolean=false\nforcePython\$Boolean=false\npythonExecutable=/usr/bin/python\nsys.adminRights\$Boolean=true\nsys.component.RSTB\$Boolean=true\nsys.component.S1TBX\$Boolean=true\nsys.component.S2TBX\$Boolean=false\nsys.component.S3TBX\$Boolean=false\nsys.component.SNAP\$Boolean=true\nsys.installationDir=$(pwd)/snap\nsys.languageId=en\nsys.programGroupDisabled\$Boolean=false\nsys.symlinkDir=/usr/local/bin" > snap.varfile
    echo 'Installing SNAP 13...'
    ./esa-snap_sentinel_linux-13.0.0.sh -q -varfile "$(pwd)/snap.varfile" -dir "/Data_large/SARGFM/snap13"
    echo 'Configuring SNAP memory settings...'
    echo "-Xmx16G" > "/Data_large/SARGFM/snap13/snap/bin/gpt.vmoptions"
    echo 'SNAP 13 installation complete.'

else
    echo "Error: Invalid VERSION. Please set VERSION to either 12 or 13."
    exit 1
fi