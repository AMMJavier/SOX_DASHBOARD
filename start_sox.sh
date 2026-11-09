#!/bin/bash

echo "=================================="
echo " INICIO SISTEMA SOX "
echo "=================================="


BACKEND="/data/sisauto/Proyecto_Sox/sox-dashboard/backend"
FRONTEND="/data/sisauto/Proyecto_Sox/sox-dashboard/frontend"


# =========================
# BACKEND
# =========================

cd $BACKEND || exit 1

echo "Activando entorno virtual..."

source .venv/bin/activate


echo "Ejecutando extractor Check Point..."

python -m checkpoint.sync_service


if [ $? -ne 0 ]; then
    echo "ERROR en extractor"
    exit 1
fi


echo "Levantando API SOX..."

uvicorn main:app \
--host 0.0.0.0 \
--port 8000 &


BACKEND_PID=$!


# =========================
# FRONTEND
# =========================

echo "Levantando Frontend..."

cd $FRONTEND || exit 1

npm run dev -- --host 0.0.0.0 &


FRONTEND_PID=$!


echo "=================================="
echo " SISTEMA SOX INICIADO "
echo " Backend PID: $BACKEND_PID "
echo " Frontend PID: $FRONTEND_PID "
echo "=================================="


wait