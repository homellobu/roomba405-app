# Controlador Roomba 405 Combo

Aplicación de escritorio/terminal para controlar un **Roomba 405 Combo** desde tu cuenta de iRobot.

> **Importante:** el Roomba 405 Combo pertenece a la nueva generación de iRobot
> (protocolo interno **V4**, modelos 105/205/405/505). A diferencia de los Roomba
> clásicos, **no admite control local MQTT**: todos los comandos pasan por la nube
> de iRobot (AWS IoT). Este proyecto usa el mismo protocolo que la app oficial,
> documentado en [roomba-v4](https://github.com/lvigilantecorreo-commits/roomba-v4).

## Comandos soportados

| Comando | Acción |
|---|---|
| `start` | Iniciar limpieza |
| `pause` | Pausar |
| `stop` | Detener |
| `resume` | Reanudar |
| `dock` | Volver a la base |
| `find` | Localizar (pitido) |
| `evac` | Vaciar depósito |
| `reset` | Reiniciar robot |

El estado (batería, fase de limpieza, errores, posición, Wi-Fi…) se lee del
device shadow de AWS. El token MQTT caduca en ~5 minutos; la app lo renueva
automáticamente cada 4 minutos.

### Volver a la base con reintentos

Si a veces el robot no encuentra la base al terminar de limpiar, la GUI y el
comando `dock` tienen un modo con reintentos: se envía el comando de regreso y
se comprueba el estado real del robot; si no entra en fase de regreso o carga,
se reintenta hasta 3 veces.

En la GUI usa el botón **"Volver a la base (con reintentos)"**. Si agota los
reintentos, el robot probablemente esté demasiado lejos o desorientado:
acércalo a la base y vuelve a pulsarlo.

## Instalación

Requiere Python 3.10+.

```bash
cd roomba-app
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

Interfaz gráfica (Tkinter, incluida en Python):

```bash
roomba --gui
```

Menú interactivo:

```bash
roomba
```

Comandos directos:

```bash
roomba start          # inicia la limpieza
roomba dock           # vuelve a la base
roomba --status       # muestra el estado del robot y sale
roomba --gui          # interfaz gráfica
roomba start --watch  # envía el comando y muestra el estado después
roomba --logout       # borra credenciales guardadas
```

Opciones:

- `--country XX` — código de país para el descubrimiento (por defecto `ES`).
- `--blid BLID` — selecciona el robot si tienes varios en la cuenta.

## Credenciales

La primera vez te pedirá el email y la contraseña de tu **cuenta iRobot** (las
mismas de la app oficial). Se guardan en `~/.roomba_app/config.json` con
permisos `0600` y la contraseña ofuscada. Borra el fichero o usa `roomba
--logout` para eliminarlas. No compartas ese fichero.

## Tests

```bash
pytest
```

Los tests no necesitan un robot real: cubren el renderizado de estado, el
almacén de credenciales y la cadena de login con respuestas simuladas.

## App con doble clic en macOS

Para tener la interfaz gráfica como una aplicación más del Mac:

```bash
bash scripts/make_mac_app.sh
```

Esto crea `Roomba.app` dentro de la carpeta del proyecto. Muévela a
Aplicaciones si quieres (`mv Roomba.app /Applications/`) y ábrela con doble
clic. La primera vez, si macOS muestra el aviso de "desarrollador no
verificado", haz clic derecho sobre la app > **Abrir** > **Abrir**.

La app usa el mismo entorno virtual del proyecto, así que actualiza con
`git pull` y vuelve a ejecutar el script si cambias de versión.

## Diagnóstico de problemas

Si el robot no responde o algo falla, ejecuta con `--debug` para ver en qué
paso se detiene:

```bash
roomba --debug --status
```

Comprobaciones habituales:

1. **¿El robot aparece como conectado en la app oficial de iRobot?** Si la app
   oficial tampoco lo ve, el robot está sin Wi-Fi o apagado: ponlo en la base
   y comprueba que la luz de Wi-Fi está fija.
2. **Login fallido (Gigya)**: email o contraseña incorrectos. Prueba a
   iniciar sesión en la app oficial. Para cambiar las credenciales guardadas:
   `roomba --logout` y vuelve a ejecutar.
3. **Login fallido en `/v2/login`**: el servidor de iRobot rechaza el acceso.
   Verifica que el robot está vinculado a ESA cuenta (no a otra).
4. **Se conecta pero no responde a los comandos**: el robot puede estar
   dormido en la base. Envía `find` (pitido) para comprobar si recibe algo;
   si suena, prueba `start` de nuevo.
5. **Varios robots en la cuenta**: usa `--blid` con el identificador que
   muestra `roomba --debug --status`.
6. **Comandos publicados sin efecto** (y en el log aparece "usando el prefijo
   corregido"): iRobot migra robots entre despliegues y el prefijo del topic
   de comandos cambia. La app lo detecta leyendo `svcEndpoints.svcDeplId` del
   estado del robot y reescribe el prefijo automáticamente.

## Limitaciones conocidas

- Limpieza por habitaciones/mapa: no implementado (el protocolo V4 para mapas
  aún no está documentado públicamente).
- Programación de horarios: topic identificado (`rw-schedule`), payload pendiente.
- Proyecto no afiliado a iRobot. Úsalo solo con tu propio robot y tu propia cuenta.
