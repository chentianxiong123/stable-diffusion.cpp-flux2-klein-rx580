# stable-diffusion.cpp-flux2-klein-rx580

FLUX.2 Klein CLI fork based on `stable-diffusion.cpp`, focused on local Vulkan execution, RX580/RX590-class GPUs, and explicit one-stage-at-a-time CLI workflows.

This fork is not intended as an upstream PR. It is a standalone working branch for FLUX.2 Klein experiments where every pipeline stage can be called like a function with clear inputs and outputs.

## What This Fork Adds

- FLUX.2 Klein local CLI workflow.
- Qwen3-VL / mmproj vision encoder compatibility work.
- Atomic `sd-cli --stage` execution:
  - `llm_encode_vision`
  - `llm_encode_text`
  - `vae_encode`
  - `diffuse`
  - `vae_decode`
- Vulkan-friendly staged execution for RX580/RX590-class cards.
- Explicit cache directories for stage input/output.
- `--mask` support in atomic `diffuse`.
- Manual mask drawing utility without Python generation workflow.

## Design Rules

- Do not run comma-separated stages.
- Run each stage in a separate `sd-cli` process.
- Treat every stage as a callable function: inputs are paths/parameters, outputs are cache directories or final images.
- Keep Python out of generation. Python is only for manual mask drawing or simple file inspection.
- For release-style runs, keep only the final output image. Intermediate cache directories should be temporary and deleted after success.
- Do not commit model files, images, local inputs, local outputs, or run caches.

## GPU Notes

The local target is AMD RX580/RX590-class Vulkan execution.

On this machine:

```powershell
Vulkan0 = integrated AMD GPU
Vulkan1 = AMD Radeon RX590 GME
```

Set this before running on RX580/RX590-class Vulkan drivers:

```powershell
$env:GGML_VK_FORCE_MAX_BUFFER_SIZE = "4294967296"
```

Prefer explicit backend selection:

```powershell
--backend "te=Vulkan1,diffusion=Vulkan1,vae=Vulkan1"
```

For some atomic stages, a narrower backend is enough:

```powershell
--backend "te=Vulkan1"
--backend "vae=Vulkan1"
--backend "diffusion=Vulkan1,vae=Vulkan1"
```

## Build

Use the existing CMake flow from `stable-diffusion.cpp`.

Debug build example:

```powershell
cmake --build build --config Debug --target stable-diffusion.cpp-flux2-klein-rx580
```

The local development binary is:

```powershell
.\build\bin\Debug\stable-diffusion.cpp-flux2-klein-rx580.exe
```

## Model Paths

Expected local model paths:

```powershell
$Diffusion = "D:\models\flux-2-klein-9b-Q4_0.gguf"
$LLM       = "D:\models\qwen3-vl-7b-llm-q4_k_m.gguf"
$Vision    = "D:\models\mmproj-Qwen3VL-8B-Instruct-F16.gguf"
$VAE       = "D:\models\flux2-vae.safetensors"
```

Model files are intentionally ignored by Git.

## Atomic Stage Interface

Each stage should be called independently.

| Stage | Input | Output |
|---|---|---|
| `llm_encode_vision` | `--ref-image`, `--llm`, `--llm_vision` | `--vision-out` |
| `llm_encode_text` | `--prompt`, `--llm`, optional `--vision-out` | `--llm-out` |
| `vae_encode` | `--ref-image`, `--vae` | `--vae-out` |
| `diffuse` | `--llm-out`, optional `--vae-out`, optional `--init-img`, optional `--mask` | `--diffuse-out` |
| `vae_decode` | `--diffuse-out`, `--vae` | `-o` |

If you pass a comma-separated stage list, the CLI rejects it. This keeps memory ownership and cache handoff explicit.

## Example: Text/Reference Inpaint Without Vision

This is the current lightweight route for RX580/RX590-class testing.

```powershell
$env:GGML_VK_FORCE_MAX_BUFFER_SIZE = "4294967296"

$Cli = ".\build\bin\Debug\stable-diffusion.cpp-flux2-klein-rx580.exe"
$Diffusion = "D:\models\flux-2-klein-9b-Q4_0.gguf"
$LLM = "D:\models\qwen3-vl-7b-llm-q4_k_m.gguf"
$VAE = "D:\models\flux2-vae.safetensors"

$W = 384
$H = 576
$Seed = 42
$Steps = 4
$Work = "$env:TEMP\flux2-klein-run"
$Out = "D:\output\output.png"

Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Work | Out-Null
```

Text encoding:

```powershell
& $Cli --stage llm_encode_text --backend "te=Vulkan1" `
  --diffusion-model $Diffusion --vae $VAE --llm $LLM `
  -W $W -H $H --seed $Seed `
  --llm-out "$Work\llm" `
  --prompt "local inpainting, preserve the original image structure, natural blending"
```

Reference VAE encoding:

```powershell
& $Cli --stage vae_encode --backend "vae=Vulkan1" `
  --diffusion-model $Diffusion --vae $VAE `
  -W $W -H $H --seed $Seed `
  --vae-out "$Work\vae" `
  --ref-image "D:\path\reference.png"
```

Diffusion:

```powershell
& $Cli --stage diffuse --backend "diffusion=Vulkan1,vae=Vulkan1" `
  --diffusion-model $Diffusion --vae $VAE `
  -W $W -H $H --seed $Seed `
  --llm-out "$Work\llm" `
  --vae-out "$Work\vae" `
  --diffuse-out "$Work\diffuse" `
  --prompt "local inpainting, preserve the original image structure, natural blending" `
  --steps $Steps `
  --init-img "D:\path\target.png" `
  --mask "D:\path\mask.png"
```

Decode:

```powershell
& $Cli --stage vae_decode --backend "vae=Vulkan1" `
  --diffusion-model $Diffusion --vae $VAE `
  -W $W -H $H --seed $Seed `
  --diffuse-out "$Work\diffuse" `
  -o $Out
```

Clean temporary stage caches after success:

```powershell
Remove-Item -LiteralPath $Work -Recurse -Force
```

## Manual Mask Utility

The only retained Python tool is:

```powershell
python .\project\manual_mask_draw.py `
  --image "D:\path\target.png" `
  --mask-out "D:\path\mask.png" `
  --image-out "D:\path\target_copy.png"
```

Rules:

- The mask must be drawn against the exact target image.
- The mask and target must have the same dimensions.
- No crop workflow.
- No automatic mask resize.
- No automatic mask alignment.

## Repository Hygiene

This repository intentionally excludes:

- all image files
- generated outputs
- local inputs
- run directories
- model weights
- local LoRA files
- build products

Use `git status --short` before publishing and confirm no image files are staged.

## License

This fork keeps the original `stable-diffusion.cpp` license and attribution. See `LICENSE`.
