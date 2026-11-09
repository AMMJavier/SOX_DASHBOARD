from fastapi import APIRouter, HTTPException


router = APIRouter()


@router.post("/login")
def login():

    return {
        "mensaje": "Ruta login SOX funcionando"
    }