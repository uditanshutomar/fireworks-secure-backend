#!/bin/bash
# Fine-tune Nemotron Nano 3 on Fireworks with the exploit-filtered SFT data, then deploy it.
# firectl refuses account-changing commands from an AI agent, so a person runs this:
#   scripts/finetune.sh start    # upload data/sft_fireworks.jsonl, start the LoRA SFT job
#   scripts/finetune.sh status   # job state
#   scripts/finetune.sh deploy   # deploy the tuned model when the job is COMPLETED
# Uses FIREWORKS_API_KEY_FT from .env (the account with dataset uploads enabled),
# else FIREWORKS_API_KEY.
set -euo pipefail
cd "$(dirname "$0")/.."
key=$(sed -n 's/^FIREWORKS_API_KEY_FT=//p' .env)
[ -n "$key" ] || key=$(sed -n 's/^FIREWORKS_API_KEY=//p' .env)
fc() { ~/.local/bin/firectl --api-key "$key" "$@" 2>&1 | grep -v -i deprecat; }
BASE=accounts/fireworks/models/nemotron-nano-3-30b-a3b
DATASET=secure-backend-sft
MODEL=secure-backend-nano3-lora
JOB=secure-backend-sft

case "${1:-}" in
  start)
    fc dataset create "$DATASET" data/sft_fireworks.jsonl
    fc sftj create --base-model "$BASE" --dataset "$DATASET" --output-model "$MODEL" \
      --epochs 3 --lora-rank 16 --max-context-length 8192 --display-name "$JOB"
    ;;
  status)
    fc sftj list | head -5
    ;;
  deploy)
    fc deployment create "$MODEL" --deployment-shape default --display-name secure-backend-nano3-tuned \
      --min-replica-count 0 --max-replica-count 1 --scale-to-zero-window 30m
    ;;
  *)
    echo "usage: $0 start|status|deploy" >&2; exit 2 ;;
esac
