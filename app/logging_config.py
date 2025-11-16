
import logging

# Configuración básica de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("pokedex_api.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# Logger principal de la API
logger = logging.getLogger("pokedex_api")
