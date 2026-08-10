# audiomax aligner sidecar — CPU-only ASR + forced alignment.
#
# Targets, and why there is more than one:
#   runtime        the shipping image. Lean stack, NO model weights.
#   baked          runtime + the en/es/fr weights as an image layer.
#   whisperx       the NAMED tool, for cost comparison only. Heavier; see below.
#
#   docker build --target runtime  -t audiomax-aligner:runtime  aligner/
#   docker build --target baked    -t audiomax-aligner:baked    aligner/
#   docker build --target whisperx -t audiomax-aligner:whisperx aligner/
#
# BAKED vs NOT, stated so a future reader does not re-derive it:
#   not baked → smaller image and faster pulls, but the first request per
#     language fetches ~360 MiB of alignment weights from download.pytorch.org.
#     That is not a cold start, it is a network fetch, and it lands on a user's
#     first render. Sound ONLY with a persistent cache volume, so it is paid once
#     per volume instead of once per container.
#   baked → every container starts equal and no render depends on a third-party
#     CDN being reachable. `CLAUDE.md` constraint 2 (no fallback launch) points
#     here: a primary path that needs a CDN at render time has a fallback in it.
#
# ── Base ─────────────────────────────────────────────────────────────────────
# python:3.12-slim (Debian) rather than alpine: ctranslate2, torch and av publish
# manylinux wheels only. On alpine's musl, pip finds no wheel and builds from
# source, which needs a full toolchain and yields a LARGER image than the one
# alpine was chosen to shrink.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # One cache root, so ONE volume mount covers every model. torch-hub and
    # huggingface default to different directories, and for en/es/fr the
    # alignment models are torch-hub downloads — a HF-only mount would cache
    # nothing that matters.
    XDG_CACHE_HOME=/models \
    HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    # OMP/MKL otherwise start one thread per HOST core, which inside a
    # cpu-limited container means dozens of threads fighting over a fraction of
    # a core. The worker overrides this per deployment; this is a safe floor.
    OMP_NUM_THREADS=4
#
# PYTHONDONTWRITEBYTECODE is deliberately NOT set. Cold start is a per-container
# cost and imports dominate it, so the image keeps the .pyc files pip writes at
# build time. Suppressing them trades a permanent startup tax for a few MiB.

# NOTE: no ffmpeg package here, and that is a measured decision rather than an
# oversight. faster-whisper 1.2.1 decodes through PyAV (`av`), whose wheels bundle
# their own ffmpeg shared libraries — 25 of them, verified in the installed
# package. `apt-get install ffmpeg` would add roughly 300 MiB of codec tree that
# nothing in the lean stack calls. The `whisperx` target below DOES install it,
# because whisperx.load_audio shells out to the ffmpeg BINARY.

# ── Lean dependencies ────────────────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt /tmp/requirements.txt

# The CPU wheel index is not optional. Without it `torch` on linux/amd64 resolves
# to the CUDA build and drags in ~2.5 GB of nvidia-* runtime wheels that never
# execute here. --extra-index-url (not --index-url) so everything else still
# resolves from PyPI.
RUN pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements.txt \
    # Assert the CPU pin took. A CUDA torch that installs "successfully" is a
    # multi-GB image nobody notices until the registry bill arrives.
    && python -c "import torch,sys; print('torch',torch.__version__); sys.exit(0 if '+cpu' in torch.__version__ else 1)" \
    # Assert the alignment bundles this product needs are reachable in the
    # installed torchaudio, by NAME. A rename upstream would otherwise surface as
    # a runtime failure on a user's first render in that language.
    && python -c "import torchaudio.pipelines as p; [getattr(p,n) for n in ('WAV2VEC2_ASR_BASE_960H','VOXPOPULI_ASR_BASE_10K_ES','VOXPOPULI_ASR_BASE_10K_FR')]; print('align bundles OK')"

# ── Runtime: no weights ──────────────────────────────────────────────────────
FROM deps AS runtime

WORKDIR /app
COPY service.py /app/service.py
COPY spike-e/measure.py /app/spike-e/measure.py

# Not root. The sidecar reads audio and writes timings; it needs no more.
RUN useradd --create-home --uid 10001 aligner \
    && mkdir -p /models \
    && chown -R aligner:aligner /models /app
USER aligner

ENV PORT=8081 HOST=0.0.0.0
EXPOSE 8081
# Healthcheck uses the stdlib: adding curl to observe a service is adding a
# package to observe a package.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/health',timeout=4).status==200 else 1)"
CMD ["python", "/app/service.py"]

# ── Baked: weights in the image ──────────────────────────────────────────────
FROM runtime AS baked
# `base` is the faster-whisper size SPIKE A's accuracy figures were produced on.
# Changing it changes the numbers that spike quotes, so it is a build arg with
# the spike's value as the default rather than a silent edit.
ARG ASR_MODEL=base
ARG ALIGN_LANGS="en es fr"
# ARG is build-time only and is NOT visible to a process unless promoted. Without
# these two lines the script below would silently bake the defaults and ignore
# --build-arg.
ENV ASR_MODEL=${ASR_MODEL} \
    ALIGN_LANGS=${ALIGN_LANGS}

RUN python - <<'PY'
import os
from faster_whisper import WhisperModel
import torchaudio.pipelines as pipelines

BUNDLES = {
    "en": "WAV2VEC2_ASR_BASE_960H",
    "es": "VOXPOPULI_ASR_BASE_10K_ES",
    "fr": "VOXPOPULI_ASR_BASE_10K_FR",
}

model = os.environ.get("ASR_MODEL", "base")
print(f"baking faster-whisper:{model}", flush=True)
WhisperModel(model, device="cpu", compute_type="int8")

for lang in os.environ.get("ALIGN_LANGS", "en es fr").split():
    name = BUNDLES.get(lang)
    if name is None:
        # Refuse rather than skip. A silently unbaked language is a container
        # that looks ready and fetches 360 MiB on a user's first render.
        raise SystemExit(f"no alignment bundle mapped for language {lang!r}")
    print(f"baking align bundle {lang} -> {name}", flush=True)
    getattr(pipelines, name).get_model()
print("bake complete", flush=True)
PY

ENV AUDIOMAX_MODELS_BAKED=1

# ── whisperx: the named tool, for comparison ─────────────────────────────────
# Built from `base`, not from `deps`, so its dependency closure is resolved on
# its own terms and the size comparison is honest.
FROM base AS whisperx

# whisperx.load_audio shells out to the ffmpeg BINARY, so this target needs the
# package the lean image omits.
RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-whisperx.txt /tmp/requirements-whisperx.txt

# antlr4-python3-runtime 4.9.3 (reached via pyannote-audio -> hydra -> omegaconf,
# which pins ==4.9.*) publishes NO wheel — sdist only. So this install cannot use
# --only-binary=:all:. It is pure Python and needs no compiler, but a hardened
# build that forbids sdists will fail here, and that is a property of whisperx's
# dependency closure worth knowing before adopting it.
RUN pip install --no-cache-dir \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements-whisperx.txt \
    && python -c "import torch,sys; print('torch',torch.__version__); sys.exit(0 if '+cpu' in torch.__version__ else 1)" \
    # The import that has never succeeded on the workstation. transformers 5.x
    # removed the top-level Wav2Vec2ForCTC/Wav2Vec2Processor exports whisperx
    # imports at module scope; this line is what turns that from a silent
    # runtime failure into a failed build.
    && python -c "from whisperx.alignment import load_align_model; print('whisperx.alignment OK')"

WORKDIR /app
COPY service.py /app/service.py
COPY spike-e/measure.py /app/spike-e/measure.py
RUN useradd --create-home --uid 10001 aligner \
    && mkdir -p /models && chown -R aligner:aligner /models /app
USER aligner
ENV PORT=8081 HOST=0.0.0.0
EXPOSE 8081
CMD ["python", "/app/service.py"]
