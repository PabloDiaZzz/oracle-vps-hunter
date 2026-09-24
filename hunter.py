"""
Oracle Cloud Always Free Instance Hunter — GitHub Actions & Local Edition.
Continuously or periodically attempts to claim a compute instance in Madrid (eu-madrid-1).
"""

import os
import sys
import time
import datetime
from pathlib import Path
import requests
import oci

CONFIG_DIR = Path(os.path.expanduser("~/.oci"))
CONFIG_PATH = CONFIG_DIR / "config"
KEY_PATH = CONFIG_DIR / "oci_api_key.pem"
SSH_PUB_KEY_PATH = CONFIG_DIR / "oracle_instance_key.pub"

SUBNET_ID = "ocid1.subnet.oc1.eu-madrid-1.aaaaaaaafjk5uqafvmgjlzuilrl56d3gjylqrhq67sgf7r2dc3vyid6c7q2q"
AD = "zUXp:EU-MADRID-1-AD-1"
IMAGE_ARM = "ocid1.image.oc1.eu-madrid-1.aaaaaaaacbdtisnyjmnegacmtscuoyevmjeuucoguxwmhspzhljbx6kpzhja"
IMAGE_AMD = "ocid1.image.oc1.eu-madrid-1.aaaaaaaau2ofu7fml3oy72bnamsvdebrcoceqbpuedkc4lxp2zdragatutsa"

FAULT_DOMAINS = [None, "FAULT-DOMAIN-1", "FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]

def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def setup_environment_from_secrets():
    """Inicializa archivos de credenciales OCI desde variables de entorno si están presentes."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Config
    oci_config_env = os.environ.get("OCI_CONFIG")
    if oci_config_env:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(oci_config_env.strip() + "\n")
        log(f"✓ Configuración OCI generada desde secret.")

    # 2. Private Key PEM
    oci_key_env = os.environ.get("OCI_KEY_FILE")
    if oci_key_env:
        with open(KEY_PATH, "w", encoding="utf-8") as f:
            f.write(oci_key_env.strip() + "\n")
        if sys.platform != "win32":
            try:
                os.chmod(KEY_PATH, 0o600)
            except Exception:
                pass
        log(f"✓ Clave privada API OCI generada desde secret.")

    # 3. Instance SSH Public Key
    ssh_pub_env = os.environ.get("OCI_INSTANCE_PUB_KEY")
    if ssh_pub_env:
        with open(SSH_PUB_KEY_PATH, "w", encoding="utf-8") as f:
            f.write(ssh_pub_env.strip() + "\n")
        log(f"✓ Clave pública SSH de instancia generada desde secret.")

def notify_telegram(msg: str):
    """Envía alerta por Telegram si el token y chat ID están configurados."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    cid = os.environ.get("TELEGRAM_CHAT_ID")
    
    # Fallback local a settings.json si no vienen por env
    if not tok or not cid:
        try:
            import json
            cfg_path = Path(__file__).resolve().parent.parent / "scripts" / "torrent_cli" / "config" / "settings.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    s = json.load(f)
                tok = tok or s.get("telegram_bot_token")
                cid = cid or s.get("telegram_chat_id")
        except Exception:
            pass

    if tok and cid:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{tok}/sendMessage",
                json={"chat_id": cid, "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
            if resp.status_code == 200:
                log("✓ Alerta de Telegram enviada exitosamente.")
            else:
                log(f"Telegram API response: {resp.status_code} - {resp.text}")
        except Exception as e:
            log(f"Error enviando alerta Telegram: {e}")

def wait_for_running_and_get_ip(compute: oci.core.ComputeClient, network: oci.core.VirtualNetworkClient, instance_id: str, compartment_id: str):
    log(f"Esperando a que la instancia {instance_id} pase a RUNNING...")
    for _ in range(60):
        time.sleep(10)
        inst = compute.get_instance(instance_id).data
        log(f"Estado de la instancia: {inst.lifecycle_state}")
        if inst.lifecycle_state == oci.core.models.Instance.LIFECYCLE_STATE_RUNNING:
            vnics = compute.list_vnic_attachments(compartment_id, instance_id=instance_id).data
            for vnic_att in vnics:
                vnic = network.get_vnic(vnic_att.vnic_id).data
                if vnic.public_ip:
                    log("=====================================================")
                    log("🎉 INSTANCIA ACTIVA Y LISTA!")
                    log(f"IP PÚBLICA: {vnic.public_ip}")
                    log("SSH USER: ubuntu")
                    log("SSH KEY: ~/.oci/oracle_instance_key")
                    log(f"Comando: ssh -i ~/.oci/oracle_instance_key ubuntu@{vnic.public_ip}")
                    log("=====================================================")
                    alert_msg = (
                        "🎉 <b>¡ORACLE CLOUD VPS CAPTURADO!</b>\n\n"
                        f"🚀 <b>Instancia:</b> <code>{instance_id[:25]}...</code>\n"
                        f"🌐 <b>IP Pública:</b> <code>{vnic.public_ip}</code>\n"
                        "👤 <b>SSH User:</b> <code>ubuntu</code>\n"
                        "🔑 <b>SSH Key:</b> <code>~/.oci/oracle_instance_key</code>\n\n"
                        "💻 <b>Comando:</b>\n"
                        f"<code>ssh -i ~/.oci/oracle_instance_key ubuntu@{vnic.public_ip}</code>"
                    )
                    notify_telegram(alert_msg)
                    return vnic.public_ip
    return None

def main():
    log("Iniciando Oracle Cloud Always Free Hunter para Madrid (eu-madrid-1)...")
    setup_environment_from_secrets()

    if not CONFIG_PATH.exists():
        log(f"ERROR: Archivo de configuración {CONFIG_PATH} no encontrado.")
        sys.exit(1)
        
    if not SSH_PUB_KEY_PATH.exists():
        log(f"ERROR: Clave pública SSH {SSH_PUB_KEY_PATH} no encontrada.")
        sys.exit(1)

    with open(SSH_PUB_KEY_PATH, "r", encoding="utf-8") as f:
        ssh_public_key = f.read().strip()

    config = oci.config.from_file(str(CONFIG_PATH))
    # Asegurar ruta correcta a la clave PEM si se especificó ~
    if "key_file" in config:
        config["key_file"] = os.path.expanduser(config["key_file"])

    tenancy_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    network = oci.core.VirtualNetworkClient(config)

    # 1. Comprobar si ya existe alguna instancia activa
    try:
        existing = compute.list_instances(compartment_id=tenancy_id).data
        for inst in existing:
            if inst.lifecycle_state in ["PROVISIONING", "RUNNING"]:
                log(f"Ya existe una instancia activa: {inst.display_name} ({inst.id})")
                with open("instance_created.txt", "w", encoding="utf-8") as f:
                    f.write(inst.id)
                wait_for_running_and_get_ip(compute, network, inst.id, tenancy_id)
                return
    except Exception as e:
        log(f"Aviso al listar instancias existentes: {e}")

    max_cycles = int(os.environ.get("MAX_CYCLES", os.environ.get("INPUT_CYCLES", "2")))
    max_duration = int(os.environ.get("MAX_DURATION_SECONDS", "600"))
    start_time = time.time()
    current_cycle = 0

    log(f"Configuración de ejecución: máximo {max_cycles} ciclos o {max_duration} segundos.")

    while current_cycle < max_cycles:
        if (time.time() - start_time) >= max_duration:
            log("Límite de tiempo alcanzado para esta ejecución. Finalizando ronda.")
            break

        current_cycle += 1
        log(f"--- Iniciando Ciclo #{current_cycle} de {max_cycles} ---")

        # Probar formas en rotación (ARM primero, luego AMD)
        targets = [
            ("ARM", "VM.Standard.A1.Flex", IMAGE_ARM, 1, 6),
            ("AMD", "VM.Standard.E2.1.Micro", IMAGE_AMD, None, None),
        ]
        
        for arch, shape, image_id, ocpus, mem in targets:
            for fd in FAULT_DOMAINS:
                fd_label = fd if fd else "AUTO"
                vnic = oci.core.models.CreateVnicDetails(
                    subnet_id=SUBNET_ID,
                    assign_public_ip=True,
                    display_name="vnic-primary"
                )
                
                shape_cfg = None
                if ocpus and mem:
                    shape_cfg = oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpus, memory_in_gbs=mem)
                
                launch_details = oci.core.models.LaunchInstanceDetails(
                    compartment_id=tenancy_id,
                    availability_domain=AD,
                    fault_domain=fd,
                    shape=shape,
                    shape_config=shape_cfg,
                    display_name=f"qbit-proxy-{arch.lower()}",
                    image_id=image_id,
                    create_vnic_details=vnic,
                    metadata={"ssh_authorized_keys": ssh_public_key},
                    is_pv_encryption_in_transit_enabled=True
                )
                
                try:
                    log(f"Intento [{arch}] shape={shape} FD={fd_label}...")
                    resp = compute.launch_instance(launch_details)
                    log(f"🎉 ÉXITO TOTAL! Instancia reservada con ID: {resp.data.id}")
                    with open("instance_created.txt", "w", encoding="utf-8") as f:
                        f.write(resp.data.id)
                    notify_telegram(f"⚡ <b>¡Instancia reservada en Oracle Cloud ({arch})!</b>\nID: <code>{resp.data.id}</code>\nEsperando IP pública...")
                    wait_for_running_and_get_ip(compute, network, resp.data.id, tenancy_id)
                    return
                except oci.exceptions.ServiceError as e:
                    if e.status == 429 or "TooManyRequests" in str(e.code):
                        log("    [Rate Limit] Pausando 60s...")
                        time.sleep(60)
                        break
                    elif "Out of host capacity" in str(e.message) or "InternalError" in str(e.code):
                        pass
                    else:
                        log(f"    [{e.code}] {e.message.strip()}")
                except Exception as ex:
                    log(f"    [Excepción] {ex}")
                
                time.sleep(2)

        if current_cycle < max_cycles:
            log("Pausando 45s antes del siguiente ciclo...")
            time.sleep(45)

    log("Ronda de comprobación completada sin hueco libre.")

if __name__ == "__main__":
    main()
