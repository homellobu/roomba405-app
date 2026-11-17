PHASE = {
    "charge": "Cargando",
    "run": "Limpiando",
    "stop": "En reposo",
    "pause": "En pausa",
    "hmUsrDock": "Volviendo a la base",
    "hmMidMsn": "Volviendo (media misión)",
    "hmPostMsn": "Volviendo (fin de misión)",
    "evac": "Vaciando depósito",
    "chargingerror": "Error de carga",
}

CYCLE = {
    "none": "Inactivo",
    "clean": "Limpieza estándar",
    "spot": "Limpieza puntual",
    "dock": "Acoplándose",
    "evac": "Vaciado de depósito",
    "train": "Mapeo",
}

ERRORS = {
    0: "Sin errores",
    1: "Rueda izquierda en el aire",
    2: "Cepillo principal atascado",
    5: "Rueda derecha en el aire",
    6: "Sensor de desniveles",
    8: "Motor de aspiración",
    9: "Parachoques atascado",
    11: "Motor de aspiración",
    14: "Depósito ausente",
    15: "Reinicio necesario",
    16: "Golpe al acoplarse",
    17: "Camino bloqueado",
    18: "Acoplamiento fallido",
    34: "Depósito lleno",
    46: "Batería baja",
    66: "Batería muy baja",
    68: "Robot perdido, reubícalo",
}


def render_state(state: dict) -> str:
    if not state:
        return "  Aún no se ha recibido estado del robot."
    lines = []

    if state.get("name"):
        lines.append(f"  Nombre      {state['name']}")
    if state.get("sku"):
        lines.append(f"  Modelo      {state['sku']}")
    firmware = state.get("softwareVer") or state.get("soft_ver")
    if firmware:
        lines.append(f"  Firmware    {firmware}")

    battery = state.get("batPct")
    if battery is not None:
        filled = max(0, min(20, battery // 5))
        bar = "█" * filled + "░" * (20 - filled)
        lines.append(f"  Batería     {battery}%  [{bar}]")

    mission = state.get("cleanMissionStatus") or {}
    if mission.get("phase"):
        lines.append(f"  Estado      {PHASE.get(mission['phase'], mission['phase'])}")
    if mission.get("cycle"):
        lines.append(f"  Ciclo       {CYCLE.get(mission['cycle'], mission['cycle'])}")
    if "error" in mission:
        code = mission["error"]
        lines.append(f"  Error       {ERRORS.get(code, f'Código {code}')}")
    if mission.get("mssnM"):
        lines.append(f"  Tiempo      {mission['mssnM']} min")
    if mission.get("sqft") is not None:
        lines.append(f"  Superficie  {mission['sqft']} ft²")

    bin_state = state.get("bin") or {}
    if bin_state:
        flags = ["presente" if bin_state.get("present") else "ausente"]
        if bin_state.get("full"):
            flags.append("LLENO")
        lines.append(f"  Depósito    {', '.join(flags)}")

    pad = state.get("detectedPad") or state.get("padWetness")
    if pad:
        lines.append(f"  Pad/suelo   {pad}")

    pose = state.get("pose") or {}
    if pose.get("point"):
        point = pose["point"]
        lines.append(f"  Posición    x={point.get('x')}  y={point.get('y')}  θ={pose.get('theta')}")

    signal = state.get("signal")
    rssi = signal.get("rssi") if isinstance(signal, dict) else signal
    if rssi is not None:
        lines.append(f"  Wi-Fi RSSI  {rssi} dBm")

    dock = state.get("dock") or {}
    if dock.get("known") is not None:
        lines.append(f"  Base        {'conocida' if dock['known'] else 'desconocida'}")

    return "\n".join(lines) if lines else "  (estado vacío)"
