from dis import disco
import os
import subprocess
import shutil
from rich.console import Console
from rich.text import Text




main_dir= ""

def run(cmd):
    try:
        print(f"[EXEC] {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed: {e}")
        return False


def config_samba():#TODO: añadir la opcion de autoconfig si ya hicieron un raid antes
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
    shared_dir = input(f"Enter shared directory [{default_share}]: ").strip() or default_share
    main_dir=os.path.dirname(shared_dir)
    os.makedirs(shared_dir, exist_ok=True)

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
    if "active" in status.stdout:
        ip = run("hostname -I | awk '{print $1}'").stdout.strip()
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
    
    def format_disk():
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

        for disco in discos:
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

    format_disk()












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


    #TODO: necesario assignar la creaciion automatica de un LV y un VG


















def main():
    print("=== System Configuration Script ===")
    print("1. Configure Samba.\n2. Check File Integrity.\n3. Make full NAS \n4 make full backup \nX. Exit.")
    choice = input("Select an option [1-3]: ").strip()
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
        case "X" | "x":
            print("Exiting...")
        case _:
            print("Invalid option. Exiting...")# TODO: necesario añadir raid y interfaz de web

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
