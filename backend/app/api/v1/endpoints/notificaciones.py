from fastapi import APIRouter, Depends, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.seguridad import PushToken, Usuario
from app.schemas.notificacion import PushTokenCreate
from app.services.push_service import registrar_o_actualizar_token

router = APIRouter()


@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
def registrar_push_token(
    datos: PushTokenCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Registra (o reasigna a este usuario) el token de FCM del dispositivo actual."""
    registrar_o_actualizar_token(db, current_user.id, datos.token, datos.plataforma)


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_push_token(
    datos: PushTokenCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_active_user),
):
    """Deja de enviar push a este dispositivo (ej. al cerrar sesión)."""
    db.execute(
        delete(PushToken).where(PushToken.token == datos.token, PushToken.usuario_id == current_user.id)
    )
    db.commit()
