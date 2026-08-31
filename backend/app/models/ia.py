from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class InteraccionIA(Base):
    __tablename__ = "interaccion_ia"
    __table_args__ = (Index("idx_interaccion_ia_usuario", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    tipo_consulta: Mapped[str | None] = mapped_column(String(30))
    prompt_consulta: Mapped[str | None] = mapped_column(Text)
    prendas_sugeridas_ids: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
