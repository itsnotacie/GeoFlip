# Evaluation protocol

The evaluation protocol follows [GeoFlip Preview, arXiv v2](https://arxiv.org/abs/2610.42002v2). It contains 482 paired tests and 964 core reference conditions. Auxiliary controls are kept separately.

## Frozen scopes

| Subset | Conditions | Purpose |
| --- | ---: | --- |
| `core` | 964 | Complete paired-reference inventory, 482 pairs |
| `auxiliary` | 16 | Unpaired neutral controls, excluded from core count |
| `paper-pool` | 720 | Historical selected inference pool, including four auxiliary controls |
| `paper-main` | 442 | 438 core conditions + 4 controls for the 16-model main comparison, 34 tasks |
| `cross-judge` | 346 | 342 core conditions + 4 controls; original source judge identified as Qwen3-VL |

Comparisons use the fixed condition lists in `splits/`. These are evaluation scopes, not train/test splits; original partitions are recorded in the evaluator metadata.

`inputs/manifest.jsonl` and the first-frame files are model-facing. Pair identities, task taxonomies, labels, observation times, and reference futures reside in `evaluation/`. Never pass evaluation files or contact sheets to a generative model. The download script's default `inputs` scope omits those evaluator files.

## Event correctness

For each task, compute recall separately for each reference class present in the selected subset. Average class recall within the task, then average tasks with equal weight. Report the result as a percentage:

```text
Event = 100 × mean_over_tasks(mean_over_supported_reference_classes(recall))
```

Missing predictions, unknown labels, `other`, and `uncertain` count incorrect. Classes absent from the frozen truth subset are not invented as extra denominator terms. The task set and denominator are defined by the requested truth scope, not by successfully judged rows. A model's own predictions cannot change its evaluation scope.

## Structural integrity

Each condition receives an independent `clear`, `flagged`, or `uncertain` structural judgment. Visible deformation, extra or missing components, changed support geometry and other scene violations can be flagged even when the predicted event is correct.

```text
Structure = 100 × mean_over_tasks(number_explicitly_clear / all_task_conditions)
```

Flagged, uncertain, missing, failed and unrecognized structural outcomes stay in the denominator. The paper's structure score uses the `violation` field of the judgments.

Optional pair-complete accuracy counts a pair correct only if both events are correct. Only pairs whose two members are present in the requested scope enter this supplementary metric. It does not replace the paper's event score.

## Judge prompt and frame sampling

`prompts/judge.txt` and `prompts/tasks.json` provide the event/structure prompt, task definitions, and label sets. The prompt instructs the judge to describe observed motion rather than infer the expected outcome from geometry.

Each judge request contains up to eight chronologically ordered images, resized to fit 832 × 480 without cropping or upscaling beyond that bound. Sampling uses native presentation timestamps without changing playback speed or inserting frames.

Two explicitly named profiles are available:

- `paper-prefix-8`: samples up to eight distinct frames from the prefix ending at 119/30 seconds. Short clips retain their actual length; time coverage is reported separately.
- `observation-8` (default for new submissions): extends that prefix when a task's declared observation time is later. If the generated clip does not reach the required observation time, the condition remains uncertain and incorrect rather than asking the judge to guess an unseen event.

The profile, exact sampled times, frame indices, resize rule, video hash and prompt hashes are recorded. New judge runs must disclose the provider's exact model/version. Different judge versions or sampling profiles are not silently interchangeable.

Baseline reproduction uses the released judgments. Original provider request envelopes are not included; new judge runs should report their own endpoint, model version, and sampling profile.

## Reference similarity and overall ranking

The paper's PSNR and SSIM columns come from a separate 40-clip evaluation, not from the 964-condition GeoFlip inventory. Those published aggregate values are included in `baselines/paper-results.json`; the 40-clip reference media are not included.

`geoflip similarity` computes an explicitly separate GeoFlip reference diagnostic: 16 common timestamps on the overlapping native timeline, nearest available frames, resize to 256 × 256, MSE over normalized RGB, PSNR with a documented 99 dB cap for zero error, and SSIM with an 11 × 11 Gaussian window and standard constants. It reports overlap duration and failures. Do not substitute these diagnostic numbers for the paper's 40-clip columns.

For the original four component columns, `geoflip rank` implements the paper's overall ranking:

```text
similarity_rank = (rank(PSNR) + rank(SSIM)) / 2
mean_rank = (rank(Event) + rank(Structure) + similarity_rank) / 3
```

Higher component scores are better. Component ties receive average ranks; equal overall values share a competition rank. Overall rank depends on the comparison model pool. A standalone new model should report its component scores, scope, coverage and judge settings before claiming a rank against the frozen paper table.

## Re-score released results

```bash
geoflip baselines --data data/geoflip --subset paper-main \
  --judge gpt-6-astra --out reproduced-main.json
geoflip baselines --data data/geoflip --subset cross-judge \
  --judge Qwen3-VL-32B-Instruct --out reproduced-source-judge.json
geoflip score --data data/geoflip --subset paper-main \
  --predictions my-judgments.jsonl --out my-scores.json
```

All 32 main-table event/structure values across the 16 models were checked against the paper's rounded numbers. Re-scoring does not call an API or require model weights.

## Released judge results

The released GPT predictions reproduce all 32 main-table event/structure values. Additional predictions use `Qwen3-VL-32B-Instruct`. The paper's independent Opus evaluation was run separately; its raw judgments and request configuration are not included.
