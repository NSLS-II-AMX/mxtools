#!/bin/bash

set -vxeuo pipefail

script_dir=$(dirname ${0})

# isort
bash ${script_dir}/isort.sh

# black
bash ${script_dir}/black.sh

# flake8
bash ${script_dir}/flake8.sh
