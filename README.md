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

## Instalación

Requiere Python 3.10+.

```bash
cd roomba-app
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

Menú interactivo:

```bash
roomba
```

Comandos directos:

```bash
roomba start          # inicia la limpieza
roomba dock           # vuelve a la base
roomba --status       # muestra el estado del robot y sale
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

## Limitaciones conocidas

- Limpieza por habitaciones/mapa: no implementado (el protocolo V4 para mapas
  aún no está documentado públicamente).
- Programación de horarios: topic identificado (`rw-schedule`), payload pendiente.
- Proyecto no afiliado a iRobot. Úsalo solo con tu propio robot y tu propia cuenta.
