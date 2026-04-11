#!/usr/bin/env bash
prompt="${1:-}"
case "$prompt" in
  *Username*) printf '%s' "x-access-token" ;;
  *Password*) cat /opt/clara-care/.secrets/github_pat.txt ;;
  *) printf '%s' "" ;;
esac
