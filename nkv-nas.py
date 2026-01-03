from dis import disco
import os
import subprocess
import shutil
import json
from rich.console import Console
from rich.text import Text
from flask import Flask, render_template_string, send_from_directory, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)
CONFIG_FILE = "/home/nkv/Desktop/nkv-nas/config.json"

def load_config():
    """Carga la configuración desde JSON"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"main_dir": "none"}
    return {"main_dir": "none"}

def save_config(config):
    """Guarda la configuración en JSON"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"[OK] Configuración guardada en {CONFIG_FILE}")

config = load_config()
main_dir = config.get("main_dir", "none")




def run(cmd):
    try:
        print(f"[EXEC] {cmd}")
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e}")
        return None


def config_samba():
    global main_dir, config
    print("=== Automatic SAMBA configuration ===")


    # Instalación de paquetes
    res = input("Is Samba installed? (y/n) [n]: ").strip().lower() or "n"
    if res == "n":
        print("[INFO] Installing Samba packages...")
        run("apt update -y")
        run("apt install -y samba samba-common-bin")

    smb_conf = "/etc/samba/smb.conf"

    # Directorio compartido
    default_share = "/srv/samba/shared"
    match main_dir:
        case "none":
            main_dir = input(f"Enter main directory for Samba share [{default_share}]: ").strip() or default_share
            config["main_dir"] = main_dir
            save_config(config)
            shared_dir = main_dir
        case _:
            print(f"[INFO] Using existing main directory for Samba share: {main_dir}")
            shared_dir = main_dir

    
        

    # Permisos
    os.system(f"chmod 2770 '{shared_dir}'")
    os.system(f"chown root:sambashare '{shared_dir}' 2>/dev/null || chown root:root '{shared_dir}'")

    # Usuario Samba
    print("\n[STEP] Samba user configuration:")
    user = input("Enter user to grant Samba access [default current user]: ").strip() or os.getenv("SUDO_USER") or os.getenv("USER")
    run(f"id -u {user} >/dev/null 2>&1 || useradd -m {user}")
    print(f"[INFO] Setting Samba password for user '{user}'")
    os.system(f"smbpasswd -a {user}")

    # Crear grupo si no existe
    run("getent group sambashare || groupadd sambashare")
    run(f"usermod -aG sambashare {user}")

    # Modificar configuración smb.conf
    print("[INFO] Updating smb.conf ...")
    with open(smb_conf, "r") as f:
        data = f.read()

    readonly = input("Read only? (yes/no) [no]: ").strip().lower() or "no"
    guest = input("Allow guests? (yes/no) [no]: ").strip().lower() or "no"
    browseable = input("Browseable? (yes/no) [no]: ").strip().lower() or "no"

    if "[shared]" not in data:
        data += f"""
    [shared]
    path = {shared_dir}
    browseable = {browseable}
    read only = {readonly}
    guest ok = {guest}
    valid users = {user}
    force user = {user}
    create mask = 0660
    directory mask = 2770
    """
    with open(smb_conf, "w") as f:
        f.write(data)

    # Validar configuración
    print("[INFO] Validating Samba configuration...")
    run("testparm -s")

    # Reiniciar servicio
    print("[INFO] Restarting Samba service...")
    run("systemctl enable smbd nmbd")
    run("systemctl restart smbd nmbd")

    status = run("systemctl is-active smbd")
    if status and "active" in status.stdout:
        ip_result = run("hostname -I | awk '{print $1}'")
        if ip_result:
            ip = ip_result.stdout.strip()
            print(f"[OK] Samba active. Shared folder: {shared_dir}")
            print(f"[INFO] Access from Windows via: \\\\{ip}\\shared")
    else:
        print("[ERROR] Samba service could not start. Check logs with: journalctl -u smbd")

def check_integrity():
    awnser = input("Do you want to install md5deep for file integrity checking? (y/n) [n]: ").strip().lower() or "n"
    if awnser == "y":
        print("[INFO] Installing md5deep...") # * no encuentro la forma de verificar si ya está instalado esto es mucho mas sencillo
        run("apt install md5deep -y")
    
    target_dir = main_dir
    print(f"[STEP] Generating MD5 checksums for files in {target_dir} ...")
    checksum_file = os.path.join(target_dir, "checksums.md5")
    run(f"md5deep -r '{target_dir}' > '{checksum_file}'")
    print(f"[OK] Checksums saved to {checksum_file}")





def make_full_nas():
    global main_dir, config
    console = Console()
    console.print(Text("ARE YOU SURE THIS YOU WANT THIS THIS WILL WIPE ALL DATA FROM THE EXTRA DISKS AND MAKE A FULL RAID SETUP", style="bold magenta", justify="center"), justify="center")
    confirmation = input("Type 'YES' to confirm: ").strip()
    if confirmation != "YES":
        print("[INFO] Operation cancelled by user.")
        return
    run("lsblk")
    selled_disks = input("Enter the disks to use for NAS (e.g., /dev/sdb /dev/sdc): ").strip().split()
    if not selled_disks:
        print("[ERROR] No disks selected. Exiting...")
        return
    
    
    tamanos = {}
    for disk in selled_disks:
        try:
            cmd = f"lsblk -b -dn -o SIZE {disk}"
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                tamanos[disk] = int(res.stdout.strip())
            else:
                print(f"[ERROR] Could not read size of {disk}")
        except Exception as e:
            print(f"[ERROR] {disk}: {e}")
            return
        
    if not tamanos:
        print("[ERROR] Could not determine any disk size.")
        return

    print("\nDetected disk sizes:")
    for d, sz in tamanos.items():
        print(f"  {d}: {sz / (1024**3):.2f} GB")

    disco_min = min(tamanos, key=tamanos.get)
    min_gb = tamanos[disco_min] / (1024**3)
    print(f"\n[INFO] Smallest disk: {disco_min} ({min_gb:.2f} GB)")

    tamaño_input = input(f"Enter partition size (<= {min_gb:.2f}GB, e.g., 25GB or 500MB): ").upper().strip()

    if tamaño_input.endswith("GB"):
        tamaño_bytes = float(tamaño_input[:-2]) * (1024**3)
    elif tamaño_input.endswith("MB"):
        tamaño_bytes = float(tamaño_input[:-2]) * (1024**2)
    else:
        print("[ERROR] Invalid size format. Use GB or MB suffix.")
        return

    if tamaño_bytes > tamanos[disco_min]:
        print("[ERROR] Size exceeds smallest disk capacity.")
        return

    tipo_fs = input("Enter filesystem type (e.g., ext4, xfs, btrfs): ").strip()

    print("\n[INFO] Starting complete wipe and partitioning...\n")

    for disco in selled_disks:
        print(f"[TASK] Processing {disco}...")

        # Unmount all filesystems
        print("[STEP] Unmounting all filesystems on this disk...")
        run(f"lsblk -ln -o MOUNTPOINT {disco} | grep -v '^$' | xargs -r -n1 umount -f || true")

        # Remove active device mapper entries
        print("[STEP] Removing any device mapper entries...")
        run(f"dmsetup remove -f {disco}* || true")

        # Remove Logical Volumes
        print("[STEP] Removing all Logical Volumes on this disk...")
        run("lvdisplay --colon 2>/dev/null | cut -d: -f1 | xargs -r -n1 lvremove -ff -y || true")

        # Remove Volume Groups
        print("[STEP] Removing all Volume Groups on this disk...")
        run("vgdisplay --colon 2>/dev/null | cut -d: -f1 | xargs -r -n1 vgremove -ff -y || true")

        # Remove Physical Volumes
        print("[STEP] Removing all Physical Volumes on this disk...")
        run("pvdisplay --colon 2>/dev/null | cut -d: -f1 | xargs -r -n1 pvremove -ff -y || true")

        # Stop and clean any RAID arrays
        print("[STEP] Stopping any RAID arrays containing this disk...")
        run("mdadm --detail --scan | awk '{print $2}' | xargs -r -n1 mdadm --stop || true")
        run(f"mdadm --zero-superblock {disco} || true")

        # Wipe all signatures and partition table
        print("[STEP] Wiping all signatures and partition table...")
        run(f"wipefs -a {disco} || true")
        run(f"sgdisk --zap-all {disco} || true")

        # Fast zero for header
        print("[STEP] Zeroing first 10MB for clean slate...")
        run(f"dd if=/dev/zero of={disco} bs=1M count=10 conv=fdatasync status=none || true")
        run(f"blkdiscard {disco} || true")
        run(f'sudo sgdisk --zap-all {disco}')

        print(f"[OK] Disk {disco} fully cleaned and ready for reuse.\n")

        # Create new GPT structure and partition
        if not run(f"parted -s {disco} mklabel gpt"):
            print(f"[ERROR] Failed to create GPT on {disco}")
            continue

        run(f"parted -s {disco} mkpart primary 1MiB {tamaño_input}")

        # Get new partition name
        part = disco + "1" if "nvme" not in disco else disco + "p1"
        print(f"[INFO] Formatting {part} as {tipo_fs}...")
        run(f"mkfs.{tipo_fs} -F {part}")

        print(f"[OK] {disco} fully wiped and formatted ({tipo_fs}, {tamaño_input}).\n")

        print("[INFO] All selected disks cleaned and formatted uniformly.")

    nombre_raid = input("Enter RAID name (e.g., md0): ")

    def crear_raid(tipo, discos, nombre_raid):
        nivel = str(tipo)
        discos_str = " ".join(discos)
        cmd = f"mdadm --create /dev/{nombre_raid} --level={nivel} --raid-devices={len(discos)} {discos_str}"
        return run(cmd)

    num_disks = len(selled_disks.split())
    num_disks = int(num_disks)
    match num_disks:
        case 1:
            print("[INFO] Single disk selected, no RAID will be created.")  
        case 2:
            nivel_raid = 1
        case 3 | 4:
            nivel_raid = 5
        case _ if num_disks >= 5:
            nivel_raid = 6
        case _:
            nivel_raid = None
    if num_disks is None:
        print("[ERROR] Invalid RAID selection")
        return

    if not crear_raid(nivel_raid, selled_disks, nombre_raid):
        print("[ERROR] RAID creation failed.")
        return

    run("mkdir -p /etc/mdadm")
    run(f"mdadm --detail --scan >> /etc/mdadm/mdadm.conf")

    # Crear Volume Group y Logical Volume
    print("[INFO] Creating Volume Group and Logical Volume...")
    
    raid_device = f"/dev/{nombre_raid}"
    vg_name = input("Enter Volume Group name [vg_nas]: ").strip() or "vg_nas"
    lv_name = input("Enter Logical Volume name [lv_storage]: ").strip() or "lv_storage"
    lv_size = input("Enter Logical Volume size (e.g., 100GB, 500GB): ").strip()
    
    # Crear Physical Volume
    print(f"[STEP] Creating Physical Volume on {raid_device}...")
    run(f"pvcreate -f {raid_device}")
    
    # Crear Volume Group
    print(f"[STEP] Creating Volume Group '{vg_name}'...")
    run(f"vgcreate {vg_name} {raid_device}")
    
    # Crear Logical Volume
    print(f"[STEP] Creating Logical Volume '{lv_name}' with size {lv_size}...")
    run(f"lvcreate -L {lv_size} -n {lv_name} {vg_name}")
    
    # Formatear Logical Volume
    lv_path = f"/dev/{vg_name}/{lv_name}"
    print(f"[STEP] Formatting {lv_path} as {tipo_fs}...")
    run(f"mkfs.{tipo_fs} -F {lv_path}")
    
    # Montar Logical Volume
    mount_point = input("Enter mount point [/mnt/nas]: ").strip() or "/mnt/nas"
    os.makedirs(mount_point, exist_ok=True)
    print(f"[STEP] Mounting {lv_path} to {mount_point}...")
    run(f"mount {lv_path} {mount_point}")
    
    print(f"[OK] Logical Volume mounted at {mount_point}")
    main_dir = mount_point
    config["main_dir"] = mount_point
    save_config(config)

def web_interface():
    global main_dir
    
    HTML_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Explorador RAID</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            a { text-decoration: none; color: blue; }
            a:hover { text-decoration: underline; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        </style>
    </head>
    <body>
        <h1>Explorador del RAID</h1>
        <p>Ruta actual: {{ current_path }}</p>
        <table>
            <tr><th>Nombre</th><th>Tamaño</th><th>Última modificación</th></tr>
            {% for item in items %}
                <tr>
                    <td><a href="{{ item.url }}">{{ item.name }}</a></td>
                    <td>{{ item.size }}</td>
                    <td>{{ item.mtime }}</td>
                </tr>
            {% endfor %}
        </table>
        <hr>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file" multiple>
            <input type="submit" value="Subir archivo(s)">
        </form>
    </body>
    </html>
    '''

    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
    @app.route('/<path:path>', methods=['GET', 'POST'])
    def browse(path):
        full_path = os.path.join(main_dir, path)
        
        if not os.path.realpath(full_path).startswith(os.path.realpath(main_dir)):
            return "Acceso denegado", 403
        
        if not os.path.exists(full_path):
            return "Ruta no encontrada", 404
        
        if request.method == 'POST':
            for file in request.files.getlist('file'):
                if file.filename and os.path.isdir(full_path):
                    file.save(os.path.join(full_path, file.filename))
            return redirect(request.url)
        
        if os.path.isfile(full_path):
            return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path))
        
        items = []
        if path:
            items.append({'name': '.. (padre)', 'url': url_for('browse', path=os.path.dirname(path.rstrip('/'))), 'size': '-', 'mtime': '-'})
        
        try:
            for entry in sorted(os.listdir(full_path), key=lambda x: (not os.path.isdir(os.path.join(full_path, x)), x.lower())):
                entry_path = os.path.join(full_path, entry)
                rel_path = os.path.join(path, entry).replace('\\', '/')
                stat = os.stat(entry_path)
                size = stat.st_size if os.path.isfile(entry_path) else '-'
                mtime_str = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                url = url_for('browse', path=rel_path)
                if os.path.isdir(entry_path):
                    entry += '/'
                    url += '/'
                items.append({'name': entry, 'url': url, 'size': f'{size:,} bytes' if size != '-' else '-', 'mtime': mtime_str})
        except PermissionError:
            return "Permiso denegado", 403
        
        return render_template_string(HTML_TEMPLATE, current_path='/' + path, items=items)

    print(f"[INFO] Starting web interface on http://0.0.0.0:5000")
    print(f"[INFO] Serving files from: {main_dir}")
    app.run(host='0.0.0.0', port=5000, debug=False)

def main():
    global config, main_dir
    config = load_config()
    main_dir = config.get("main_dir", "none")
    
    print("=== System Configuration Script ===")
    print(f"[INFO] Directorio actual: {main_dir}")
    print("1. Configure Samba.\n2. Check File Integrity.\n3. Make full NAS \n4 make full backup \n5. Start Web Interface\nX. Exit.")
    choice = input("Select an option [1-5]: ").strip()
    match choice:
        case "1":
            config_samba()
        case "2":
            check_integrity()
        case "3":
            run("clear")
            make_full_nas()
        case "4":
            shutil.copytree(main_dir, f"{main_dir}_backup", dirs_exist_ok=True)
            print(f"[OK] Full backup created at {main_dir}_backup")
        case "5":
            web_interface()
        case "X" | "x":
            print("Exiting...")
        case _:
            print("Invalid option. Exiting...")







if __name__ == "__main__":
    main()





'''
program writed by nkv also know as nkv-alex

 ^   ^
( o.o ) 
 > ^ <
 >cat<
'''
# copiable comments for program
# [INFO]
# [WARN]
# [ERROR]
# [STEP]
# [OK]

# ! Esto es un comentario importante (rojo)
# ? Esto es una pregunta o duda (azul)
# TODO: Esto es una tarea pendiente (naranja)
# * Esto es información clave (verde)
# // Comentario tachado (gris)
# NOTE: nota
