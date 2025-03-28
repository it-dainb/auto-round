#!/bin/bash
set -x
device=0

model_path='./tmp_autoround'
model=Phi-3-vision-128k-instruct

CUDA_VISIBLE_DEVICES=$device python3 eval_042/evaluation.py \
--model_name ${model_path}/${model} \
--trust_remote_code \
--eval_bs 16
