# GeoFlip Preview

**Benchmarking Geometry-Sensitive Physics in Video Generation** · [Paper](https://arxiv.org/abs/2610.42002v2) · [Project page](https://itsnotacie.github.io/GeoFlip/) · [Dataset](https://huggingface.co/datasets/DreamingLow/GeoFlip)

GeoFlip contains **482 paired tests / 964 reference videos** across six physical mechanisms. This repository provides dataset downloads, generation and judge prompts, evaluation code, and baseline predictions.

Yuqi Li and Junming Liu contributed equally. Hao Wu is the corresponding author.

## Evaluate your model

```bash
python -m pip install -e '.[download,video,http]'
python scripts/download_dataset.py --repo DreamingLow/GeoFlip --scope full --output data/geoflip
```

Follow the [quickstart](docs/QUICKSTART.md) to generate videos, validate your outputs, obtain judgments, and compute scores.

To reproduce the 16-model baseline scores without API calls:

```bash
geoflip baselines --data data/geoflip --subset paper-main --judge gpt-6-astra --out reproduced-main.json
```

- [Quickstart and submission format](docs/QUICKSTART.md)
- [Metrics, evaluation subsets, and frame sampling](docs/EVALUATION.md)
- [Data format and generation prompts](docs/DATA_FORMAT.md)
- [Judge prompt](prompts/judge.txt) and [task definitions](prompts/tasks.json)

## Evaluation

Event correctness and structural integrity use **442 conditions / 34 tasks** for the paper's main comparison. The released GPT judgments reproduce all 32 event/structure values across 16 models. PSNR and SSIM use a separate **40-clip** benchmark. See the [evaluation protocol](docs/EVALUATION.md) for subset definitions, judge versions, and ranking.

## Project page

To preview the website locally:

```bash
python3 scripts/build.py
python3 scripts/preview.py --port 8080
```

Open the URL printed by the preview command.

## Data usage

Dataset usage terms are in [LICENSE.txt](https://huggingface.co/datasets/DreamingLow/GeoFlip/blob/main/LICENSE.txt).
