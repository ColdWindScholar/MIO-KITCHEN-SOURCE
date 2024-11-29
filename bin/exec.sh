#!/bin/bash
# The MIO-KITCHEN-PROJECT
# Yes!
tool_author="ColdWindSolar"
if [[ $(uname) == "Windows_NT" ]]; then
  echo "[Nt]Preparing Environment Variables..."
  for i in $(set)
  do
    if [[ "$i" == "*=*" ]]; then
      if [[ "$i" == "*\n*" || "$i" == "*\r*" || "$i" == "'" || "$i" == '"' ||   "$i" == '$*' ]];then
        continue
      fi
      value_name=$(echo ${i%=*} | tr A-Z a-z)
      if [[ "${value_name}" == 'ifs' ]] || [[ "${value_name}" == 'ps*' ]]; then
        continue
      fi
      eval "${value_name}=${i#*=}"
    fi
  done
  echo "[Nt]Executing Script..."
fi
source $1