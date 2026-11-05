#!/bin/sh
set -eu

# Pastikan model E5 tersedia di /models (named volume tigabe-models).
#
# Volume bisa berisi sisa/state tak lengkap (mis. hasil download yang putus,
# .agent_harnesses.json, xet). JANGAN hanya cek "folder kosong" atau
# "folder ada" — verifikasi berkas model (model.safetensors) benar-benar ada.
# Bila tidak ada, salin ulang dari bake image (/models_baked).
MODEL_CACHE="models--intfloat--multilingual-e5-small"
MODEL_DIR="/models/$MODEL_CACHE"

perlu_seed=1
if [ -d "$MODEL_DIR" ] && find "$MODEL_DIR" -name 'model.safetensors' -print -quit 2>/dev/null | grep -q .; then
    perlu_seed=0
fi

if [ -d /models_baked ] && [ "$perlu_seed" = "1" ]; then
    echo "[entrypoint] seeding /models dari /models_baked (model belum lengkap)"
    mkdir -p /models
    cp -a /models_baked/. /models/
    echo "[entrypoint] seed selesai: $(find "$MODEL_DIR" -name model.safetensors -print -quit 2>/dev/null)"
fi

exec "$@"
