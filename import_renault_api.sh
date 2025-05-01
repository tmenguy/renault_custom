#!/bin/bash
GH_RAW_BASE="https://raw.githubusercontent.com"

## Gather renault-api and modify
path="custom_components/renault/renault_api"
mkdir -p ${path}
rm -f ${path}/*.py
rm -f ${path}/*.typed

GH_ACCOUNT="tmenguy"
GH_REPO="renault-api"
GH_BRANCH="main"
gh_path="${GH_RAW_BASE}/${GH_ACCOUNT}/${GH_REPO}/${GH_BRANCH}/src/renault_api"
files="__init__.py const.py credential.py credential_store.py exceptions.py helpers.py models.py py.typed renault_account.py renault_client.py renault_session.py renault_vehicle.py"

for file in ${files}; do
  wget ${gh_path}/${file} -O ${path}/${file}
  gsed -i 's/from renault_api/from \./g' ${path}/${file}
  gsed -i 's/from \.\./from \./g' ${path}/${file}
done

path="custom_components/renault/renault_api/cli"
mkdir -p ${path}
rm -f ${path}/*.py

gh_path="${GH_RAW_BASE}/${GH_ACCOUNT}/${GH_REPO}/${GH_BRANCH}/src/renault_api/cli"
files="__init__.py __main__.py helpers.py renault_account.py renault_client.py renault_settings.py renault_vehicle.py"

for file in ${files}; do
  wget ${gh_path}/${file} -O ${path}/${file}
  gsed -i 's/from renault_api/from \.\./g' ${path}/${file}
  gsed -i 's/from \.\./from \./g' ${path}/${file}
done

path="custom_components/renault/renault_api/cli/hvac"
mkdir -p ${path}
rm -f ${path}/*.py

gh_path="${GH_RAW_BASE}/${GH_ACCOUNT}/${GH_REPO}/${GH_BRANCH}/src/renault_api/cli/hvac"
files="__init__.py commands.py control.py history.py"

for file in ${files}; do
  wget ${gh_path}/${file} -O ${path}/${file}
  gsed -i 's/from renault_api/from \.\.\./g' ${path}/${file}
  gsed -i 's/from \.\.\./from \./g' ${path}/${file}
done

path="custom_components/renault/renault_api/cli/charge"
mkdir -p ${path}
rm -f ${path}/*.py

gh_path="${GH_RAW_BASE}/${GH_ACCOUNT}/${GH_REPO}/${GH_BRANCH}/src/renault_api/cli/charge"
files="__init__.py commands.py control.py history.py schedule.py"

for file in ${files}; do
  wget ${gh_path}/${file} -O ${path}/${file}
  gsed -i 's/from renault_api/from \.\.\./g' ${path}/${file}
  gsed -i 's/from \.\.\./from \./g' ${path}/${file}
done

path="custom_components/renault/renault_api/gigya"
mkdir -p ${path}
rm -f ${path}/*.py

gh_path="${GH_RAW_BASE}/${GH_ACCOUNT}/${GH_REPO}/${GH_BRANCH}/src/renault_api/gigya"
files="__init__.py exceptions.py models.py schemas.py"

for file in ${files}; do
  wget ${gh_path}/${file} -O ${path}/${file}
  gsed -i 's/from renault_api/from \.\./g' ${path}/${file}
  gsed -i 's/from \.\./from \./g' ${path}/${file}
done

path="custom_components/renault/renault_api/kamereon"
mkdir -p ${path}
rm -f ${path}/*.py

gh_path="${GH_RAW_BASE}/${GH_ACCOUNT}/${GH_REPO}/${GH_BRANCH}/src/renault_api/kamereon"
files="__init__.py enums.py exceptions.py helpers.py models.py schemas.py"

for file in ${files}; do
  wget ${gh_path}/${file} -O ${path}/${file}
  gsed -i 's/from renault_api/from \.\./g' ${path}/${file}
  gsed -i 's/from \.\./from \./g' ${path}/${file}
done

# Copy compatibility module to the renault component folder
echo "Creating and copying compatibility module..."
cp renault_compat.py custom_components/renault/

# Update import statements in the renault component
echo "Updating import statements..."
bash update_renault_imports.sh

echo "Everything completed successfully!"
