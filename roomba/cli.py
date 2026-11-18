import argparse
import logging
import os
import sys
from getpass import getpass

import requests

from .cloud import IRobotCloud, LoginError
from .robot import COMMANDS, Roomba
from .state import render_state
from .store import Store


def ask_credentials(store: Store, force: bool = False):
    if force or not store.email or not store.password:
        print()
        email = input("Email de iRobot:  ").strip()
        password = getpass("Contraseña:       ")
        if not email or not password:
            print("Credenciales vacías, abortando.")
            sys.exit(1)
        store.set_credentials(email, password)


def login_flow(store: Store, cloud: IRobotCloud, force: bool = False) -> dict:
    ask_credentials(store, force=force)
    if not force:
        cached = store.cached_session()
        if cached:
            return cached
    try:
        session = cloud.login(store.email, store.password)
    except LoginError as e:
        print(f"Login fallido: {e}")
        store.forget_all()
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"Error del servidor: {e}")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error de red: {e}")
        sys.exit(1)
    store.save_session(session)
    return session


def resolve_blid(store: Store, session: dict, prefer_blid: str | None = None):
    robots = session.get("robots") or {}
    if not robots:
        raise RuntimeError("No hay robots vinculados a esta cuenta")
    if prefer_blid:
        if prefer_blid not in robots:
            raise RuntimeError(f"El BLID {prefer_blid} no está en tu cuenta")
        store.set_blid(prefer_blid)
        return prefer_blid
    stored = store.blid
    if stored in robots:
        return stored
    if len(robots) == 1:
        blid = next(iter(robots))
        store.set_blid(blid)
        return blid
    return None


def connect_robot(store: Store, cloud: IRobotCloud, blid: str | None = None,
                  picker=None) -> Roomba:
    session = login_flow(store, cloud)
    blid = resolve_blid(store, session, prefer_blid=blid)
    if blid is None and picker:
        blid = picker(session["robots"])
        store.set_blid(blid)
    try:
        robot = Roomba(store, cloud, session, blid=blid)
        robot.connect()
    except Exception as e:
        print(f"Conexión fallida: {e}")
        store.forget_session()
        session = login_flow(store, cloud)
        robot = Roomba(store, cloud, session, blid=blid)
        robot.connect()
    return robot


def run_menu(robot: Roomba):
    print(f"Conectado: {robot.name}")
    try:
        while True:
            print()
            for i, (cmd, label) in enumerate(COMMANDS.items(), 1):
                print(f"  {i}) {label}")
            print("  e) Estado del robot")
            print("  q) Salir")
            choice = input("> ").strip().lower()

            if choice == "q":
                break
            if choice == "e":
                robot.refresh_state()
                print()
                print(render_state(robot.snapshot()))
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(COMMANDS):
                cmd = list(COMMANDS)[int(choice) - 1]
                try:
                    robot.send(cmd)
                    print(f"  Enviado: {COMMANDS[cmd]}")
                except Exception as e:
                    print(f"  Fallo al enviar: {e}")
    finally:
        robot.disconnect()
        print("Desconectado")


def run_command(robot: Roomba, command: str, watch: bool):
    robot.send(command)
    print(f"Enviado: {COMMANDS.get(command, command)}")
    if watch:
        import time

        time.sleep(2)
        robot.refresh_state()
        print()
        print(render_state(robot.snapshot()))


def main():
    parser = argparse.ArgumentParser(
        prog="roomba",
        description="Controla tu Roomba 405 Combo (protocolo V4 de iRobot) desde la terminal.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=sorted(COMMANDS),
        help="Comando directo (sin menú interactivo)",
    )
    parser.add_argument("--country", default=os.environ.get("ROOMBA_COUNTRY", "ES"),
                        help="Código de país para el descubrimiento (por defecto ES)")
    parser.add_argument("--blid", default=None, help="BLID del robot si tienes varios")
    parser.add_argument("--status", action="store_true", help="Muestra el estado y sale")
    parser.add_argument("--gui", action="store_true", help="Abre la interfaz gráfica")
    parser.add_argument("--watch", action="store_true",
                        help="Tras un comando, muestra el estado del robot")
    parser.add_argument("--logout", action="store_true", help="Borra credenciales guardadas")
    parser.add_argument("--debug", action="store_true",
                        help="Muestra el detalle de cada paso (diagnóstico de problemas)")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s")

    store = Store()
    if args.logout:
        store.forget_all()
        print("Credenciales borradas.")
        return

    cloud = IRobotCloud(country=args.country)
    robot = connect_robot(store, cloud, blid=args.blid)

    try:
        if args.gui:
            from .gui import RoombaGUI
            RoombaGUI(robot).run()
        elif args.status:
            robot.refresh_state()
            print()
            print(render_state(robot.snapshot()))
        elif args.command:
            run_command(robot, args.command, watch=args.watch)
        else:
            run_menu(robot)
    finally:
        robot.disconnect()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(0)
