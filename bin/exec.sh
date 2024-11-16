#!/bin/bash
# The MIO-KITCHEN-PROJECT
# Yes!
tool_author="ColdWindSolar"
if [[ $(uname) == "Windows_NT" ]]; then
  tool_bin=$TOOL_BIN
  version=$VERSION
  project=$PROJECT
  language=$LANGUAGE
  bin=$BIN
  moddir=$MODDIR
  project_output=$PROJECT_OUTPUT
fi
source $1