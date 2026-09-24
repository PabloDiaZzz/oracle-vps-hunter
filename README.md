# Oracle Cloud Always Free Hunter — GitHub Actions

Automatización periódica para reclamar una instancia *Always Free* (ARM A1.Flex o AMD Micro) en la región de Madrid (`eu-madrid-1`) en Oracle Cloud Infrastructure (OCI).

## Funcionamiento
1. **GitHub Actions**:
   - Corre automáticamente cada 30 minutos mediante `cron`.
   - Soporta ejecución manual en cualquier momento desde la pestaña **Actions** (`workflow_dispatch`).
2. **Secrets seguros**:
   - `OCI_CONFIG`: Contenido del archivo de configuración OCI.
   - `OCI_KEY_FILE`: Clave privada PEM de la API OCI.
   - `OCI_INSTANCE_PUB_KEY`: Clave pública SSH que se inyecta en la máquina al crearla.
   - `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`: Notificación instantánea al cazar la máquina con IP y comando SSH.
3. **Notificación**:
   - Al encontrar hueco y pasar a `RUNNING`, el script envía una alerta por Telegram con la IP pública asignada y el comando exacto para conectar por SSH.
