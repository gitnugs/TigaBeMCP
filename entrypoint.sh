#!/bin/sh
set -eu

# Pastikan model E5 tersedia di /models (named volume tigabe-models).
# Volume mungkin berisi sisa kosong (mis. .agent_harnesses.json, xet) dari
# download HF sebelumnya — jadi JANGAN cek "folder kosong"; cek eksistensi
# folder cache model yang sebenarnya.
MODEL_CACHE="models--intfloat--multilingual-e5-small"

if [ -d /models_baked ] && [ ! -d "/models/$MODEL_CACHE" ]; then
    echo "[entrypoint] seeding /models dari /models_baked (model $MODEL_CACHE belum ada)"
    mkdir -p /models
    cp -a /models_baked/. /models/
    echo "[entrypoint] seed selesai: $(find /models -name model.safetensors | head -1)"
fi

exec "$@"