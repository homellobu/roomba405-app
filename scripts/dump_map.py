#!/usr/bin/env python3
import json
import os
import sys
import tarfile
from pathlib import Path

OUT = Path.home() / ".roomba_app" / "map_dump.txt"


def abbr(value, limit=160):
    text = json.dumps(value, ensure_ascii=False)
    if len(text) > limit:
        text = text[:limit] + " ...(" + str(len(text)) + " chars)"
    return text


def coords_summary(feature):
    geometry = feature.get("geometry") or {}
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    points = []

    def walk(node, depth=0):
        if isinstance(node, (int, float)):
            return
        if isinstance(node, list) and len(node) >= 2 \
                and isinstance(node[0], (int, float)):
            points.append(node)
            return
        if isinstance(node, list):
            for child in node[:6]:
                walk(child, depth + 1)

    walk(coords)
    return {
        "geometry": gtype or None,
        "coordinates_kind": type(coords).__name__,
        "sample_points": points[:5],
        "total_sampled": len(points),
    }


def feature_report(name, content, out):
    out.append(f"--- archivo: {name}")
    if not isinstance(content, dict):
        out.append(f"    tipo de contenido: {type(content).__name__} "
                   f"(no es un dict JSON)")
        return
    out.append(f"    claves principales: {list(content.keys())[:12]}")
    out.append(f"    type: {repr(content.get('type'))}")
    features = content.get("features")
    if not isinstance(features, list):
        other = {k: v for k, v in content.items() if k != "features"}
        for key, value in list(other.items())[:10]:
            out.append(f"    {key}: {abbr(value)}")
        return
    out.append(f"    numero de features: {len(features)}")
    counts = {}
    for feature in features:
        gtype = (feature.get("geometry") or {}).get("type") \
            if isinstance(feature, dict) else None
        counts[gtype or "(sin geometry)"] = \
            counts.get(gtype or "(sin geometry)", 0) + 1
    out.append(f"    features por tipo de geometria: {counts}")
    for i, feature in enumerate(list(features)[:4]):
        if not isinstance(feature, dict):
            continue
        props = feature.get("properties") or {}
        prop_keys = sorted(props.keys()) if isinstance(props, dict) else []
        out.append(f"    feature[{i}]: id={feature.get('id')!r} "
                   f"type={feature.get('type')!r}")
        out.append(f"              {coords_summary(feature)}")
        out.append(f"    propiedades de feature[{i}]: claves={prop_keys}")
        for key in prop_keys:
            value = props[key] if isinstance(props, dict) else None
            out.append(f"      {key}: {abbr(value, 100)}")


async def dump_robot(backend, label, out):
    out.append("")
    out.append("=" * 62)
    out.append(f"ROBOT: {label}")
    out.append("versiones de mapa (get_active_map_versions):")
    try:
        versions = await backend.robot.get_active_map_versions()
        out.append(abbr(versions, 800))
    except Exception as e:
        out.append(f"  ERROR: {e!r}")
        return
    from roombapy_prime.models.robot_info import parse_active_map_versions
    parsed = parse_active_map_versions(versions)
    if not parsed:
        out.append("  sin versiones de mapa activas")
        return
    version = parsed[0]
    p2map_id = version.p2map_id
    out.append(f"  version elegida: repr={version!r}"[:800])
    out.append("")
    out.append("metadatos del mapa (get_map_metadata):")
    try:
        metadata = await backend.robot.get_map_metadata(p2map_id)
        current = getattr(metadata, "current_map_version", None)
        out.append(f"  current_map_version: {current!r}")
        rooms = getattr(metadata, "rooms_metadata", None) or []
        out.append(f"  habitaciones en los metadatos: {len(rooms)}")
        for room in rooms:
            out.append(f"    - id={room.room_id!r} nombre={room.name!r} "
                       f"region_type={room.region_type!r}")
    except Exception as e:
        out.append(f"  ERROR: {e!r}")
        return
    out.append("")
    out.append("Descargando GeoJSON del mapa...")
    version_id = None
    for attr in ("user_p2mapv_id", "active_p2mapv_id", "p2mapv_id"):
        value = getattr(version, attr, None)
        if value:
            version_id = value
            break
    if not version_id:
        version_id = current
    if not version_id:
        out.append("  ERROR: sin version de mapa descargable")
        return
    out.append(f"  version_id usado: {version_id!r}")
    try:
        link = await backend.robot.get_map_geojson_link(p2map_id, version_id)
        out.append(f"  enlace (get_map_geojson_link): "
                   f"{abbr({k: v for k, v in link.items()} if isinstance(link, dict) else link, 400)}")
        url = link.get("map_url") if isinstance(link, dict) else None
        bundle = await backend.robot.download_map_bundle(url)
        out.append(f"  bundle descargado: {len(bundle)} bytes (tar.gz)")
        from roombapy_prime.models import parse_map_bundle
        files = parse_map_bundle(bundle)
        out.append(f"  archivos dentro del bundle: {list(files.keys())}")
        for name, content in files.items():
            feature_report(name, content, out)
    except Exception as e:
        out.append(f"  ERROR: {e!r}")


async def amain():
    from roomba.cli import login_flow, resolve_blid
    from roomba.cloud import IRobotCloud
    from roomba.prime_backend import PrimeBackend
    from roomba.store import Store

    country = os.environ.get("ROOMBA_COUNTRY", "ES")
    out = ["Volcado de mapa generado. Sin datos privados de coordenadas"
           " completas (solo muestras)."]
    store = Store()
    cloud = IRobotCloud(country=country)
    session = login_flow(store, cloud)
    blids = list(session["robots"].keys())
    for blid in blids:
        info = session["robots"][blid]
        nombre = info.get("name", "Roomba")
        backend = PrimeBackend(store.email, store.password,
                               country=country, blid=blid)
        try:
            backend.connect()
            backend._call(dump_robot(backend, f"{nombre} ({blid})", out),
                          timeout=120)
        except Exception as e:
            out.append(f"  ERROR conectando {nombre}: {e!r}")
        finally:
            try:
                backend.close()
            except Exception:
                pass
    return "\n".join(out)


def main():
    import asyncio
    text = asyncio.run(amain())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print("Informe listo en:", OUT)
    print("Copia ese archivo y envialo al asistente.")


if __name__ == "__main__":
    sys.exit(main())
