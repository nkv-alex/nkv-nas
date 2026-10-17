# NKV-NAS

Herramienta en Python para configurar y administrar un **NAS en Linux**, automatizando tareas de almacenamiento, redundancia de discos y compartición de archivos en red.

## Características

- **Configuración de RAID:** preparación de discos y creación de conjuntos RAID.
- **LVM:** creación de volúmenes físicos, grupos de volúmenes y volúmenes lógicos.
- **Sistemas de archivos:** permite seleccionar sistemas como `ext4`, `XFS` o `Btrfs`.
- **Montaje de almacenamiento:** montaje del volumen lógico en el directorio elegido.
- **Samba:** configuración de carpetas compartidas y usuarios para acceder desde otros equipos.
- **Integridad de archivos:** generación de sumas de comprobación MD5.
- **Copias de seguridad:** creación de una copia del directorio principal del NAS.
- **Interfaz web:** exploración de archivos, subida y descarga de ficheros y descarga de carpetas en ZIP.
- **Configuración persistente:** guarda el directorio de almacenamiento seleccionado en un archivo JSON.

## Requisitos

- Linux con permisos de administración.
- Python 3.
- Gestor de paquetes `apt` en sistemas Debian o Ubuntu.
- Discos adicionales para crear un RAID.
- Dependencias y herramientas del sistema:

  - `mdadm`
  - `lvm2`
  - `parted`
  - `gdisk`
  - `util-linux`
  - `e2fsprogs` u otras herramientas para el sistema de archivos seleccionado
  - `samba`
  - `md5deep`, para las comprobaciones de integridad
  - `python3-flask`
  - `python3-rich`

## Instalación

Clona el repositorio:

```bash
git clone https://github.com/nkv-alex/nkv-nas.git
cd nkv-nas
```

Instala las dependencias de Python:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-flask python3-rich
```

Instala las herramientas de almacenamiento que necesites:

```bash
sudo apt install mdadm lvm2 parted gdisk util-linux e2fsprogs samba
```

Para comprobar que el archivo principal tiene una sintaxis Python válida:

```bash
python3 -m py_compile nkv-nas.py
```

> La comprobación de sintaxis no garantiza que todas las funciones se ejecuten correctamente. Consulta las advertencias de seguridad y limitaciones antes de utilizarlo.

## Uso

Ejecuta el programa:

```bash
sudo python3 nkv-nas.py
```

El menú principal ofrece las siguientes opciones:

| Opción | Función |
|---|---|
| `1` | Configurar Samba y la carpeta compartida |
| `2` | Generar sumas de comprobación de los archivos |
| `3` | Preparar discos y configurar el almacenamiento NAS |
| `4` | Crear una copia del directorio de almacenamiento |
| `5` | Iniciar la interfaz web |
| `X` | Salir |

Las opciones que modifican discos, servicios o permisos requieren privilegios adecuados.

## Configuración del almacenamiento

La configuración del NAS permite seleccionar discos, establecer el tamaño de las particiones, elegir el sistema de archivos y definir los nombres del RAID y de los volúmenes LVM.

El flujo previsto es:

1. Seleccionar los discos que se utilizarán.
2. Preparar las particiones.
3. Crear el conjunto RAID cuando corresponda.
4. Crear el volumen físico de LVM.
5. Crear el grupo y el volumen lógico.
6. Formatear y montar el volumen.
7. Guardar el directorio de almacenamiento para las demás funciones.

**Importante:** el programa contiene operaciones destructivas que pueden borrar particiones, metadatos RAID y datos de los discos seleccionados. No lo ejecutes con discos que contengan información que quieras conservar.

## Compartir archivos con Samba

La opción de Samba permite configurar:

- El directorio compartido.
- El usuario autorizado.
- La contraseña de Samba.
- El acceso de invitados.
- El acceso de solo lectura o lectura y escritura.
- La visibilidad de la carpeta en la red.

Una vez configurado el servicio, el programa muestra una dirección de acceso para clientes de la red local, por ejemplo:

```text
\\IP_DEL_SERVIDOR\shared
```

La disponibilidad de esta ruta depende de la configuración de Samba y de la red.

## Comprobación de integridad

La herramienta puede generar sumas MD5 para los archivos del directorio de almacenamiento.

El resultado se guarda en:

```text
checksums.md5
```

Estas sumas permiten detectar cambios accidentales en los archivos comparando los resultados con una referencia anterior. **MD5 no es adecuado para verificar autenticidad frente a un atacante**; para ese propósito conviene utilizar SHA-256 y proteger las referencias de confianza.

## Copias de seguridad

La opción de copia de seguridad crea una copia del directorio principal con el sufijo `_backup`.

Por ejemplo, si el almacenamiento está en `/mnt/nas`, la copia se crea en:

```text
/mnt/nas_backup
```

Esta operación copia archivos, pero no constituye por sí sola una estrategia de backup completa. Es recomendable utilizar otro disco o equipo y comprobar periódicamente que los datos pueden restaurarse.

## Interfaz web

La interfaz web permite:

- Navegar por el directorio de almacenamiento.
- Consultar el tamaño y la fecha de modificación de los archivos.
- Subir archivos.
- Descargar archivos individuales.
- Descargar carpetas como archivos ZIP.

La aplicación está configurada para escuchar en el puerto `5000` y en todas las interfaces de red:

```text
http://IP_DEL_SERVIDOR:5000
```

**Advertencia:** el código actual no implementa autenticación de usuarios para la interfaz web. No la expongas a Internet ni a redes no confiables. Antes de utilizarla en un NAS real, añade autenticación, protección CSRF, límites de subida y controles de acceso.

## Seguridad y limitaciones

- Haz copias de seguridad antes de modificar discos o volúmenes.
- Comprueba cuidadosamente los nombres de dispositivo, como `/dev/sdb` o `/dev/nvme0n1`.
- Prueba primero en una máquina virtual con discos de prueba.
- No ejecutes el programa en producción sin revisar las operaciones destructivas.
- Revisa el uso de comandos de shell y la validación de las entradas.
- Restringe el acceso a Samba y a la interfaz web.
- Verifica la configuración y el estado de los servicios después de cada operación.

El código actual necesita pruebas y correcciones antes de considerarse apto para producción. En particular, la rutina de creación del NAS presenta un posible error al contar los discos seleccionados y necesita revisar el tratamiento del caso de un solo disco y la selección del nivel RAID.

## Tecnologías

- Python 3
- Flask
- Rich
- Linux RAID (`mdadm`)
- LVM
- Samba
- Herramientas de particionado y sistemas de archivos

## Autor

**nkv-alex**

Repositorio: https://github.com/nkv-alex/nkv-nas
