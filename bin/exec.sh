#!/bin/bash
# The MIO-KITCHEN-PROJECT
# I know Its Too Slowly On Windows,But I have not any better solutions.
if [[ $(uname) == "Windows_NT" ]]; then
  echo "[Nt]Preparing Environment Variables..."
  for i in $(set)
  do
      if [[ "$i" != "*=*" ||  "$i" == "*\n*" || "$i" == "*\r*" || "$i" == "'" || "$i" == '"' ||   "$i" == '$*' ]]; then
        continue
      fi
      value_name=${i%=*}
      if [[ "${value_name}" == 'IFS' || "${value_name}" == 'PS*'  ]]; then
        continue
      fi
      value_name=$(echo ${value_name} | tr A-Z a-z)
      eval "${value_name}=${i#*=}"
  done
  echo "[Nt]Executing Script..."
fi
source $1