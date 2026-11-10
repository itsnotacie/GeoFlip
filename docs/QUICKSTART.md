# Score your world-model videos

From the cloned repository root:

```bash
python -m pip install -e '.[download,video,http]'
```

## 1. Download the data

The dataset is available at [DreamingLow/GeoFlip](https://huggingface.co/datasets/DreamingLow/GeoFlip). Downloads do not require a token.

```bash
python scripts/download_dataset.py --repo DreamingLow/GeoFlip \
  --scope full --output data/geoflip
```

The downloader resolves the requested revision to an immutable commit and verifies every selected file against SHA-256 checksums. Use `--scope inputs` to download only first frames, generation prompts, and scope lists. Use `--scope evaluation` to add evaluator metadata and frozen baseline predictions without reference video files. `--scope full` downloads everything, including references and the evaluation toolkit snapshot.

## 2. Generate videos with your own model

Select ids from `splits/paper-main.json` for the 442-condition paper comparison, or `splits/core.json` for all 964 core conditions. Look up each id in `inputs/manifest.jsonl`. Give your model only the specified first frame and prompt. Each paired condition must be generated independently. Preserve the native output; do not pad, freeze, interpolate, or change playback speed to meet the requested horizon.

Create `results/my-model/submission.json`:

```json
{
  "model": "your-model-version",
  "generation": {"seed": 0, "sampling_steps": 50, "guidance": 5.0},
  "videos": [
    {"id": "ID_FROM_THE_MANIFEST", "video": "videos/ID_FROM_THE_MANIFEST.mp4"}
  ]
}
```

Use actual settings and filenames. Video paths are relative to `submission.json`. Keep separate runs in separate submissions; do not pick favorable seeds per condition.

## 3. Validate your outputs

```bash
geoflip validate --data data/geoflip --subset paper-main \
  --submission results/my-model/submission.json --out results/my-model/validation.json
```

Missing videos and invalid timestamps are reported. The validation report distinguishes file validity from whether the native output reaches the sample's required observation time.

## 4. Read events and structural violations

Use a vision-language judge endpoint that accepts the common chat-completions JSON protocol. Set its credential in `GEOFLIP_JUDGE_API_KEY` and use its explicit model/version:

```bash
geoflip judge --data data/geoflip --subset paper-main \
  --submission results/my-model/submission.json \
  --base-url https://your-provider.example/v1 --model your-judge-version \
  --profile observation-8 --out results/my-model/judgments.jsonl
```

`--allow-no-key` supports an endpoint that does not require authentication. Judge inference is optional if you already have per-condition judgments in this format:

```json
{"id":"ID_FROM_THE_MANIFEST","label":"fell","violation":"clear","confidence":0.9,"evidence":"The object descends below the support."}
```

Manual annotations can use the same file format. Declare the annotator or judge and the sampling protocol when reporting results. Do not infer the generated label from the reference label.

The prompt is in `prompts/judge.txt`, with task definitions in `prompts/tasks.json`. Judging receives generated frames and task definitions, without reference labels, pair identities, reference futures, model names, or generation prompts. Both video hash and prompt fingerprints are recorded. Successful matching judgments can be reused on resume; failed rows remain uncertain in scoring.

## 5. Score

The judge command writes a score report automatically. To re-score an existing judgment file without API calls:

```bash
geoflip score --data data/geoflip --subset paper-main \
  --predictions results/my-model/judgments.jsonl --out results/my-model/scores.json
```

Report `event_percent`, `structure_percent`, coverage, subset, judge model/version, and sampling profile. Missing and uncertain predictions remain in the denominators. Details and equations are in [EVALUATION.md](EVALUATION.md).

## 6. Verify the released baseline numbers

```bash
geoflip baselines --data data/geoflip --subset paper-main \
  --judge gpt-6-astra --out reproduced-main.json
```

This re-scores the 16 historical model predictions. All 32 event/structure numbers match the main paper table after rounding. It does not invoke a model or API.

Optional diagnostic reference similarity:

```bash
geoflip similarity --data data/geoflip --subset paper-main \
  --submission results/my-model/submission.json --out results/my-model/reference-diagnostic.json
```

This GeoFlip diagnostic is separate from the paper's 40-clip PSNR/SSIM benchmark. Do not interchange them in an overall ranking.
