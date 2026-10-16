"""Límite de intentos fallidos (por ejemplo, de inicio de sesión) para frenar a quien prueba
contraseñas una tras otra. Vive en la memoria de cada proceso: con varios workers el límite
efectivo se multiplica, suficiente para este tamaño; a escala de SaaS conviene llevarlo a Redis."""
import math
import time
from collections import defaultdict, deque
from threading import Lock


class LimiteIntentos:
    def __init__(self, maximo: int, ventana_segundos: int):
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._fallos: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()  # los endpoints síncronos corren en varios hilos

    def _descartar_viejos(self, clave: str, ahora: float) -> deque[float]:
        fallos = self._fallos[clave]
        while fallos and ahora - fallos[0] >= self.ventana:
            fallos.popleft()
        return fallos

    def segundos_bloqueado(self, clave: str) -> int:
        """0 si puede intentar; si no, cuántos segundos faltan para el próximo intento."""
        with self._lock:
            ahora = time.monotonic()
            fallos = self._descartar_viejos(clave, ahora)
            if len(fallos) < self.maximo:
                return 0
            return max(1, math.ceil(self.ventana - (ahora - fallos[0])))

    def registrar_fallo(self, clave: str) -> None:
        with self._lock:
            ahora = time.monotonic()
            self._descartar_viejos(clave, ahora).append(ahora)

    def limpiar(self, clave: str) -> None:
        with self._lock:
            self._fallos.pop(clave, None)

    def reiniciar(self) -> None:
        with self._lock:
            self._fallos.clear()
