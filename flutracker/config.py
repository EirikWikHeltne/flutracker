"""Sources, countries and indicators tracked by the flu tracker."""

# ECDC ERVISS publishes the weekly surveillance data that each national
# health authority reports to ECDC (FHI, Folkhälsomyndigheten, SSI).
ERVISS_BASE = "https://raw.githubusercontent.com/EU-ECDC/Respiratory_viruses_weekly_data/main/data"
ERVISS_FILES = [
    "nonSentinelTestsDetections",
    "sentinelTestsDetectionsPositivity",
    "ILIARIRates",
    "nonSentinelSeverity",
    "activityFluTypeSubtype",
]

COUNTRIES = {
    "NO": {
        "erviss": "Norway",
        "name": "Norge",
        "authority": "Folkehelseinstituttet (FHI)",
        "url": "https://www.fhi.no/sy/influensa/influensaovervaking/",
    },
    "SE": {
        "erviss": "Sweden",
        "name": "Sverige",
        "authority": "Folkhälsomyndigheten",
        "url": "https://www.folkhalsomyndigheten.se/folkhalsorapportering-statistik/statistik-a-o/sjukdomsstatistik/influensa/",
    },
    "DK": {
        "erviss": "Denmark",
        "name": "Danmark",
        "authority": "Statens Serum Institut (SSI)",
        "url": "https://www.ssi.dk/sygdomme-beredskab-og-forskning/sygdomsovervaagning/i/influenzasaesonen---opgoerelse-over-sygdomsforekomst",
    },
}

# kind: "count" values are summed for season-to-date, "rate" values are not.
INDICATORS = {
    "lab_cases": {
        "label": "Laboratoriebekreftede tilfeller",
        "short": "Lab.bekreftet",
        "unit": "tilfeller",
        "kind": "count",
        "decimals": 0,
        "description": "Laboratoriebekreftede influensatilfeller (alle prøver utenfor sentinel), per uke.",
    },
    "lab_positivity": {
        "label": "Andel positive prøver",
        "short": "Positivitet",
        "unit": "%",
        "kind": "rate",
        "decimals": 1,
        "description": "Andel av alle influensaprøver som er positive (lab.bekreftede / testede).",
    },
    "sentinel_positivity": {
        "label": "Sentinel-positivitet",
        "short": "Sentinel",
        "unit": "%",
        "kind": "rate",
        "decimals": 1,
        "description": "Andel positive prøver fra sentinel-leger i primærhelsetjenesten. ECDC bruker 10 % som epidemisk terskel.",
    },
    "ili_rate": {
        "label": "Influensalignende sykdom (ILI)",
        "short": "ILI",
        "unit": "per 100 000",
        "kind": "rate",
        "decimals": 1,
        "description": "Legekonsultasjoner for influensalignende sykdom per 100 000 innbyggere.",
    },
    "icu": {
        "label": "Intensivinnleggelser",
        "short": "Intensiv",
        "unit": "innleggelser",
        "kind": "count",
        "decimals": 0,
        "description": "Nye intensivinnleggelser med influensa per uke.",
    },
    "deaths": {
        "label": "Dødsfall",
        "short": "Dødsfall",
        "unit": "dødsfall",
        "kind": "count",
        "decimals": 0,
        "description": "Dødsfall med bekreftet influensa per uke.",
    },
}

SUBTYPES = ["A(H1)pdm09", "A(H3)", "A (unknown)", "B/Vic", "B (unknown)"]
SUBTYPE_LABELS = {
    "A(H1)pdm09": "A(H1N1)pdm09",
    "A(H3)": "A(H3N2)",
    "A (unknown)": "A (ikke subtypet)",
    "B/Vic": "B/Victoria",
    "B (unknown)": "B (ikke typet)",
}

SEASON_START_WEEK = 40
SENTINEL_EPIDEMIC_THRESHOLD = 10.0  # % positivity, ECDC convention
MIN_SENTINEL_TESTS = 20  # below this, sentinel positivity is flagged as uncertain

# Intensity relative to the mean historical season peak of the indicator.
INTENSITY_LEVELS = [
    (0.10, "Basisnivå"),
    (0.40, "Lav"),
    (0.70, "Moderat"),
    (1.00, "Høy"),
    (float("inf"), "Svært høy"),
]

DASHBOARD_URL = "https://eirikwikheltne.github.io/flutracker/"
