# Data format

## Model input

`inputs/manifest.jsonl` has one record per condition:

| Field | Meaning |
| --- | --- |
| `id` | Condition identifier |
| `first_frame` | Relative path to the input PNG |
| `prompt` | Video-generation prompt |
| `target_duration_s` | Requested video duration |
| `target_fps` | Requested frame rate |

The input manifest contains no outcome labels or pair membership. `first_frames/metadata.jsonl` provides the same inputs for Hugging Face image loading.

## Evaluator files

`evaluation/truth.jsonl` contains each condition's task, category, reference label, allowed labels, reference-video path, observation time, original partition, and prompt metadata. Auxiliary controls have no pair membership.

`evaluation/pairs.jsonl` lists the 482 core pairs. Each pair has two distinct reference labels and a shared generation prompt. A/B indicates pair ordering, not an outcome. Pair-complete accuracy uses only pairs with both conditions in the selected subset.

### Generation prompts

Use `prompt` from `inputs/manifest.jsonl` for video generation. `source_prompt` in the evaluator metadata preserves the original instruction. For records marked `release-video-adaptation-v1`, that original instruction requests classification; the released generation prompt requests video continuation. Other generation prompts retain the original instructions. Exact generation requests for every historical model are not included.

## References

The dataset includes first frames and reference videos for **964 core conditions** plus **16 neutral controls**. First-frame pixels, compressed video frames, and reference timestamps are preserved.

Reference videos and outcome labels are for evaluation. Simulation scene-production assets and the separate 40-clip reference set are not included.

## Baselines

`baselines/judgments.jsonl` contains condition identifiers, model and judge names, evaluation subsets, event predictions, and structural judgments. GPT predictions reproduce the paper's main-table event and structure scores. Additional Qwen3-VL predictions are identified separately; the independently run Opus raw judgments are not included.

`baselines/paper-results.json` contains the paper's 16-model aggregate table, including the separate 40-clip PSNR/SSIM values.

## File integrity

`SHA256SUMS.json` lists the SHA-256 hash of every included file except itself. Downloads resolve to one immutable HF commit and verify the selected files. `dataset_info.json` lists dataset and subset sizes.
