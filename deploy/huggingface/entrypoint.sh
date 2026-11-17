#!/bin/sh
# supervisord stays in the background so its log files can be tailed to
# the container stdout that Hugging Face shows. PID 1 is this shell.
set -eu
supervisord -c /home/user/app/deploy/huggingface/supervisord.conf &
supervisor_pid=$!
trap 'kill -TERM "$supervisor_pid"; wait "$supervisor_pid"' TERM INT
tail -n +1 -F /tmp/billing.log /tmp/processor.log /tmp/simulator.log /tmp/nginx.log &
wait "$supervisor_pid"
