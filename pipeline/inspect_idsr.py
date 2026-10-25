"""Inspect the IDSR Weekly data set in the DHIS2 demo before writing the real loader.
Prints: data elements in the data set, district org units, a sample of weekly case
data, and a sample of reporting-rate data. Errors are printed, not hidden.
Run from the pipeline folder:  python inspect_idsr.py | Tee-Object idsr_output.txt
"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()
BASE = os.environ["DHIS2_URL"].rstrip("/")
AUTH = (os.environ["DHIS2_USER"], os.environ["DHIS2_PASSWORD"])
DS = "Nyh6laLdBEJ"  # IDSR Weekly


def get(path, **params):
    r = requests.get(f"{BASE}/api/{path}", params=params, auth=AUTH, timeout=120)
    r.raise_for_status()
    return r.json()


def attempt(title, fn):
    print(f"\n== {title} ==")
    try:
        fn()
    except requests.HTTPError as e:
        print("HTTP error:", e)
        print(e.response.text[:500])
    except Exception as e:
        print("Error:", repr(e))


def elements():
    ds = get(f"dataSets/{DS}", fields="name,periodType,dataSetElements[dataElement[id,name]]")
    print(ds["name"], "|", ds["periodType"])
    for x in ds["dataSetElements"]:
        print(" ", x["dataElement"]["id"], x["dataElement"]["name"])


def districts():
    ous = get("organisationUnits", fields="id,name", filter="level:eq:2", paging="false")["organisationUnits"]
    print(len(ous), "districts")
    for ou in sorted(ous, key=lambda o: o["name"]):
        print(" ", ou["id"], ou["name"])


def show(data):
    print("headers:", [h["name"] for h in data["headers"]])
    rows = data["rows"]
    print("rows:", len(rows))
    print("first rows:", rows[:5])
    pi = [h["name"] for h in data["headers"]].index("pe")
    periods = sorted({r[pi] for r in rows})
    print("periods:", periods[:3], "...", periods[-3:], f"({len(periods)} total)")


def cases():
    show(get("analytics", dimension=["dx:vq2qO3eTrNi", "pe:LAST_12_WEEKS", "ou:LEVEL-2"], skipMeta="true"))


def reporting():
    show(get("analytics", dimension=[f"dx:{DS}.ACTUAL_REPORTS;{DS}.EXPECTED_REPORTS",
                                     "pe:LAST_12_WEEKS", "ou:LEVEL-2"], skipMeta="true"))


attempt("IDSR Weekly data elements", elements)
attempt("District org units (level 2)", districts)
attempt("Sample: IDSR Malaria, last 12 weeks, by district", cases)
attempt("Sample: reporting rates, last 12 weeks, by district", reporting)
