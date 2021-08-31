#!/bin/bash

set -vxeuo pipefail

black --line-length=115 . ${1:-}
