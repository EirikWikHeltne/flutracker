"""Download ERVISS weekly data and keep the Nordic influenza rows."""

import io
import time
import urllib.request

import pandas as pd

from .config import COUNTRIES, ERVISS_BASE, ERVISS_FILES

NORDIC = [c["erviss"] for c in COUNTRIES.values()]


def _download(url, retries=4):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return resp.read()
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def fetch_erviss(base=ERVISS_BASE):
    """Return one long DataFrame with a `file` column naming the source file."""
    frames = []
    for name in ERVISS_FILES:
        raw = _download(f"{base}/{name}.csv")
        df = pd.read_csv(io.BytesIO(raw))
        df = df[df["countryname"].isin(NORDIC)]
        if "pathogen" in df.columns:
            df = df[df["pathogen"] == "Influenza"]
        df.insert(0, "file", name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
