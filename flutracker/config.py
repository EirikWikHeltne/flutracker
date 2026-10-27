"""Sources, countries and indicators tracked by the flu tracker."""

# ECDC ERVISS (European Respiratory Virus Surveillance Summary) publishes the
# weekly surveillance data that each national public health institute reports
# to ECDC: FHI (Norway), Folkhälsomyndigheten (Sweden) and SSI (Denmark).
ERVISS_BASE = "https://raw.githubusercontent.com/EU-ECDC/Respiratory_viruses_weekly_data/main/data"
ERVISS_FILES = [
    "nonSentinelTestsDetections",
    "sentinelTestsDetectionsPositivity",
    "ILIARIRates",
    "SARIRates",
    "nonSentinelSeverity",
    "activityFluTypeSubtype",
]
PATHOGENS = ["Influenza", "SARS-CoV-2", "RSV"]

SOURCE = {
    "name": "ECDC – European Respiratory Virus Surveillance Summary (ERVISS)",
    "publisher": "European Centre for Disease Prevention and Control (ECDC), an EU agency",
    "url": "https://erviss.org/",
    "data": "https://github.com/EU-ECDC/Respiratory_viruses_weekly_data",
    "note": (
        "Figures are reported every week by the national public health institutes "
        "(FHI, Folkhälsomyndigheten and SSI) to ECDC, which publishes them openly every Friday. "
        "Recent weeks can be revised."
    ),
}

# Links checked against the authorities' own sites (October 2026).
COUNTRIES = {
    "NO": {
        "erviss": "Norway",
        "name": "Norway",
        "authority": "Norwegian Institute of Public Health (FHI)",
        "url": "https://www.fhi.no/tema/influensa/overvaakingssystemet",
        "data_url": "https://statistikk.fhi.no/",
    },
    "SE": {
        "erviss": "Sweden",
        "name": "Sweden",
        "authority": "Public Health Agency of Sweden (Folkhälsomyndigheten)",
        "url": "https://www.folkhalsomyndigheten.se/statistik-och-data/lagesrapporter/luftvagsvirus-lagesrapporter/aktuell-lagesrapport-om-luftvagsvirus/",
        "data_url": "https://www.folkhalsomyndigheten.se/statistik-och-data/hitta-statistik-och-data/influensa-statistik/",
    },
    "DK": {
        "erviss": "Denmark",
        "name": "Denmark",
        "authority": "Statens Serum Institut (SSI)",
        "url": "https://www.ssi.dk/sygdomme-beredskab-og-forskning/overvaagning-af-luftvejssygdomme",
        "data_url": "https://statistik.ssi.dk/sygdomsdata",
    },
}

GROUPS = ["Influenza", "COVID-19", "RSV", "Hospital & severity"]

# spec says where the series comes from:
#   ("lab", pathogen)            non-sentinel laboratory detections
#   ("lab_type", type)           non-sentinel detections of "Influenza A" or "Influenza B" (all subtypes)
#   ("lab_pos", pathogen)        detections / tests * 100
#   ("lab_type_pos", type)       type detections / all influenza tests * 100
#   ("sentinel_pos", pathogen)   sentinel GP positivity
#   ("ili",)                     ILI consultations per 100 000
#   ("sari",)                    SARI hospitalisations per 100 000
#   ("severity", pathogen, ind)  hospitaladmissions / ICUadmissions / deaths
# kind: "count" values are summed for season-to-date, "rate" values are not.
INDICATORS = {
    "flu_cases": {
        "group": "Influenza", "spec": ("lab", "Influenza"), "kind": "count", "decimals": 0,
        "label": "Lab-confirmed influenza cases", "short": "Flu cases", "unit": "cases",
        "description": "Laboratory-confirmed influenza cases per week (all non-sentinel testing).",
    },
    "flu_positivity": {
        "group": "Influenza", "spec": ("lab_pos", "Influenza"), "kind": "rate", "decimals": 1,
        "label": "Influenza test positivity", "short": "Flu positivity", "unit": "%",
        "description": "Share of all influenza tests that were positive.",
    },
    "flu_sentinel": {
        "group": "Influenza", "spec": ("sentinel_pos", "Influenza"), "kind": "rate", "decimals": 1,
        "label": "Influenza sentinel positivity (GPs)", "short": "Flu sentinel", "unit": "%",
        "description": "Share of positive samples from sentinel GPs. ECDC uses 10 % as the epidemic threshold.",
    },
    "flu_a_cases": {
        "group": "Influenza", "spec": ("lab_type", "Influenza A"), "kind": "count", "decimals": 0,
        "label": "Lab-confirmed influenza A cases", "short": "Flu A cases", "unit": "cases",
        "description": "Laboratory-confirmed influenza A cases per week, all subtypes (all non-sentinel testing).",
    },
    "flu_a_positivity": {
        "group": "Influenza", "spec": ("lab_type_pos", "Influenza A"), "kind": "rate", "decimals": 1,
        "label": "Influenza A test positivity", "short": "Flu A positivity", "unit": "%",
        "description": "Share of all influenza tests that were positive for influenza A.",
    },
    "flu_b_cases": {
        "group": "Influenza", "spec": ("lab_type", "Influenza B"), "kind": "count", "decimals": 0,
        "label": "Lab-confirmed influenza B cases", "short": "Flu B cases", "unit": "cases",
        "description": "Laboratory-confirmed influenza B cases per week, all lineages (all non-sentinel testing).",
    },
    "flu_b_positivity": {
        "group": "Influenza", "spec": ("lab_type_pos", "Influenza B"), "kind": "rate", "decimals": 1,
        "label": "Influenza B test positivity", "short": "Flu B positivity", "unit": "%",
        "description": "Share of all influenza tests that were positive for influenza B.",
    },
    "ili_rate": {
        "group": "Influenza", "spec": ("ili",), "kind": "rate", "decimals": 1,
        "label": "Influenza-like illness (ILI) consultations", "short": "ILI", "unit": "per 100,000",
        "description": "GP consultations for influenza-like illness per 100,000 population.",
    },
    "covid_cases": {
        "group": "COVID-19", "spec": ("lab", "SARS-CoV-2"), "kind": "count", "decimals": 0,
        "label": "Lab-confirmed COVID-19 cases", "short": "COVID cases", "unit": "cases",
        "description": "Laboratory-confirmed SARS-CoV-2 cases per week (all non-sentinel testing).",
    },
    "covid_positivity": {
        "group": "COVID-19", "spec": ("lab_pos", "SARS-CoV-2"), "kind": "rate", "decimals": 1,
        "label": "COVID-19 test positivity", "short": "COVID positivity", "unit": "%",
        "description": "Share of all SARS-CoV-2 tests that were positive.",
    },
    "covid_sentinel": {
        "group": "COVID-19", "spec": ("sentinel_pos", "SARS-CoV-2"), "kind": "rate", "decimals": 1,
        "label": "COVID-19 sentinel positivity (GPs)", "short": "COVID sentinel", "unit": "%",
        "description": "Share of sentinel GP samples positive for SARS-CoV-2.",
    },
    "rsv_cases": {
        "group": "RSV", "spec": ("lab", "RSV"), "kind": "count", "decimals": 0,
        "label": "Lab-confirmed RSV cases", "short": "RSV cases", "unit": "cases",
        "description": "Laboratory-confirmed respiratory syncytial virus (RSV) cases per week (all non-sentinel testing).",
    },
    "rsv_positivity": {
        "group": "RSV", "spec": ("lab_pos", "RSV"), "kind": "rate", "decimals": 1,
        "label": "RSV test positivity", "short": "RSV positivity", "unit": "%",
        "description": "Share of all RSV tests that were positive.",
    },
    "rsv_sentinel": {
        "group": "RSV", "spec": ("sentinel_pos", "RSV"), "kind": "rate", "decimals": 1,
        "label": "RSV sentinel positivity (GPs)", "short": "RSV sentinel", "unit": "%",
        "description": "Share of sentinel GP samples positive for RSV.",
    },
    "sari_rate": {
        "group": "Hospital & severity", "spec": ("sari",), "kind": "rate", "decimals": 1,
        "label": "Hospitalisations for severe respiratory infection (SARI)", "short": "SARI", "unit": "per 100,000",
        "description": "Hospital admissions with severe acute respiratory infection (flu-like symptoms) per 100,000.",
    },
    "flu_hospital": {
        "group": "Hospital & severity", "spec": ("severity", "Influenza", "hospitaladmissions"), "kind": "count", "decimals": 0,
        "label": "Hospital admissions with influenza", "short": "Flu hospital", "unit": "admissions",
        "description": "New hospital admissions with confirmed influenza per week.",
    },
    "flu_icu": {
        "group": "Hospital & severity", "spec": ("severity", "Influenza", "ICUadmissions"), "kind": "count", "decimals": 0,
        "label": "ICU admissions with influenza", "short": "Flu ICU", "unit": "admissions",
        "description": "New intensive care admissions with confirmed influenza per week.",
    },
    "flu_deaths": {
        "group": "Hospital & severity", "spec": ("severity", "Influenza", "deaths"), "kind": "count", "decimals": 0,
        "label": "Deaths with influenza", "short": "Flu deaths", "unit": "deaths",
        "description": "Deaths with confirmed influenza per week.",
    },
    "covid_hospital": {
        "group": "Hospital & severity", "spec": ("severity", "SARS-CoV-2", "hospitaladmissions"), "kind": "count", "decimals": 0,
        "label": "Hospital admissions with COVID-19", "short": "COVID hospital", "unit": "admissions",
        "description": "New hospital admissions with confirmed COVID-19 per week.",
    },
    "covid_icu": {
        "group": "Hospital & severity", "spec": ("severity", "SARS-CoV-2", "ICUadmissions"), "kind": "count", "decimals": 0,
        "label": "ICU admissions with COVID-19", "short": "COVID ICU", "unit": "admissions",
        "description": "New intensive care admissions with confirmed COVID-19 per week.",
    },
    "covid_deaths": {
        "group": "Hospital & severity", "spec": ("severity", "SARS-CoV-2", "deaths"), "kind": "count", "decimals": 0,
        "label": "Deaths with COVID-19", "short": "COVID deaths", "unit": "deaths",
        "description": "Deaths with confirmed COVID-19 per week.",
    },
}

SUBTYPES = ["A(H1)pdm09", "A(H3)", "A (unknown)", "B/Vic", "B (unknown)"]
SUBTYPE_LABELS = {
    "A(H1)pdm09": "A(H1N1)pdm09",
    "A(H3)": "A(H3N2)",
    "A (unknown)": "A (not subtyped)",
    "B/Vic": "B/Victoria",
    "B (unknown)": "B (not typed)",
}

# Viruses shown together in the "last 12 months" chart, as in the national weekly reports.
RECENT_KEYS = ["flu_a_cases", "flu_b_cases", "covid_cases", "rsv_cases"]
RECENT_WEEKS = 52

SEASON_START_WEEK = 40
SENTINEL_EPIDEMIC_THRESHOLD = 10.0  # % positivity, ECDC convention
MIN_SENTINEL_TESTS = 20  # below this, sentinel positivity is flagged as uncertain
MAX_STALE_WEEKS = 8  # indicators not reported for longer than this are left out

# Intensity relative to the mean historical season peak of the indicator.
INTENSITY_LEVELS = [
    (0.10, "Baseline"),
    (0.40, "Low"),
    (0.70, "Medium"),
    (1.00, "High"),
    (float("inf"), "Very high"),
]

DASHBOARD_URL = "https://eirikwikheltne.github.io/flutracker/"
EXCEL_NAME = "flutracker_latest.xlsx"
