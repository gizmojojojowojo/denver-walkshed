"""Rebuild the East Colfax teaching snapshot. Python 3.10+, standard library."""
import argparse
import collections
import heapq
import json
import math
import pathlib
import re
import tempfile
import urllib.parse
import urllib.request
import zipfile

CITY = "https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/ArcGIS/rest/services/"
SIDE = CITY + "ODC_TRANS_SIDEWALKS_L/FeatureServer/143"
STREETS = CITY + "ODC_TRANS_STREET_L/FeatureServer/145"
BUS = CITY + "ODC_TRANS_RTDBUSTOPS_P/FeatureServer/281"
BLOCK = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10"
PL = "https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/Colorado/co2020.pl.zip"
BBOX = (-104.921, 39.731, -104.893, 39.750)
# Coordinates are meters, relative to the southwest corner. Scale approximations
# stay within 0.3% across this neighborhood.
MX = 111319.49 * math.cos(math.radians(sum(BBOX[1::2]) / 2))
MY = 111034.0
BUDGET = 720


def xy(lon, lat):
    return ((lon - BBOX[0]) * MX, (lat - BBOX[1]) * MY)


def cached(url, file):
    if not file.exists():
        request = urllib.request.Request(
            url, headers={"User-Agent": "DenverWalkshed/1.0 public research"}
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            file.write_bytes(response.read())
    return file


def features(cache, url, fields, tag, geometry=True):
    rows = []
    offset = 0
    while True:
        query = {
            "f": "json",
            "where": "1=1",
            "outFields": fields,
            "geometryType": "esriGeometryEnvelope",
            "geometry": ",".join(map(str, BBOX)),
            "spatialRel": "esriSpatialRelIntersects",
            "inSR": 4326,
            "outSR": 4326,
            "returnGeometry": str(geometry).lower(),
        }
        if tag == "side":
            query.update(orderByFields="OBJECTID", resultRecordCount=2000, resultOffset=offset)
        path = cache / (tag + (str(offset // 2000 + 1) if offset else "") + ".json")
        data = json.loads(
            cached(url + "/query?" + urllib.parse.urlencode(query), path).read_bytes()
        )
        if "error" in data:
            raise RuntimeError(data["error"])
        rows.extend(data["features"])
        if not data.get("exceededTransferLimit"):
            return rows
        if tag != "side" or not data["features"]:
            raise RuntimeError("Unexpected pagination in " + tag)
        offset += len(data["features"])


def occupied(zip_path, blocks):
    total = {b["GEOID"]: int(b["HU100"]) for b in blocks}
    # Census 2020 PL geography record fields 8 and 9 are LOGRECNO and GEOID.
    with zipfile.ZipFile(zip_path) as archive:
        numbers = {}
        with archive.open("cogeo2020.pl") as geo:
            for record in geo:
                fields = record.split(b"|", 9)
                if fields[2] == b"750":
                    geoid = fields[8].decode().split("US")[-1]
                    if geoid in total:
                        numbers[fields[7]] = geoid
        counts = {}
        with archive.open("co000022020.pl") as part:
            for record in part:
                fields = record.rstrip().split(b"|")
                geoid = numbers.get(fields[4])
                if geoid:
                    units, homes, vacant = map(int, fields[-3:])
                    if units != total[geoid] or units != homes + vacant:
                        raise ValueError("Housing control total mismatch at " + geoid)
                    counts[geoid] = homes
    if counts.keys() != total.keys():
        raise ValueError("Missing housing joins")
    return counts


def point_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2)) if length2 else 0
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def simplify(points, tolerance=0.7):
    if len(points) <= 2:
        return points
    distance, index = max(
        (point_segment(p, points[0], points[-1]), i) for i, p in enumerate(points[1:-1], 1)
    )
    if distance <= tolerance:
        return [points[0], points[-1]]
    return simplify(points[: index + 1])[:-1] + simplify(points[index:])


class Graph:
    def __init__(self):
        self.nodes = []
        self.buckets = collections.defaultdict(list)
        self.links = {}

    def nearby(self, p, radius):
        bx, by = (math.floor(v / 24) for v in p)
        reach = math.ceil(radius / 24)
        for x in range(bx - reach, bx + reach + 1):
            for y in range(by - reach, by + reach + 1):
                for i in self.buckets.get((x, y), []):
                    distance = math.dist(self.nodes[i], p)
                    if distance <= radius:
                        yield distance, i

    def index(self, p):
        near = min(self.nearby(p, 0.8), default=None)
        if near:
            return near[1]
        n = len(self.nodes)
        self.nodes.append([round(v, 1) for v in p])
        self.buckets[tuple(math.floor(v / 24) for v in p)].append(n)
        return n

    def line(self, p, q):
        left, right = self.index(p), self.index(q)
        if left != right:
            self.links[tuple(sorted([left, right]))] = round(
                math.dist(self.nodes[left], self.nodes[right]), 2
            )


def walk(adj, sources, cutoff=math.inf):
    distance = [math.inf] * len(adj)
    queue = [(0, s) for s in sources]
    for s in sources:
        distance[s] = 0
    heapq.heapify(queue)
    while queue:
        d, u = heapq.heappop(queue)
        if d != distance[u] or d > cutoff:
            continue
        for v, length in adj[u]:
            t = d + length
            if t < distance[v] and t <= cutoff:
                distance[v] = t
                heapq.heappush(queue, (t, v))
    return distance


def baseline_graph(lines):
    graph = Graph()
    paths = [
        path
        for f in lines
        if f["attributes"]["SIDEWALKTYPE"] in ("Sidewalk", "Trail", "Crosswalk", "Other Path")
        for path in f["geometry"]["paths"]
        if len(path) >= 2
    ]
    occurrences = collections.Counter(tuple(v) for path in paths for v in path)
    for path in paths:
        # Preserve shared interior survey vertices when simplifying curves.
        breaks = (
            [0]
            + [i for i in range(1, len(path) - 1) if occurrences[tuple(path[i])] > 1]
            + [len(path) - 1]
        )
        for l, r in zip(breaks, breaks[1:]):
            points = simplify([xy(*v) for v in path[l : r + 1]])
            for a, b in zip(points, points[1:]):
                steps = max(1, math.ceil(math.dist(a, b) / 25))
                prev = a
                for i in range(1, steps + 1):
                    endpoint = tuple(x + (y - x) * i / steps for x, y in zip(a, b))
                    graph.line(prev, endpoint)
                    prev = endpoint
    return graph


def street_name(raw):
    words = raw.split("/")[0].title().split()
    expansions = {
        "N": "North",
        "E": "East",
        "St": "Street",
        "Ave": "Avenue",
        "Pl": "Place",
        "Pkwy": "Parkway",
    }
    return re.sub(
        r"(\d)(St|Nd|Rd|Th)\b",
        lambda m: m[0].lower(),
        " ".join(expansions.get(w, w) for w in words),
    )


def choose_links(graph, adj, baseline, origins, streets):
    """Screen hypothetical crossings of mapped, named street centerlines."""
    options = []
    evaluated = set()
    for feature in streets:
        attr = feature["attributes"]
        if (
            not attr["FULLNAME"]
            or attr["STATUS"] != "CONSTRUCTED"
            or attr["F_ZLEV"] != 0
            or attr["T_ZLEV"] != 0
        ):
            continue
        if "ALLEY" in attr["FULLNAME"] or "RAMP" in attr["FULLNAME"]:
            continue
        for path in feature["geometry"]["paths"]:
            for p, q in zip(path, path[1:]):
                x, y = xy(*p)
                u, v = xy(*q)
                length = math.hypot(u - x, v - y)
                if length < 1:
                    continue
                dx, dy = (u - x) / length, (v - y) / length
                # Sample both sides of each named roadway. Keep short links that
                # cross the centerline approximately perpendicularly.
                for n in range(math.ceil(length / 18)):
                    t = (n + 0.5) / math.ceil(length / 18)
                    cx, cy = x + (u - x) * t, y + (v - y) * t
                    left = []
                    right = []
                    for _, i in graph.nearby((cx, cy), 26):
                        if not math.isfinite(baseline[i]):
                            continue
                        gx, gy = graph.nodes[i][0] - cx, graph.nodes[i][1] - cy
                        along = dx * gx + dy * gy
                        across = -dy * gx + dx * gy
                        if abs(along) > 11 or not 3 <= abs(across) <= 23:
                            continue
                        (left if across < 0 else right).append((i, along))
                    for a, posa in left:
                        for b, posb in right:
                            if abs(posa - posb) > 7:
                                continue
                            pair = tuple(sorted([a, b]))
                            if pair in evaluated:
                                continue
                            evaluated.add(pair)
                            w = math.dist(graph.nodes[a], graph.nodes[b])
                            if not 10 <= w <= 42 or abs(baseline[a] - baseline[b]) < w + 45:
                                continue
                            near, far = (a, b) if baseline[a] < baseline[b] else (b, a)
                            entry = baseline[near] + w
                            if entry >= BUDGET:
                                continue
                            after = walk(adj, [far], BUDGET - entry)
                            gain = sum(
                                o["homes"]
                                for o in origins
                                if baseline[o["node"]] + o["offset"] > BUDGET
                                and entry + after[o["node"]] + o["offset"] <= BUDGET
                            )
                            if gain:
                                options.append(
                                    (
                                        gain,
                                        round(abs(baseline[a] - baseline[b]) - w, 2),
                                        a,
                                        b,
                                        attr["FULLNAME"],
                                        attr["FROMNAME"],
                                        attr["TONAME"],
                                    )
                                )
    chosen = []
    for gain, saving, a, b, street, fromname, toname in sorted(options, reverse=True):
        if any(
            math.dist(graph.nodes[a], graph.nodes[c["a"]]) < 200 or c["street"] == street
            for c in chosen
        ):
            continue
        name = street_name(street)
        chosen.append(
            {
                "a": a,
                "b": b,
                "name": f"{name} crossing",
                "street": street,
                "description": f"Hypothetical crossing of {name} between {street_name(fromname or 'one block end')} and {street_name(toname or 'the other block end')}. Field verification required.",
            }
        )
        if len(chosen) == 3:
            break
    if len(chosen) != 3:
        raise ValueError("Fewer than three distinct crossing scenarios")
    return chosen


def build(cache):
    raw = features(
        cache,
        SIDE,
        "OBJECTID,ROUTABLE,SIDEWALKTYPE,CROSSINGTYPE,SIDEWALKSTATUS,STREETNAME,Z_LEV",
        "side",
    )
    bus = features(cache, BUS, "BUS_STOPID,STOP_NAME,DIRECTION,ROUTES", "bus")
    blocks = [
        x["attributes"]
        for x in features(cache, BLOCK, "GEOID,INTPTLAT,INTPTLON,HU100,POP100", "blocks", False)
    ]
    counts = occupied(cached(PL, cache / "co2020.pl.zip"), blocks)
    graph = baseline_graph(raw)
    selected = []
    for f in sorted(bus, key=lambda row: row["attributes"]["BUS_STOPID"]):
        a, p = f["attributes"], f["geometry"]
        if not a["STOP_NAME"].startswith("Colfax Ave & ") or a["DIRECTION"] != "E":
            continue
        pos = xy(p["x"], p["y"])
        distance, i = min(graph.nearby(pos, 35))
        selected.append(
            {
                "node": i,
                "name": a["STOP_NAME"],
                "id": str(a["BUS_STOPID"]),
                "snapMeters": round(distance, 1),
            }
        )
    adj = [[] for _ in graph.nodes]
    for (a, b), w in graph.links.items():
        adj[a].append((b, w))
        adj[b].append((a, w))
    before = walk(adj, [s["node"] for s in selected])
    origins = []
    for b in sorted(blocks, key=lambda b: b["GEOID"]):
        lon, lat = float(b["INTPTLON"]), float(b["INTPTLAT"])
        if not (BBOX[0] < lon < BBOX[2] and BBOX[1] < lat < BBOX[3]) or counts[b["GEOID"]] == 0:
            continue
        p = xy(lon, lat)
        closest = min(graph.nearby(p, 150), default=None)
        if closest is None:
            continue
        distance, i = closest
        origins.append(
            {
                "node": i,
                "offset": round(distance, 1),
                "homes": counts[b["GEOID"]],
                "label": "Block " + b["GEOID"][-4:] + " · tract " + b["GEOID"][5:11],
                "geoid": b["GEOID"],
                "point": [round(x, 1) for x in p],
            }
        )
    streets = features(
        cache, STREETS, "FULLNAME,STATUS,F_ZLEV,T_ZLEV,FROMNAME,TONAME", "streets"
    )
    cand = choose_links(graph, adj, before, origins, streets)
    return {
        "nodes": graph.nodes,
        "edges": [[a, b, w] for (a, b), w in sorted(graph.links.items())],
        "origins": origins,
        "stops": selected,
        "candidates": cand,
        "metadata": {
            "title": "East Colfax Avenue",
            "subtitle": "Eastbound Colfax stops · Denver, Colorado",
            "weights": "2020 occupied housing units (Census PL table H1)",
            "lengthUnits": "meters",
            "speedMps": 1.2,
            "walkBudgetMeters": 720,
            "boundsWgs84": list(BBOX),
            "projection": {"origin": [BBOX[0], BBOX[1]], "metersPerDegree": [MX, MY]},
            "sourceLinks": [
                {"name": "Denver sidewalk centerlines", "url": SIDE},
                {"name": "Denver / RTD stop inventory", "url": BUS},
                {"name": "Denver street centerlines", "url": STREETS},
                {"name": "2020 Census block locations", "url": BLOCK},
                {"name": "Census occupied housing units", "url": PL},
            ],
        },
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cache",
        type=pathlib.Path,
        default=pathlib.Path(tempfile.gettempdir()) / "walkshed-inputs",
    )
    ap.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path(__file__).resolve().parents[1] / "dist/corridor.json",
    )
    args = ap.parse_args()
    args.cache.mkdir(exist_ok=True, parents=True)
    snapshot = build(args.cache)
    args.out.parent.mkdir(exist_ok=True, parents=True)
    args.out.write_text(json.dumps(snapshot, separators=(",", ":"), allow_nan=False) + "\n")
    print({k: len(v) for k, v in snapshot.items() if isinstance(v, list)})
