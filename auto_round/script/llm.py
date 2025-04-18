# Copyright (c) 2024 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copyright (c) 2024 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import re
import argparse
import sys


from auto_round.utils import (
    get_fp_layer_names,
    clear_memory,
    is_debug_mode,
    get_device_and_parallelism,
    set_cuda_visible_devices)

os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"


class BasicArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            "--model", "--model_name", "--model_name_or_path", default="facebook/opt-125m", help="model name or path")

        self.add_argument('--eval', action='store_true', help="whether to use eval only mode")

        self.add_argument("--bits", default=4, type=int, help="number of weight bits")

        self.add_argument("--eval_bs", default=None, type=int, help="batch size in evaluation")

        self.add_argument(
            "--device",
            "--devices",
            default="0",
            type=str,
            help="the device to be used for tuning. "
                 "Currently, device settings support CPU, GPU, and HPU."
                 "The default is set to cuda:0,"
                 "allowing for automatic detection and switch to HPU or CPU."
                 "set --device 0,1,2 to use multiple cards.")

        self.add_argument("--asym", action='store_true', help="whether to use asym quantization")

        self.add_argument(
            "--dataset", default="NeelNanda/pile-10k", type=str, help="the dataset for quantization training")

        self.add_argument(
            "--lr", default=None, type=float, help="learning rate, if None, it will be set to 1.0/iters automatically")

        self.add_argument(
            "--minmax_lr",
            default=None,
            type=float,
            help="minmax learning rate, if None, it will beset to be the same with lr")

        self.add_argument("--seed", default=42, type=int, help="random seed")

        self.add_argument("--adam", action='store_true', help="whether to use adam optimizer instead of SignSGD")

        self.add_argument("--gradient_accumulate_steps", default=1, type=int, help="gradient accumulate steps")

        self.add_argument("--nblocks", default=1, type=int, help="how many blocks to tune together")

        self.add_argument("--low_gpu_mem_usage", action='store_true', help="offload intermediate features to cpu")

        self.add_argument("--format", default="auto_round", type=str, help="the format to save the model")

        self.add_argument("--data_type", "--dtype", default='int', help="data type for tuning, 'int', 'mx_fp' and etc")

        self.add_argument(
            "--scale_dtype",
            default='fp16',
            choices=["fp16", "float16", "bf16", "bfloat16", "fp32", "float32"],
            help="scale data type to use for quantization")

        self.add_argument("--tasks",
                          default="lambada_openai,hellaswag,winogrande,piqa,mmlu,wikitext,truthfulqa_mc1," \
                                  "truthfulqa_mc2,openbookqa,boolq,rte,arc_easy,arc_challenge",
                          help="lm-eval tasks")

        self.add_argument(
            "--output_dir", default="./tmp_autoround", type=str, help="the directory to save quantized model")

        self.add_argument("--disable_eval", action='store_true', help="whether to do lm-eval evaluation after tuning")

        self.add_argument(
            "--eval_task_by_task",
            action="store_true",
            help="whether to eval task by task.")

        self.add_argument("--disable_amp", action='store_true', help="disable amp")

        self.add_argument(
            "--disable_minmax_tuning", action='store_true', help="whether to disable enable weight minmax tuning")

        self.add_argument("--enable_norm_bias_tuning", action='store_true', help="whether to enable norm bias tuning")

        self.add_argument(
            "--disable_trust_remote_code", action='store_true', help="whether to disable trust_remote_code")

        self.add_argument(
            "--disable_quanted_input",
            action='store_true',
            help="whether to disuse the output of quantized block to tune the next block")

        self.add_argument("--quant_lm_head", action='store_true', help="whether to quant lm_head")

        self.add_argument(
            "--low_cpu_mem_mode",
            default=0,
            type=int,
            choices=[0, 1, 2],
            help="choose which low cpu memory mode to use. "
                 "Can significantly reduce cpu memory footprint but cost more time."
                 "1 means choose block-wise mode, load the weights of each block"
                 " from disk when tuning and release the memory of the block after tuning."
                 "2 means choose layer-wise mode, load the weights of each layer from disk when tuning,"
                 " minimum memory consumption and also slowest running speed."
                 "others means not use low cpu memory. Default to 0, not use low cpu memory.")

        self.add_argument(
            "--low_cpu_mem_tmp_dir",
            default=None,
            type=str,
            help="temporary work space to store the temporary files "
                 "when using low cpu memory mode. Will remove after tuning.")

        self.add_argument(
            "--model_dtype",
            default=None,
            type=str,
            choices=["fp16", "float16", "bf16", "bfloat16", "fp32", "float32"],
            help="force to convert the dtype, some backends supports fp16 dtype better")

        self.add_argument("--act_bits", default=16, type=int, help="activation bits")

        self.add_argument(
            "--fp_layers", default="", type=str, help="list of Layer names to maintain original data type")

        self.add_argument(
            "--not_use_best_mse",
            action='store_true',
            help="whether to use the iter of best mes loss in the tuning phase")

        self.add_argument(
            "--to_quant_block_names",
            default=None,
            type=str,
            help="Names of quantitative blocks, please use commas to separate them.")

        self.add_argument("--enable_torch_compile", action='store_true',
                          help="whether to enable torch compile")

        self.add_argument("--act_data_type", default=None, type=str, help="activation data type")

        self.add_argument("--disable_act_dynamic", action='store_true', help="activation static quantization")

        self.add_argument("--disable_deterministic_algorithms", action='store_true',
                          help="disable torch deterministic algorithms.")

        self.add_argument("--device_map", default=None, type=str, help="device_map for block in tuning phase")


class EvalArgumentParser(argparse.ArgumentParser):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument(
            "--model", "--model_name", "--model_name_or_path", default="facebook/opt-125m", help="model name or path")
        self.add_argument(
            "--device",
            "--devices",
            default="0",
            type=str,
            help="the device to be used for tuning. "
            "Currently, device settings support CPU, GPU, and HPU."
            "The default is set to cuda:0,"
            "allowing for automatic detection and switch to HPU or CPU."
            "set --device 0,1,2 to use multiple cards.")
        self.add_argument(
            "--tasks",
            "--task",
            default="lambada_openai,hellaswag,winogrande,piqa,mmlu,wikitext,truthfulqa_mc1,"
            "openbookqa,boolq,arc_easy,arc_challenge",
            help="lm-eval tasks")
        self.add_argument(
            "--disable_trust_remote_code", action='store_true', help="whether to disable trust_remote_code")
        self.add_argument("--eval_bs", "--bs", "--batch_size", default=None, type=int, help="batch size in evaluation")
        self.add_argument("--eval_task_by_task", action='store_true', help="whether to eval task by task.")



def setup_parser():
    parser = BasicArgumentParser()

    parser.add_argument("--group_size", default=128, type=int, help="group size")

    parser.add_argument("--batch_size", "--train_bs", "--bs", default=8, type=int, help="train batch size")

    parser.add_argument("--iters", "--iter", default=200, type=int, help="iteration to tune each block")

    parser.add_argument(
        "--seqlen", "--seq_len", default=2048, type=int, help="sequence length of the calibration samples")

    parser.add_argument("--nsamples", "--nsample", default=128, type=int, help="number of samples")

    args = parser.parse_args()
    return args


def setup_best_parser():
    parser = BasicArgumentParser()

    parser.add_argument("--group_size", default=128, type=int, help="group size")

    parser.add_argument("--batch_size", "--train_bs", "--bs", default=8, type=int, help="train batch size")

    parser.add_argument("--iters", "--iter", default=1000, type=int, help="iterations to tune each block")

    parser.add_argument(
        "--seqlen", "--seq_len", default=2048, type=int, help="sequence length of the calibration samples")

    parser.add_argument("--nsamples", "--nsample", default=512, type=int, help="number of samples")

    args = parser.parse_args()
    args.low_gpu_mem_usage = True

    return args


def setup_fast_parser():
    parser = BasicArgumentParser()

    parser.add_argument("--group_size", default=128, type=int, help="group size")

    parser.add_argument("--batch_size", "--train_bs", "--bs", default=4, type=int, help="train batch size")

    parser.add_argument("--iters", default=200, type=int, help="iterations to tune each block")

    parser.add_argument(
        "--seqlen", "--seq_len", default=512, type=int, help="sequence length of the calibration samples")

    parser.add_argument("--nsamples", "--nsample", default=128, type=int, help="number of samples")

    args = parser.parse_args()

    return args


def setup_eval_parser():
    parser = EvalArgumentParser()
    args = parser.parse_args()
    return args


def _gguf_args_check(args):
    from auto_round.utils import logger

    _GGUF_CONFIG = {
        "gguf:q4_0": {
            "bits": 4,
            "act_bits": 16,
            "group_size": 32,
            "asym": False,
        },
        "gguf:q4_1": {
            "bits": 4,
            "act_bits": 16,
            "group_size": 32,
            "asym": True,
        }
    }

    formats = args.format.lower().replace(' ', '').split(",")
    for format in _GGUF_CONFIG:
        if format in formats:
            from pathlib import Path
            from auto_round.export.export_to_gguf.convert import Model
            hparams = Model.load_hparams(Path(args.model))
            model_architecture = hparams["architectures"][0]
            try:
                model_class = Model.from_model_architecture(model_architecture)
            except NotImplementedError:
                logger.error(f"Model {model_architecture} is not supported to export GGUF format")
                sys.exit(1)

            unsupport_list, reset_list = [], []
            gguf_config = _GGUF_CONFIG[format]
            for k, v in gguf_config.items():
                if getattr(args, k) != v:
                    unsupport_list.append(f"{k}={getattr(args, k)}")
                    reset_list.append(f"{k}={v}")
                    setattr(args, k, v)
            if len(unsupport_list) > 0:
                if len(formats) > 1:
                    logger.error(
                        f"format {format} not support for {', '.join(unsupport_list)},"
                        f" please reset to {', '.join(reset_list)}, and retry")
                    exit(-1)
                else:
                    logger.error(
                        f"format {format} not support for {', '.join(unsupport_list)},"
                        f" reset to {', '.join(reset_list)}.")
            logger.info(f"export format {format}, sym = {not args.asym}, group_size = {args.group_size}")

    return args


def tune(args):
    import transformers

    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoModel, AutoConfig, AutoProcessor

    from auto_round import AutoRoundConfig
    from auto_round.utils import detect_device, get_library_version, detect_device_count
    from auto_round.utils import logger

    tasks = args.tasks
    if args.format is None:
        args.format = "auto_round"
    supported_formats = [
        "auto_round", "auto_gptq", "auto_awq", "auto_round:auto_gptq", "auto_round:auto_awq", "auto_gptq:marlin",
        "gguf:q4_0", "gguf:q4_1", "itrex", "itrex_xpu", "fake"
    ]
    formats = args.format.lower().replace(' ', '').split(",")
    for format in formats:
        if format not in supported_formats:
            raise ValueError(f"{format} is not supported, we only support {supported_formats}")

    args = _gguf_args_check(args)

    if "auto_gptq" in args.format and args.asym is True:
        logger.warning("The auto_gptq kernel has issues with asymmetric quantization. "
                       "It is recommended to use sym quantization or --format='auto_round'")

    if "marlin" in args.format and args.asym is True:
        assert False, "marlin backend only supports sym quantization, please remove --asym"

    ##must set this before import torch
    set_cuda_visible_devices(args.device)
    device_str, use_auto_mapping = get_device_and_parallelism(args.device)

    import torch
    if not args.disable_deterministic_algorithms:
        torch.use_deterministic_algorithms(True, warn_only=True)
        # logger.info("`torch.use_deterministic_algorithms` is enabled by default for reproducibility "
        #             "and can be disabled using the `--disable_deterministic_algorithms` argument.")

    if args.enable_torch_compile:
        logger.info("`torch.compile` is enabled to reduce tuning costs. "
                    "If it causes issues, you can disable it by remove `--enable_torch_compile` argument.")

    model_name = args.model
    if model_name[-1] == "/":
        model_name = model_name[:-1]
    logger.info(f"start to quantize {model_name}")
    torch_dtype = "auto"
    if device_str is not None and "hpu" in device_str:
        torch_dtype = torch.bfloat16

    is_glm = bool(re.search("chatglm", model_name.lower()))
    low_cpu_mem_usage = False

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=not args.disable_trust_remote_code)

    model_cls = AutoModel if is_glm else AutoModelForCausalLM

    if args.low_cpu_mem_tmp_dir is None:
        args.low_cpu_mem_tmp_dir = os.path.join(args.output_dir, "low_cpu_mem_tmp")
    if args.low_cpu_mem_mode == 2:
        from auto_round.low_cpu_mem.utils import load_model_with_hooks
        model = load_model_with_hooks(
            model_name,
            model_cls,
            device=device_str,
            clean_weight=True,
            saved_path=args.low_cpu_mem_tmp_dir,
            torch_dtype=torch_dtype,
            trust_remote_code=not args.disable_trust_remote_code)
    elif args.low_cpu_mem_mode == 1:
        from auto_round.low_cpu_mem.utils import load_empty_model
        low_cpu_mem_usage = True
        model = load_empty_model(
            model_name,
            model_cls,
            device=device_str,
            saved_path=args.low_cpu_mem_tmp_dir,
            torch_dtype=torch_dtype,
            trust_remote_code=not args.disable_trust_remote_code)
    else:
        model = model_cls.from_pretrained(
            model_name,
            low_cpu_mem_usage=True,
            torch_dtype=torch_dtype,
            trust_remote_code=not args.disable_trust_remote_code,
            device_map="auto" if use_auto_mapping else None)

    from auto_round import AutoRound, AutoRoundAdam

    model = model.eval()
    seqlen = args.seqlen

    if args.model_dtype != None:
        try:
            if args.model_dtype == "float16" or args.model_dtype == "fp16":
                model = model.to(torch.float16)
            elif args.model_dtype == "bfloat16" or args.model_dtype == "bfp16" or args.model_dtype == "bf16":
                model = model.to(torch.bfloat16)
            elif args.model_dtype == "float32" or args.model_dtype == "fp32":
                model = model.to(torch.float32)
        except:
            logger.error("please use more device to fit the device or just use one device")
            exit()

    if hasattr(tokenizer, "model_max_length"):
        if tokenizer.model_max_length < seqlen:
            logger.info(
                f"change sequence length to {tokenizer.model_max_length} due to the limitation of model_max_length")
            seqlen = min(seqlen, tokenizer.model_max_length)
            args.seqlen = seqlen

    if "bloom" in model_name:
        args.low_gpu_mem_usage = False

    round = AutoRound
    if args.adam:
        round = AutoRoundAdam

    layer_config = {}
    for n, m in model.named_modules():
        if isinstance(m, torch.nn.Linear) or isinstance(m, transformers.modeling_utils.Conv1D):
            if m.weight.shape[0] % 32 != 0 or m.weight.shape[1] % 32 != 0:
                layer_config[n] = {"bits": 16}
                logger.info(
                    f"{n} will not be quantized due to its shape not being divisible by 32,"
                    " resulting in an exporting issue to autogptq")

    not_quantize_layer_names = get_fp_layer_names(model, args.fp_layers)
    for name in not_quantize_layer_names:
        layer_config[name] = {"bits": 16}
    if len(not_quantize_layer_names) > 0:
        logger.info(f"{not_quantize_layer_names} will not be quantized.")
        for format in formats:
            if "auto_round" not in format and "fake" not in format and "awq" not in format:
                ##TODO gptq could support some mixed precision config
                logger.warning(f"mixed precision exporting does not support {format} currently")

    lm_head_layer_name = "lm_head"
    for n, _ in model.named_modules():
        lm_head_layer_name = n
    if args.quant_lm_head:
        config = AutoConfig.from_pretrained(model_name, trust_remote_code=not args.disable_trust_remote_code)
        if config.tie_word_embeddings and hasattr(model, "_tied_weights_keys"):
            tied_keys = model._tied_weights_keys
            for item in tied_keys:
                if lm_head_layer_name in item:  ##TODO extend to encoder-decoder layer, seq classification model
                    args.quant_lm_head = False
                    logger.warning(
                        f"reset `quant_lm_head` to `False` as quantizing lm_head with tied weights has not been "
                        f"supported currently")
                    break

    if args.quant_lm_head:
        layer_config[lm_head_layer_name] = {"bits": args.bits}
        for format in formats:
            if "auto_round" not in format and "fake" not in format:
                auto_round_formats = [s for s in supported_formats if s.startswith("auto_round")]
                raise ValueError(
                    f"{format} is not supported for lm-head quantization, please change to {auto_round_formats}")

    if "auto_awq" in args.format:
        from auto_round.utils import check_awq_gemm_compatibility
        awq_supported, info = check_awq_gemm_compatibility(
            model, args.bits, args.group_size, not args.asym, layer_config)
        if not awq_supported:
            logger.warning(f"The AutoAWQ format may not be supported due to {info}")

    enable_torch_compile = True if "--enable_torch_compile" in sys.argv else False

    autoround = round(
        model,
        tokenizer,
        args.bits,
        args.group_size,
        sym=not args.asym,
        batch_size=args.batch_size,
        dataset=args.dataset,
        seqlen=seqlen,
        nblocks=args.nblocks,
        iters=args.iters,
        lr=args.lr,
        minmax_lr=args.minmax_lr,
        enable_quanted_input=not args.disable_quanted_input,
        device=device_str,
        amp=not args.disable_amp,
        nsamples=args.nsamples,
        seed=args.seed,
        low_gpu_mem_usage=args.low_gpu_mem_usage,
        scale_dtype=args.scale_dtype,
        gradient_accumulate_steps=args.gradient_accumulate_steps,
        layer_config=layer_config,
        enable_minmax_tuning=not args.disable_minmax_tuning,
        act_bits=args.act_bits,
        low_cpu_mem_usage=low_cpu_mem_usage,
        data_type=args.data_type,
        enable_norm_bias_tuning=args.enable_norm_bias_tuning,
        not_use_best_mse=args.not_use_best_mse,
        to_quant_block_names=args.to_quant_block_names,
        enable_torch_compile=enable_torch_compile,
        act_data_type=args.act_data_type,
        act_dynamic=not args.disable_act_dynamic,
        device_map=args.device_map)
    model, _ = autoround.quantize()
    model_name = args.model.rstrip("/")
    if args.low_cpu_mem_mode == 1 or args.low_cpu_mem_mode == 2:
        import shutil
        shutil.rmtree(args.low_cpu_mem_tmp_dir, ignore_errors=True)

    model.eval()
    clear_memory()

    if model_name.split('/')[-1].strip('.') == "":
        export_dir = os.path.join(args.output_dir, f"w{args.bits}g{args.group_size}")
    else:
        export_dir = os.path.join(args.output_dir, model_name.split('/')[-1] + f"-w{args.bits}g{args.group_size}")

    format_list = args.format.replace(' ', '').split(',')
    inplace = False if len(format_list) > 1 else True
    eval_folder = None
    for format_ in format_list:
        save_format_ = format_.replace(":", "-")
        save_format_ = save_format_.replace("_", "-")
        save_folder = f'{export_dir}-{save_format_}'
        autoround.save_quantized(save_folder, format=format_, inplace=inplace)
        if 'gguf' in format_:
            gguf_format = format_.upper().split(":")[-1]
            if not any([file.endswith(f"{gguf_format}.gguf") for file in os.listdir(save_folder)]):
                logger.error(f"fail to export {format_}")
        else:
            eval_folder = save_folder

    lm_eval_version = get_library_version("lm-eval")

    if isinstance(tasks, str):
        tasks = tasks.split(',')

    if not args.disable_eval and eval_folder is not None:
        from lm_eval.utils import make_table  # pylint: disable=E0401

        logger.info(f"Using lm-eval version {lm_eval_version}")

        if args.act_bits <= 8:
            if hasattr(model, "hf_device_map") and len(model.hf_device_map) > 1:
                from accelerate.big_modeling import dispatch_model

                dispatch_model(model, model.hf_device_map)
                user_model = model
            else:
                device_str = detect_device(device_str)
                user_model = model.to(device_str)

            if args.eval_task_by_task:
                eval_task_by_task(user_model, device=device_str, tasks=args.tasks, batch_size=args.eval_bs)
            else:
                if args.eval_bs is None or args.eval_bs == "auto":
                    logger.warning("This API does not support auto currently, reset eval_bs to 16")
                    args.eval_bs = 16
                from auto_round.eval.evaluation import simple_evaluate_user_model
                res = simple_evaluate_user_model(
                    user_model, tokenizer, tasks=tasks, batch_size=args.eval_bs, device=device_str)
                print(make_table(res))
        else:
            if args.eval_task_by_task:
                eval_task_by_task(eval_folder, device=device_str, tasks=args.tasks, batch_size=args.eval_bs)
            else:
                from auto_round.eval.evaluation import simple_evaluate
                tasks, model_args, device_str = _eval_init(
                    args.tasks, eval_folder, args.device, args.disable_trust_remote_code)
                res = simple_evaluate(
                    model="hf", model_args=model_args, tasks=tasks, device=device_str, batch_size=args.eval_bs)
                print(make_table(res))


def _eval_init(tasks, model_path, device, disable_trust_remote_code=False):
    set_cuda_visible_devices(device)
    device_str, parallelism = get_device_and_parallelism(device)
    ##model_args = f'pretrained={model_path},trust_remote_code={not disable_trust_remote_code},add_bos_token=True'
    model_args = f'pretrained={model_path},trust_remote_code={not disable_trust_remote_code}'
    if parallelism:
        model_args += ",parallelize=True"
    if isinstance(tasks, str):
        tasks = tasks.split(',')
    return tasks, model_args, device_str


def eval(args):
    tasks, model_args, device_str = _eval_init(args.tasks, args.model, args.device, args.disable_trust_remote_code)

    # load after _eval_int in order to make sure import torch after set CUDA_VISBILE_DEVICES
    from auto_round.eval.evaluation import simple_evaluate

    res = simple_evaluate(model="hf", model_args=model_args, tasks=tasks, device=device_str, batch_size=args.eval_bs)

    from lm_eval.utils import make_table  # pylint: disable=E0401
    print(make_table(res))


def eval_task_by_task(model, device, tasks, batch_size=None, max_batch_size=64, trust_remote_code=True):
    set_cuda_visible_devices(device)
    device_str, parallelism = get_device_and_parallelism(device)

    # load after _eval_int in order to make sure import torch after set CUDA_VISBILE_DEVICES
    import traceback
    from auto_round.utils import logger
    from lm_eval import simple_evaluate as lm_simple_evaluate
    from lm_eval.models.huggingface import HFLM

    # from auto_round import AutoRoundConfig
    if batch_size is None:
        batch_size = "auto"
    if not isinstance(model, str):
        parallelism = False
    hflm = HFLM(
        pretrained=model,
        device=device_str,
        batch_size=batch_size,
        max_batch_size=max_batch_size,
        parallelize=parallelism,
        trust_remote_code=trust_remote_code)

    if isinstance(tasks, str):
        tasks = tasks.replace(" ", "").split(",")

    from lm_eval.utils import make_table  # pylint: disable=E0401
    res_all = {}
    res_keys = ["results", "versions", "n-shot", "higher_is_better"]
    for task in tasks:
        try:
            res = lm_simple_evaluate(model=hflm, model_args=None, device=device_str, tasks=task, batch_size=batch_size)
        except RuntimeError as e:
            if "CUDA out of memory" in str(e) or "MODULE:PT_DEVMEM" in str(e):
                try:
                    logger.warning("Out of memory, reset batch_size to 1 and re-try.")
                    res = lm_simple_evaluate(model=hflm, model_args=None, device=device_str, tasks=task, batch_size=1)
                except Exception as e:
                    traceback.print_exc()
                    continue
            else:
                traceback.print_exc()
                continue
        except Exception as e:
            traceback.print_exc()
            continue

        if not res_all:
            res_all = res
        else:
            for key in res_keys:
                res_all[key].update(res[key])
        print(make_table(res_all))
