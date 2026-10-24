from dotenv import find_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    jwt_secret_key: str = ""
    environment: str = "development"
    payment_gateway_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Libélula (pasarela boliviana, pago con QR Simple). Sin appkey funciona en modo de prueba.
    libelula_appkey: str = ""
    libelula_api_url: str = "https://api.libelula.bo"
    # URLs públicas: donde Libélula avisa el pago (backend) y adonde devuelve al cliente (frontend)
    backend_public_url: str = "https://fashionstore-backend-production-4c32.up.railway.app"
    frontend_public_url: str = "https://fashionstore-uagrm.up.railway.app"
    # Sitios web que pueden llamar a la API desde el navegador, separados por coma (localhost en
    # cualquier puerto siempre se permite para desarrollo). La app móvil no pasa por CORS.
    cors_origins: str = "https://fashionstore-uagrm.up.railway.app"
    # SaaS: tienda que se usa cuando el pedido no dice de cuál es (la web y la app actuales)
    tienda_por_defecto: str = "fashionstore"
    # Con dominio propio (ej. "fashionstore.app"), mi-tienda.fashionstore.app identifica a la tienda
    dominio_base: str = ""
    # Row Level Security en Postgres (requiere la migración que crea el rol fashionstore_app)
    rls_habilitado: bool = True
    # Cobro de las suscripciones de las tiendas: "simulado" (el cambio de plan y la renovación se
    # aplican en el acto y quedan registrados como pago simulado) o "stripe" (Stripe Billing)
    cobro_suscripciones: str = "simulado"
    # Mientras se paga con tarjeta o QR, las prendas quedan apartadas este tiempo
    minutos_apartado_pago: int = 15
    # Cada cuánto se devuelven al stock los apartados de pagos que no se completaron (0: nunca)
    segundos_entre_liberaciones: int = 60
    ai_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"
    replicate_api_token: str = ""
    tryon_replicate_model: str = "prunaai/p-image-try-on"
    firebase_credentials_json: str = ""
    # Alternativa en Base64 al JSON crudo de arriba: pegar un JSON largo con
    # comillas y \n escapados a mano en el editor de variables de Railway es
    # fragil (se corta o se corrompe con facilidad); Base64 es una sola cadena
    # alfanumerica sin caracteres problematicos. Si esta presente, tiene prioridad.
    firebase_credentials_json_b64: str = ""

    model_config = SettingsConfigDict(
        env_file=find_dotenv(usecwd=True),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def origenes_cors(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
