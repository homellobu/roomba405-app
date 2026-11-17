#!/usr/bin/env python3
import sys
import traceback


def run():
    from roomba.cli import connect_robot
    from roomba.cloud import IRobotCloud
    from roomba.gui import RoombaGUI, pick_robot_dialog
    from roomba.store import Store

    store = Store()
    cloud = IRobotCloud()
    robot = connect_robot(store, cloud, picker=pick_robot_dialog)
    RoombaGUI(robot).run()


try:
    run()
except SystemExit:
    raise
except BaseException:
    error = traceback.format_exc()
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Roomba", error)
    except Exception:
        print(error, file=sys.stderr)
    sys.exit(1)
