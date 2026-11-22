"""Build IPCC AR6 sea-level projections per tide gauge, and the NOAA CO-OPS -> AR6 gauge mapping. Run by hand; never at run time.

Writes (all three are committed; nothing imports this script at request time):
  earthtrends/data/ar6_gauges.npz       int16 levels (mm) and rates (0.1 mm a year) at the AR6 tide-gauge locations
  earthtrends/data/ar6_gauges.json      manifest: DOI, version, md5 of every source entry, baseline, units, citations
  earthtrends/data/coops_to_psmsl.csv   every CO-OPS water-level station the app can answer with -> an AR6 location

Data: Garner et al. (2021), IPCC AR6 Sea Level Projections, version 20210809, Zenodo record 6382554
  (doi:10.5281/zenodo.6382554, concept doi:10.5281/zenodo.5914709), CC-BY-4.0. `ar6-regional-confidence.zip` (9.24 GB)
  is a zip of separately deflated netCDF4 files, so HTTP Range requests fetch only the 51 entries used (about 3.8 GB):
  total and its rates, sterodynamic, Greenland, Antarctica, glaciers, land water storage and vertical land motion (VLM),
  for SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5 at medium confidence and SSP1-2.6, SSP2-4.5, SSP5-8.5 at low confidence.
  VLM does not depend on the scenario, so it is fetched once per confidence (from different scenarios, and checked equal).
Gauge names: PSMSL station list, https://psmsl.org/data/obtaining/rlr.monthly.data/filelist.txt
Stations: NOAA CO-OPS water-level station list, the same request earthtrends/data/coops.py makes.

Run (standard library + numpy + httpx, all already project dependencies):
  uv run python scripts/build_ar6.py
Each fetched entry is cut to the kept quantiles and decades (all locations) and cached in data/raw/ar6/ (gitignored),
with its md5; so are the small lists. A rerun fetches nothing; delete that folder to fetch again.
The netCDF4 files are read by the small HDF5 reader below (numpy + stdlib): it handles what these files use (superblock 0,
version-2 object headers with compact links, contiguous or chunked datasets, shuffle + deflate) and fails on anything else.
"""
import csv
import hashlib
import json
import re
import struct
import sys
import time
import zlib
from datetime import date
from pathlib import Path

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_grace import write_npz  # noqa: E402  (byte-identical npz from run to run)

RECORD = 6382554
API = f"https://zenodo.org/api/records/{RECORD}"
ZIP = "ar6-regional-confidence.zip"
ZIP_URL = f"{API}/files/{ZIP}/content"
LIST_URL = f"{API}/files/location_list.lst/content"
VERSION = "20210809"
PREFIX = "ar6-regional-confidence/regional/confidence_output_files/"
PSMSL_LIST = "https://psmsl.org/data/obtaining/rlr.monthly.data/filelist.txt"

Q = (0.05, 0.167, 0.5, 0.833, 0.95)
YEARS = tuple(range(2020, 2151, 10))
SCENARIOS = (("ssp126", "medium"), ("ssp245", "medium"), ("ssp370", "medium"), ("ssp585", "medium"),
             ("ssp126", "low"), ("ssp245", "low"), ("ssp585", "low"))
COMPONENTS = ("total", "oceandynamics", "GIS", "AIS", "glaciers", "landwaterstorage", "verticallandmotion")
VLM_FROM = {"medium": "ssp245", "low": "ssp585"}
FILL = -32768
GRID = 10**9  # AR6 location IDs below this are PSMSL gauge IDs, from it up 1-degree grid cells

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "earthtrends" / "data"
CACHE = ROOT / "data" / "raw" / "ar6"

# The build fails unless the file reproduces AR6 for New York (The Battery), PSMSL 12, SSP2-4.5 medium confidence, 2050.
CHECK_ID, CHECK_SCEN, CHECK_YEAR = 12, "ssp245", 2050
CHECK_TOTAL_MM = [209, 266, 358, 464, 545]
CHECK_RATE_TENTHS = 86  # median, 8.6 mm a year

# Mapping rules, in order: Great Lakes -> none; a hand-checked override; the nearest AR6 gauge within 3 km; the nearest
# within 15 km whose name shares a word; else the nearest valid AR6 1-degree cell, a regional estimate.
NEAR_KM, NAME_KM = 3.0, 15.0
# Words too common in gauge names to say two names are the same place.
GENERIC = set("""THE AND OF AT ON IN BAY PORT POINT PIER HARBOR HARBOUR ISLAND ISLE RIVER CITY BEACH INLET CREEK SOUND
STATION LAKE NORTH SOUTH EAST WEST NEW FORT CAPE KEY SAINT YACHT CLUB USCG COAST GUARD LIGHT ENTRANCE MOUTH MARINA DOCK
BRIDGE ROAD STATE PARK TIDE GAUGE SAN SANTA PASS CHANNEL LANDING HEAD HAVEN SPRINGS OCEAN GULF LOWER UPPER""".split())
# coops_id: (PSMSL id, reason). Stations no rule above matched that lie on the same water body (or small island) as an
# AR6 gauge; each checked by hand on 2026-11-22 against the gauge's PSMSL station page (position, record span).
OVERRIDES: dict[str, tuple[int, str]] = {
    "1612401": (155, "same south shore of Oahu as Honolulu (record 1905-2025)"),
    "1631428": (540, "same small island as Apra Harbor, Guam (record 1948-2025)"),
    "8452944": (430, "upper Narragansett Bay, like Providence (record 1938-2025)"),
    "8546252": (135, "same tidal Delaware River reach in Philadelphia (record 1900-2025)"),
    "8555889": (1153, "mouth of Delaware Bay, like Cape May (record 1966-2025)"),
    "8637689": (597, "across the York River from Gloucester Point (record 1950-2003)"),
    "8639348": (399, "Elizabeth River, Norfolk harbour, like Portsmouth (record 1935-1987)"),
    "8679598": (112, "same St Marys River entrance as Fernandina Beach (record 1897-2025)"),
    "8720219": (2326, "lower St Johns River; Mayport (Bar Pilots Dock) is the current Mayport gauge (record 2001-2025)"),
    "8726607": (520, "Tampa Bay, like St. Petersburg (record 1947-2025)"),
    "8764227": (440, "Atchafalaya Bay, like Eugene Island (record 1939-1974)"),
    "8774513": (538, "Copano and Aransas bays, like Rockport (record 1948-2025)"),
    "8775792": (1903, "same Padre Island shore as Bob Hall Pier, Corpus Christi (record 1998-2021)"),
    "8776139": (1903, "Padre Island, inside the barrier from Bob Hall Pier, Corpus Christi (record 1998-2021)"),
    "9410678": (245, "same San Pedro Bay port complex as Los Angeles (record 1923-2025)"),
    "9414863": (10, "central San Francisco Bay, like San Francisco (record 1854-2025)"),
    "9415102": (2330, "Carquinez Strait and Suisun Bay, like Port Chicago (record 1976-2025)"),
}

RANGE_NAMES = {  # D7: what each band is called
    "medium": {"0.167-0.833": "likely range (about 2 in 3 chance)", "0.05-0.95": "5th to 95th percentile range"},
    "low": {"0.167-0.833": "16.7th to 83.3rd percentile range", "0.05-0.95": "5th to 95th percentile range"},
}
CITATIONS = [  # required by the dataset's licence terms (Rutgers-ESSP/IPCC-AR6-Sea-Level-Projections, LICENSE.md)
    "Fox-Kemper, B., H.T. Hewitt, C. Xiao, G. Aðalgeirsdóttir, S.S. Drijfhout, T.L. Edwards, N.R. Golledge, M. Hemer, "
    "R.E. Kopp, G. Krinner, A. Mix, D. Notz, S. Nowicki, I.S. Nurhati, L. Ruiz, J.-B. Sallée, A.B.A. Slangen, and Y. Yu, "
    "2021: Ocean, Cryosphere and Sea Level Change. In Climate Change 2021: The Physical Science Basis. Contribution of "
    "Working Group I to the Sixth Assessment Report of the Intergovernmental Panel on Climate Change [Masson-Delmotte, V., "
    "P. Zhai, A. Pirani, S.L. Connors, C. Péan, S. Berger, N. Caud, Y. Chen, L. Goldfarb, M.I. Gomis, M. Huang, "
    "K. Leitzell, E. Lonnoy, J.B.R. Matthews, T.K. Maycock, T. Waterfield, O. Yelekçi, R. Yu, and B. Zhou (eds.)]. "
    "Cambridge University Press, Cambridge, United Kingdom and New York, NY, USA, pp. 1211–1362, "
    "doi:10.1017/9781009157896.011.",
    "Kopp, R. E., Garner, G. G., Hermans, T. H. J., Jha, S., Kumar, P., Reedy, A., Slangen, A. B. A., Turilli, M., "
    "Edwards, T. L., Gregory, J. M., Koubbe, G., Levermann, A., Merzky, A., Nowicki, S., Palmer, M. D., & Smith, C. (2023). "
    "The Framework for Assessing Changes To Sea-Level (FACTS) v1.0: A platform for characterizing parametric and "
    "structural uncertainty in future global, relative, and extreme sea-level change. Geoscientific Model Development, "
    "16, 7461–7489. https://doi.org/10.5194/gmd-16-7461-2023",
    "Garner, G. G., T. Hermans, R. E. Kopp, A. B. A. Slangen, T. L. Edwards, A. Levermann, S. Nowikci, M. D. Palmer, "
    "C. Smith, B. Fox-Kemper, H. T. Hewitt, C. Xiao, G. Aðalgeirsdóttir, S. S. Drijfhout, T. L. Edwards, N. R. Golledge, "
    "M. Hemer, G. Krinner, A. Mix, D. Notz, S. Nowicki, I. S. Nurhati, L. Ruiz, J-B. Sallée, Y. Yu, L. Hua, T. Palmer, "
    "B. Pearson, 2021. IPCC AR6 Sea Level Projections. Version 20210809. Dataset accessed {accessed} at "
    "https://doi.org/10.5281/zenodo.5914709.",
]
ACKNOWLEDGEMENT = ("We thank the projection authors for developing and making the sea-level rise projections available, "
                   "multiple funding agencies for supporting the development of the projections, and the NASA Sea Level "
                   "Change Team for developing and hosting the IPCC AR6 Sea Level Projection Tool.")
TERMS_URL = "https://github.com/Rutgers-ESSP/IPCC-AR6-Sea-Level-Projections/blob/main/LICENSE.md"


# ---- network, cached ----

def cached(name: str, fetch) -> bytes:
    p = CACHE / name
    if not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(fetch())
    return p.read_bytes()


def get(url: str, **kw) -> bytes:
    r = httpx.get(url, timeout=httpx.Timeout(120, connect=10), follow_redirects=True, **kw)
    r.raise_for_status()
    return r.content


def get_range(start: int, end: int, tries: int = 5) -> bytes:
    """Bytes start..end (inclusive) of the zip; fails unless Zenodo answers 206 with exactly that range.
    A dropped connection resumes from the last byte received, up to `tries` requests in all."""
    out = bytearray()
    for attempt in range(tries):
        a = start + len(out)
        try:
            with httpx.stream("GET", ZIP_URL, headers={"Range": f"bytes={a}-{end}"}, follow_redirects=True,
                              timeout=httpx.Timeout(120, connect=10)) as r:
                if r.status_code != 206 or not r.headers.get("content-range", "").startswith(f"bytes {a}-{end}/"):
                    raise ValueError(f"range {a}-{end}: HTTP {r.status_code} {r.headers.get('content-range')}")
                for chunk in r.iter_bytes(1 << 20):
                    out += chunk
            break
        except (httpx.TransportError, httpx.RemoteProtocolError) as e:
            if attempt == tries - 1:
                raise
            print(f"  connection dropped at {len(out) / 1e6:.0f} MB ({type(e).__name__}); resuming", flush=True)
            time.sleep(5 * (attempt + 1))
    if len(out) != end - start + 1:
        raise ValueError(f"range {start}-{end}: got {len(out)} bytes")
    return bytes(out)


# ---- zip ----

def central_directory(tail: bytes, tail_start: int) -> dict[str, dict]:
    """The zip64 central directory in the zip's last bytes -> {name: {offset, csize, size, crc, method}}."""
    j = tail.rfind(b"PK\x06\x06")
    if j < 0:
        raise ValueError("no zip64 end of central directory in the tail")
    n, cdo = struct.unpack("<Q", tail[j + 32:j + 40])[0], struct.unpack("<Q", tail[j + 48:j + 56])[0]
    p, out = cdo - tail_start, {}
    if p < 0:
        raise ValueError("the central directory starts before the fetched tail")
    for _ in range(n):
        sig, meth, crc, csz, usz, fl, xl, cl, lho = struct.unpack("<I6xH4xIIIHHH8xI", tail[p:p + 46])
        if sig != 0x02014B50:
            raise ValueError("bad central directory entry")
        name = tail[p + 46:p + 46 + fl].decode()
        ex, q = tail[p + 46 + fl:p + 46 + fl + xl], 0
        while q < len(ex):  # zip64 extra field: the 64-bit values, in this order, for each 32-bit field that is 0xFFFFFFFF
            hid, hl = struct.unpack("<HH", ex[q:q + 4])
            if hid == 1:
                vals = iter(struct.unpack(f"<{hl // 8}Q", ex[q + 4:q + 4 + hl // 8 * 8]))
                usz = next(vals) if usz == 0xFFFFFFFF else usz
                csz = next(vals) if csz == 0xFFFFFFFF else csz
                lho = next(vals) if lho == 0xFFFFFFFF else lho
            q += 4 + hl
        out[name] = {"offset": lho, "csize": csz, "size": usz, "crc": crc, "method": meth}
        p += 46 + fl + xl + cl
    return out


def fetch_entry(e: dict) -> bytes:
    """One deflated zip entry -> its uncompressed bytes, checked against the central directory's size and CRC-32."""
    if e["method"] != 8:
        raise ValueError(f"entry is not deflated (method {e['method']})")
    head = get_range(e["offset"], e["offset"] + 29)
    sig, nl, xl = struct.unpack("<I22xHH", head)
    if sig != 0x04034B50:
        raise ValueError("bad local header")
    start = e["offset"] + 30 + nl + xl
    data = zlib.decompress(get_range(start, start + e["csize"] - 1), -15)
    if len(data) != e["size"] or zlib.crc32(data) != e["crc"]:
        raise ValueError("entry size or CRC-32 differs from the central directory")
    return data


# ---- HDF5 (netCDF4), only what these files use ----

def _u(d, o: int, n: int) -> int:
    return int.from_bytes(d[o:o + n], "little")


def _messages(d: bytes, addr: int):
    """(type, body) of every message in a version-2 object header, following continuation blocks."""
    if d[addr:addr + 5] != b"OHDR\x02":
        raise ValueError("not a version-2 object header")
    fl = d[addr + 5]
    o = addr + 6 + (16 if fl & 0x20 else 0) + (4 if fl & 0x10 else 0)
    sz = 1 << (fl & 3)
    blocks = [(o + sz, o + sz + _u(d, o, sz))]  # (start, end) of message bytes; checksums lie outside
    while blocks:
        o, end = blocks.pop(0)
        while o + 4 <= end:  # fewer bytes left than a message header: a gap
            t, n = d[o], _u(d, o + 1, 2)
            o += 4 + (2 if fl & 4 else 0)
            body, o = d[o:o + n], o + n
            if t == 0x10:  # continuation: "OCHK", messages, 4-byte checksum
                a, n = _u(body, 0, 8), _u(body, 8, 8)
                if d[a:a + 4] != b"OCHK":
                    raise ValueError("bad object header continuation")
                blocks.append((a + 4, a + n - 4))
            else:
                yield t, body


def _links(d: bytes, addr: int) -> dict[str, int]:
    """A group's compact hard links -> {name: object header address}."""
    out = {}
    for t, b in _messages(d, addr):
        if t == 0x02 and b[2 + (8 if b[1] & 1 else 0):][:8] != b"\xff" * 8:
            raise ValueError("dense link storage is not supported")
        if t == 0x11:
            raise ValueError("old-style group symbol tables are not supported")
        if t == 0x06:
            fl, o = b[1], 2
            if fl & 8:
                if b[o] != 0:
                    raise ValueError("only hard links are supported")
                o += 1
            o += (8 if fl & 4 else 0) + (1 if fl & 16 else 0)
            ls = 1 << (fl & 3)
            n = _u(b, o, ls)
            out[b[o + ls:o + ls + n].decode()] = _u(b, o + ls + n, 8)
    return out


def _dataset(d: bytes, addr: int) -> dict:
    """A dataset's shape, dtype, layout and filters from its object header."""
    info = {"filters": []}
    for t, b in _messages(d, addr):
        if t == 0x01:  # dataspace
            o = 8 if b[0] == 1 else 4
            info["shape"] = tuple(_u(b, o + 8 * i, 8) for i in range(b[1]))
        elif t == 0x03:  # datatype: fixed-point or IEEE float, little-endian
            cls, bits, size = b[0] & 15, b[1], _u(b, 4, 4)
            if cls not in (0, 1) or bits & 1:
                raise ValueError(f"unsupported datatype class {cls}")
            info["dtype"] = np.dtype(f"<{'f' if cls else 'i' if bits & 8 else 'u'}{size}")
        elif t == 0x08:  # data layout, version 3
            if b[0] != 3 or b[1] not in (1, 2):
                raise ValueError(f"unsupported layout {b[0]}/{b[1]}")
            info["layout"] = b[1]
            if b[1] == 1:
                info["addr"] = _u(b, 2, 8)
            else:
                info["btree"], info["chunk"] = _u(b, 3, 8), tuple(_u(b, 11 + 4 * i, 4) for i in range(b[2]))
        elif t == 0x0B:  # filter pipeline
            v, o = b[0], 8 if b[0] == 1 else 2
            for _ in range(b[1]):
                fid = _u(b, o, 2)
                if v == 1 or fid >= 256:
                    nlen, nc = _u(b, o + 2, 2), _u(b, o + 6, 2)
                    o += 8 + ((nlen + 7) // 8 * 8 if v == 1 else nlen)
                else:
                    nc = _u(b, o + 4, 2)
                    o += 6
                o += 4 * nc + (4 if v == 1 and nc % 2 else 0)
                info["filters"].append(fid)
    return info


def _chunks(d: bytes, addr: int, ndim: int):
    """(offsets, address, size, filter mask) of every chunk under a version-1 B-tree node."""
    if d[addr:addr + 5] != b"TREE\x01":
        raise ValueError("not a chunk B-tree node")
    level, used, o = d[addr + 5], _u(d, addr + 6, 2), addr + 24
    for _ in range(used):
        size, mask = _u(d, o, 4), _u(d, o + 4, 4)
        offs = tuple(_u(d, o + 8 + 8 * i, 8) for i in range(ndim))
        child = _u(d, o + 8 + 8 * (ndim + 1), 8)
        o += 16 + 8 * (ndim + 1)
        if level:
            yield from _chunks(d, child, ndim)
        else:
            yield offs, child, size, mask


def _read_1d(d: bytes, info: dict) -> np.ndarray:
    if info["layout"] != 1 or len(info["shape"]) != 1 or info["filters"]:
        raise ValueError("expected a contiguous 1-D coordinate")
    return np.frombuffer(d, info["dtype"], info["shape"][0], info["addr"]).copy()


def _read_selected(d: bytes, info: dict, qi: list[int], yi: list[int]) -> np.ndarray:
    """The chunked 3-D variable (quantiles, years, locations) at quantile indices qi and year indices yi."""
    shape, dt = info["shape"], info["dtype"]
    if info["layout"] != 2 or len(shape) != 3 or info["filters"] not in ([2, 1], [1]) or info["chunk"][-1] != dt.itemsize:
        raise ValueError(f"unexpected layout {info}")
    cq, cy, cl = info["chunk"][:3]
    out = np.full((len(qi), len(yi), shape[2]), FILL, dt)
    seen = np.zeros(out.shape, np.int8)
    for (q0, y0, l0), addr, size, mask in _chunks(d, info["btree"], 3):
        qs = [(k, q - q0) for k, q in enumerate(qi) if q0 <= q < q0 + cq]
        ys = [(k, y - y0) for k, y in enumerate(yi) if y0 <= y < y0 + cy]
        if not qs or not ys:
            continue
        if mask:
            raise ValueError("a chunk skipped a filter")
        raw = zlib.decompress(d[addr:addr + size])
        if len(raw) != cq * cy * cl * dt.itemsize:
            raise ValueError("chunk size differs from the layout")
        if 2 in info["filters"]:  # undo the shuffle filter: all first bytes, then all second bytes
            raw = np.frombuffer(raw, np.uint8).reshape(dt.itemsize, -1).T.tobytes()
        c = np.frombuffer(raw, dt).reshape(cq, cy, cl)
        n = min(cl, shape[2] - l0)
        for k, a in qs:
            for m, b in ys:
                out[k, m, l0:l0 + n] = c[a, b, :n]
                seen[k, m, l0:l0 + n] += 1
    if not (seen == 1).all():
        raise ValueError("the chunks do not cover the selection exactly once")
    return out


def read_nc(nc: bytes) -> dict:
    """An AR6 confidence-output file -> its coordinates and the data variable at Q and YEARS (raw int16)."""
    if nc[:8] != b"\x89HDF\r\n\x1a\n" or nc[8] != 0:
        raise ValueError("not an HDF5 file with a version-0 superblock")
    ds = {k: _dataset(nc, a) for k, a in _links(nc, _u(nc, 64, 8)).items()}
    var = [k for k in ds if k in ("sea_level_change", "sea_level_change_rate")]
    if len(var) != 1:
        raise ValueError(f"expected one data variable, found {sorted(ds)}")
    co = {k: _read_1d(nc, ds[k]) for k in ("quantiles", "years", "locations", "lat", "lon")}
    qi = [int(np.flatnonzero(np.isclose(co["quantiles"], q, rtol=0, atol=1e-9))[0]) for q in Q]
    yi = [int(np.flatnonzero(co["years"] == y)[0]) for y in YEARS]
    if ds[var[0]]["shape"] != (len(co["quantiles"]), len(co["years"]), len(co["locations"])):
        raise ValueError("the data variable's shape is not (quantiles, years, locations)")
    return {**co, "variable": var[0], "qi": qi, "data": _read_selected(nc, ds[var[0]], qi, yi)}


# ---- the 51 entries ----

def entry_name(comp: str, scen: str, conf: str, kind: str) -> str:
    return f"{PREFIX}{conf}_confidence/{scen}/{comp}_{scen}_{conf}_confidence_{kind}.nc"


def needed() -> list[str]:
    names = []
    for scen, conf in SCENARIOS:
        names += [entry_name(c, scen, conf, "values") for c in COMPONENTS if c != "verticallandmotion"]
        names.append(entry_name("total", scen, conf, "rates"))
    names += [entry_name("verticallandmotion", VLM_FROM[c], c, "values") for c in ("medium", "low")]
    return names


def load_entry(name: str, cd: dict, ids: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> dict:
    """One entry's data at Q and YEARS for every location, from the cache or fetched (then checked and cached)."""
    p = CACHE / (Path(name).stem + ".npz")
    if not p.exists():
        t = time.monotonic()
        nc = fetch_entry(cd[name])
        r = read_nc(nc)
        if not (np.array_equal(r["locations"], ids) and np.abs(r["lat"] - lat).max() < 0.006
                and np.abs(r["lon"] - lon).max() < 0.006):
            raise ValueError(f"{name}: its locations differ from location_list.lst")
        want = "sea_level_change_rate" if name.endswith("_rates.nc") else "sea_level_change"
        if r["variable"] != want:
            raise ValueError(f"{name}: holds {r['variable']}, expected {want}")
        np.savez_compressed(p, data=r["data"], md5=hashlib.md5(nc).hexdigest(), qi=r["qi"])
        print(f"  fetched {Path(name).name}: {cd[name]['csize'] / 1e6:.0f} MB in {time.monotonic() - t:.0f} s", flush=True)
    with np.load(p) as z:
        return {"data": z["data"], "md5": str(z["md5"]), "qi": z["qi"].tolist()}


# ---- mapping ----

def km_to(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Haversine distance (km) from one point to many; same formula as earthtrends.data.coops.haversine_km."""
    p1, p2 = np.radians(lat), np.radians(lats)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lons - lon) / 2) ** 2
    return 12742 * np.arcsin(np.sqrt(a))


def tokens(name: str) -> set[str]:
    return {w for w in re.sub(r"[^A-Z]+", " ", name.upper()).split() if len(w) >= 3 and w not in GENERIC}


def match(st: dict, gauges: dict, cells: dict) -> dict:
    """One CO-OPS station -> its mapping row. gauges: ids, names (every name known for each), lat, lon;
    cells: ids, lat, lon of the valid AR6 grid cells."""
    row = {"coops_id": st["id"], "coops_name": st["name"], "coops_lat": st["lat"], "coops_lon": st["lng"]}
    if st.get("greatlakes"):
        return {**row, "ar6_id": "", "psmsl_id": "", "psmsl_name": "", "km": "", "rule": "none",
                "reason": "Great Lakes: lake levels are not sea level, and AR6 projects no sea level there"}
    km = km_to(st["lat"], st["lng"], gauges["lat"], gauges["lon"])
    order = np.argsort(km, kind="stable")
    hit, rule, reason = None, "", ""
    if st["id"] in OVERRIDES:
        gid, reason = OVERRIDES[st["id"]]
        hit, rule = int(np.flatnonzero(gauges["ids"] == gid)[0]), "override"
    elif km[order[0]] <= NEAR_KM:
        hit, rule = int(order[0]), "within_3km"
    else:
        mine = tokens(st["name"])
        for i in order:
            if km[i] > NAME_KM:
                break
            if common := mine & set().union(*map(tokens, gauges["names"][i])):
                hit, rule, reason = int(i), "within_15km_name", f"name shares {', '.join(sorted(common))}"
                break
    if hit is not None:
        gid = int(gauges["ids"][hit])
        return {**row, "ar6_id": gid, "psmsl_id": gid, "psmsl_name": gauges["names"][hit][0],
                "km": round(float(km[hit]), 1), "rule": rule, "reason": reason}
    ck = km_to(st["lat"], st["lng"], cells["lat"], cells["lon"])
    c = int(np.argmin(ck))
    g = int(order[0])
    return {**row, "ar6_id": int(cells["ids"][c]), "psmsl_id": "", "psmsl_name": "", "km": round(float(ck[c]), 1),
            "rule": "regional_estimate",
            "reason": f"AR6 1-degree cell at {cells['lat'][c]:.0f}, {cells['lon'][c]:.0f}; nearest AR6 gauge "
                      f"{gauges['names'][g][0]} (PSMSL {int(gauges['ids'][g])}) is {km[g]:.1f} km away"}


def coops_stations() -> list[dict]:
    def fetch():
        from earthtrends.data import coops
        keep = ("id", "name", "lat", "lng", "greatlakes", "state")
        return json.dumps([{k: s.get(k) for k in keep} for s in coops.stations()], indent=0).encode()
    return [{**s, "lat": float(s["lat"]), "lng": float(s["lng"])} for s in json.loads(cached("coops_stations.json", fetch))]


def psmsl_names() -> dict[int, str]:
    from earthtrends.data import psmsl
    return {s["id"]: s["name"] for s in psmsl.parse_stations(cached("psmsl_filelist.txt", lambda: get(PSMSL_LIST)).decode())}


# ---- build ----

def build() -> None:
    accessed = cached("accessed.txt", lambda: date.today().isoformat().encode()).decode()  # the day the cache was filled
    record = json.loads(cached("record.json", lambda: get(API)))
    files = {f["key"]: f for f in record["files"]}
    if record["metadata"]["version"] != VERSION or record["doi"] != f"10.5281/zenodo.{RECORD}":
        raise ValueError(f"Zenodo record is {record['doi']} version {record['metadata']['version']}")
    size = files[ZIP]["size"]
    cd = central_directory(cached("zip_tail.bin", lambda: get_range(size - 65536, size - 1)), size - 65536)

    lst = cached("location_list.lst", lambda: get(LIST_URL))
    if "md5:" + hashlib.md5(lst).hexdigest() != files["location_list.lst"]["checksum"]:
        raise ValueError("location_list.lst md5 differs from Zenodo's")
    rows = [line.split("\t") for line in lst.decode().splitlines() if line.strip()]
    ar6_names = np.array([r[0] for r in rows])
    ids = np.array([int(r[1]) for r in rows])
    lat, lon = np.array([float(r[2]) for r in rows], np.float32), np.array([float(r[3]) for r in rows], np.float32)

    names = needed()
    missing = [n for n in names if n not in cd]
    if missing or len(names) != 51:
        raise ValueError(f"{len(names)} entries, not in the zip: {missing}")
    print(f"{len(names)} entries, {sum(cd[n]['csize'] for n in names) / 1e9:.2f} GB compressed", flush=True)

    # pass 1: fetch and cache every entry; a location is valid where no entry has a missing value
    valid, md5 = np.ones(len(ids), bool), {}
    for n in names:
        e = load_entry(n, cd, ids, lat, lon)
        if e["qi"] != [7, 19, 53, 87, 99]:
            print(f"  note: {Path(n).name} keeps quantile indices {e['qi']}")
        valid &= (e["data"] != FILL).all(axis=(0, 1))
        md5[n] = e["md5"]
    gauge = ids < GRID
    dropped = ids[gauge & ~valid].tolist()
    print(f"AR6 gauges {int(gauge.sum())}, kept {int((gauge & valid).sum())}, dropped (missing values) {dropped}")

    # mapping
    pn = psmsl_names()
    gi = np.flatnonzero(gauge & valid)
    gauges = {"ids": ids[gi], "lat": lat[gi].astype(float), "lon": lon[gi].astype(float),
              "names": [[pn.get(int(i), ar6_names[k].replace("_", " ").title()), ar6_names[k]] for k, i in zip(gi, ids[gi])]}
    ci = np.flatnonzero(~gauge & valid)
    cells = {"ids": ids[ci], "lat": lat[ci].astype(float), "lon": lon[ci].astype(float)}
    stations = coops_stations()
    mapping = [match(s, gauges, cells) for s in stations]
    extra = sorted({r["ar6_id"] for r in mapping if r["rule"] == "regional_estimate"})

    # pass 2: assemble the kept gauges plus the grid cells the mapping uses
    keep = np.concatenate([gi, np.flatnonzero(np.isin(ids, extra))])
    sc = {f"{s}{'_low' if c == 'low' else ''}": k for k, (s, c) in enumerate(SCENARIOS)}
    levels = np.full((len(keep), len(COMPONENTS), len(SCENARIOS), len(Q), len(YEARS)), FILL, np.int16)
    rates = np.full((len(keep), len(SCENARIOS), len(Q), len(YEARS)), FILL, np.int16)
    vlm = {c: load_entry(entry_name("verticallandmotion", VLM_FROM[c], c, "values"), cd, ids, lat, lon)["data"][:, :, keep]
           for c in ("medium", "low")}
    for k, (s, c) in enumerate(SCENARIOS):
        for j, comp in enumerate(COMPONENTS):
            levels[:, j, k] = vlm[c].transpose(2, 0, 1) if comp == "verticallandmotion" else \
                load_entry(entry_name(comp, s, c, "values"), cd, ids, lat, lon)["data"][:, :, keep].transpose(2, 0, 1)
        rates[:, k] = load_entry(entry_name("total", s, c, "rates"), cd, ids, lat, lon)["data"][:, :, keep].transpose(2, 0, 1)

    # self-checks: the build fails unless every one holds
    kept_ids = set(ids[keep].tolist())
    g12 = int(np.flatnonzero(ids[keep] == CHECK_ID)[0])
    got = levels[g12, 0, sc[CHECK_SCEN], :, YEARS.index(CHECK_YEAR)].tolist()
    rate = int(rates[g12, sc[CHECK_SCEN], 2, YEARS.index(CHECK_YEAR)])
    checks = {
        f"PSMSL {CHECK_ID} {CHECK_SCEN} {CHECK_YEAR} total {got} mm == {CHECK_TOTAL_MM}": got == CHECK_TOTAL_MM,
        f"PSMSL {CHECK_ID} {CHECK_SCEN} {CHECK_YEAR} rate median {rate / 10} mm/yr == {CHECK_RATE_TENTHS / 10}":
            rate == CHECK_RATE_TENTHS,
        "no missing value in any kept location": not (levels == FILL).any() and not (rates == FILL).any(),
        "every quantile set is non-decreasing (levels and rates)":
            bool((np.diff(levels, axis=3) >= 0).all() and (np.diff(rates, axis=2) >= 0).all()),
        f"VLM equal across scenarios (medium {VLM_FROM['medium']} file == low {VLM_FROM['low']} file)":
            np.array_equal(vlm["medium"], vlm["low"]),
        "every mapped AR6 location is in the file": all(r["ar6_id"] in kept_ids for r in mapping if r["ar6_id"] != ""),
    }
    for text, ok in checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    if not all(checks.values()):
        raise SystemExit("self-check failed: nothing written")

    npz = OUT / "ar6_gauges.npz"
    write_npz(npz, ids=ids[keep].astype(np.int64), names=ar6_names[keep], lat=lat[keep], lon=lon[keep],
              years=np.array(YEARS, np.int16), quantiles=np.array(Q), scenarios=np.array(list(sc)),
              components=np.array(COMPONENTS), levels=levels, rates=rates)
    manifest = {
        "dataset": "IPCC AR6 Sea Level Projections: regional relative sea-level projections, confidence output "
                   f"({ZIP}), tide-gauge locations",
        "doi": record["doi"], "concept_doi": record["conceptdoi"], "version": VERSION,
        "record_url": f"https://zenodo.org/records/{RECORD}", "licence": "CC-BY-4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/", "terms_url": TERMS_URL, "accessed": accessed,
        "baseline": "1995-2014 mean", "baseline_years": [1995, 2014],
        "units": {"levels": "mm", "rates": "mm per year"},
        "scaling": {"levels": 1, "rates": 0.1, "note": "stored int16 = value / scale, AR6's own storage; fill -32768"},
        "quantiles": list(Q), "source_quantile_indices": [7, 19, 53, 87, 99], "years": list(YEARS),
        "scenarios": {k: {"ssp": s, "label": f"SSP{s[3]}-{s[4]}.{s[5]}", "confidence": c} for k, (s, c) in zip(sc, SCENARIOS)},
        "range_names": RANGE_NAMES,
        "components": {"total": "total", "oceandynamics": "sterodynamic (ocean dynamics and thermal expansion)",
                       "GIS": "Greenland ice sheet", "AIS": "Antarctic ice sheet", "glaciers": "glaciers",
                       "landwaterstorage": "land water storage", "verticallandmotion": "vertical land motion"},
        "arrays": {"levels": "[location, component, scenario, quantile, year]", "rates": "[location, scenario, quantile, year]"},
        "locations": {"gauges": int(len(gi)), "grid_cells": len(extra),
                      "note": "IDs below 1e9 are PSMSL gauge IDs; from 1e9 up, AR6 1-degree cells used by a "
                              "regional-estimate row of coops_to_psmsl.csv",
                      "dropped_gauges": dropped, "dropped_reason": "AR6 has missing values there"},
        "vertical_land_motion_from": {c: Path(entry_name("verticallandmotion", VLM_FROM[c], c, "values")).name
                                      for c in VLM_FROM},
        "notes": [
            "Rates are AR6's own rates of the total (its *_rates.nc files), centred on each decade; they are not "
            "differences of the levels, which AR6 draws from other p-boxes before 2100.",
            "AR6 levels switch p-boxes after 2100, so 2100 to 2110 can jump (AR6 FAQ).",
            "Quantiles of the parts do not add up to the quantiles of the total.",
            "Low-confidence scenarios include ice-sheet processes AR6 can't give a likelihood for; their ranges are "
            "named by percentiles.",
        ],
        "sources": {"zip": {"name": ZIP, "bytes": size, "md5": files[ZIP]["checksum"].removeprefix("md5:"),
                            "note": "md5 as Zenodo lists it; only the entries below were fetched, each checked by CRC-32"},
                    "location_list.lst": {"md5": hashlib.md5(lst).hexdigest()},
                    "entries": [{"name": n.removeprefix(PREFIX), "bytes": cd[n]["size"], "crc32": f"{cd[n]['crc']:08x}",
                                 "md5": md5[n]} for n in names],
                    "gauge_names": PSMSL_LIST},
        "citations": [c.format(accessed=accessed) for c in CITATIONS],
        "acknowledgement": ACKNOWLEDGEMENT,
    }
    (OUT / "ar6_gauges.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    cols = ["coops_id", "coops_name", "coops_lat", "coops_lon", "psmsl_id", "psmsl_name", "ar6_id", "km", "rule", "reason"]
    with open(OUT / "coops_to_psmsl.csv", "w", newline="") as f:
        w = csv.DictWriter(f, cols, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(mapping, key=lambda r: r["coops_id"]))
    count = {r: sum(m["rule"] == r for m in mapping) for r in
             ("within_3km", "within_15km_name", "override", "regional_estimate", "none")}
    print(f"mapping: {len(mapping)} CO-OPS stations {count}")
    print(f"wrote {npz} ({npz.stat().st_size / 1e6:.2f} MB), {len(keep)} locations; manifest; mapping")


if __name__ == "__main__":
    build()
