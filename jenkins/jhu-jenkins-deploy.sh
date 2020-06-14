#!/usr/bin/env bash
#
# JHU indicator: Jenkins deploy
#

set -exo pipefail
source ~/.bash_profile

#
# Deploy
#

#indicator="jhu"

cd "${WORKSPACE}/ansible" || exit

# Ansible!
ansible-playbook ansible-deploy.yaml --extra-vars "indicator=${INDICATOR}" -i inventory
