import os
import subprocess
import shutil

main_dir= ""

def run(cmd, check=True):
    return subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)



def config_samba():
    print("=== Automatic SAMBA configuration ===")


    # Instalación de paquetes
    res = input("Is Samba installed? (y/n) [n]: ").strip().lower() or "n"
    if res == "n":
        print("[INFO] Installing Samba packages...")
        run("apt update -y", check=False)
        run("apt install -y samba samba-common-bin", check=False)

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
    run(f"id -u {user} >/dev/null 2>&1 || useradd -m {user}", check=False)
    print(f"[INFO] Setting Samba password for user '{user}'")
    os.system(f"smbpasswd -a {user}")

    # Crear grupo si no existe
    run("getent group sambashare || groupadd sambashare", check=False)
    run(f"usermod -aG sambashare {user}", check=False)

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
    run("testparm -s", check=False)

    # Reiniciar servicio
    print("[INFO] Restarting Samba service...")
    run("systemctl enable smbd nmbd", check=False)
    run("systemctl restart smbd nmbd", check=False)

    status = run("systemctl is-active smbd", check=False)
    if "active" in status.stdout:
        ip = run("hostname -I | awk '{print $1}'", check=False).stdout.strip()
        print(f"[OK] Samba active. Shared folder: {shared_dir}")
        print(f"[INFO] Access from Windows via: \\\\{ip}\\shared")
    else:
        print("[ERROR] Samba service could not start. Check logs with: journalctl -u smbd")

def check_integrity():
    awnser = input("Do you want to install md5deep for file integrity checking? (y/n) [n]: ").strip().lower() or "n"
    if awnser == "y":
        print("[INFO] Installing md5deep...") # * no encuentro la forma de verificar si ya está instalado esto es mucho mas sencillo
        run("apt install md5deep -y", check=False)
        target_dir = main_dir
        print(f"[STEP] Generating MD5 checksums for files in {target_dir} ...")
        checksum_file = os.path.join(target_dir, "checksums.md5")
        run(f"md5deep -r '{target_dir}' > '{checksum_file}'", check=False)
        print(f"[OK] Checksums saved to {checksum_file}")


def main():
    print("=== System Configuration Script ===")
    print("1. Configure Samba.\n2. Check File Integrity.\n3. Exit.")
    choice = input("Select an option [1-3]: ").strip()
    match choice:
        case "1":
            config_samba()
        case "2":
            check_integrity()
        case "3":
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