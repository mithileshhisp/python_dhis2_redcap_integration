import os
import sys
import requests
import pandas as pd
from io import StringIO
from dotenv import load_dotenv


# ============================================================
# LOAD CONFIGURATION
# ============================================================

load_dotenv()

DHIS2_BASE_URL = os.getenv("DHIS2_BASE_URL")
DHIS2_USERNAME = os.getenv("DHIS2_USERNAME")
DHIS2_PASSWORD = os.getenv("DHIS2_PASSWORD")

DHIS2_PROGRAM_ID = os.getenv("DHIS2_PROGRAM_ID")
DHIS2_ORG_UNIT_ID = os.getenv("DHIS2_ORG_UNIT_ID")

REDCAP_URL = os.getenv(
    "REDCAP_URL",
    "https://redcap.ju.edu.et/api/"
)

REDCAP_TOKEN = os.getenv("REDCAP_TOKEN")

REDCAP_EVENT_NAME = os.getenv(
    "REDCAP_EVENT_NAME",
    "ipc_crfs_arm_1"
)

REDCAP_REPEAT_INSTRUMENT = os.getenv(
    "REDCAP_REPEAT_INSTRUMENT",
    "microbiology"
)

REDCAP_REPEAT_INSTANCE = os.getenv(
    "REDCAP_REPEAT_INSTANCE",
    "1"
)


# ============================================================
# VALIDATE CONFIGURATION
# ============================================================

required_config = {
    "DHIS2_BASE_URL": DHIS2_BASE_URL,
    "DHIS2_USERNAME": DHIS2_USERNAME,
    "DHIS2_PASSWORD": DHIS2_PASSWORD,
    "DHIS2_PROGRAM_ID": DHIS2_PROGRAM_ID,
    "DHIS2_ORG_UNIT_ID": DHIS2_ORG_UNIT_ID,
    "REDCAP_URL": REDCAP_URL,
    "REDCAP_TOKEN": REDCAP_TOKEN,
}

missing = [
    key for key, value in required_config.items()
    if not value
]

if missing:
    print("ERROR: Missing configuration:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)


# ============================================================
# DHIS2 -> REDCAP FIELD MAPPING
# ============================================================

DHIS2_TO_REDCAP = {
    "Microbiology done": "microbiology_done",
    "Sample collection date": "sample_date",
    "Sample type": "sample_type",
    "Antibiotic currently taken": "antibiotic_treatment",
    "Pathogen identified": "pathogen_name",
    "AST performed": "ast_done",
}


# ============================================================
# REDCAP CODE MAPPINGS
# ============================================================

YES_NO_RECODE = {
    "Yes": "1",
    "No": "0",
    "true": "1",
    "false": "0",
    "True": "1",
    "False": "0",
    "1": "1",
    "0": "0",
}


SAMPLE_TYPE_RECODE = {
    "Blood culture": "1",
    "Swab wound": "2",
    "Swab throat": "3",
    "Sputum": "4",
    "Ventilator aspirate": "5",
    "Urine": "6",
    "CSF": "7",
    "Ascites": "8",
    "Pleural fluid": "9",
    "Venous line swab": "10",
    "Other": "11",
}


ANTIBIOTIC_RECODE = {
    "Amikacin": "1",
    "Amoxicillin-clavulanic acid": "2",
    "Ampicillin": "3",
    "Bezylpenicillin": "4",
    "Cefepime": "5",
    "Cefotaxime": "6",
    "Cefoxitin": "7",
    "Ceftazidime": "8",
    "Ceftazidime-avibactam": "9",
    "Ceftriaxone": "10",
    "Cefuroxime": "11",
    "Ciprofloxacin": "12",
    "Clindamycin": "13",
    "Ertapenem": "14",
    "Erythromycin": "15",
    "Gentamycin": "16",
    "Linezolid": "17",
    "Meropenem": "18",
    "Moxifloxacin": "19",
    "Mupricum": "20",
    "Piperacillin-tazobactum": "21",
    "Sulfamethoxazole-trimethoprim": "22",
    "Tigecycline": "23",
    "Vancomycin": "24",
}


AST_RESULT_RECODE = {
    "Sensitive": "1",
    "Intermediate": "2",
    "Resistant": "3",
}


# ============================================================
# 1. GET DATA FROM DHIS2
# ============================================================

def get_dhis2_events():

    url = f"{DHIS2_BASE_URL.rstrip('/')}/tracker/events"

    params = {
        "program": DHIS2_PROGRAM_ID,
        "orgUnit": DHIS2_ORG_UNIT_ID,
        "fields": "*",
    }

    print("\nConnecting to DHIS2...")
    print(f"URL: {url}")

    response = requests.get(
        url,
        params=params,
        auth=(DHIS2_USERNAME, DHIS2_PASSWORD),
        timeout=120,
    )

    print(f"DHIS2 HTTP status: {response.status_code}")

    if response.status_code != 200:
        print("DHIS2 error:")
        print(response.text)
        response.raise_for_status()

    data = response.json()

    # Tracker API normally returns instances.
    events = data.get("instances", [])

    print(f"DHIS2 events retrieved: {len(events)}")

    return events


# ============================================================
# 2. CONVERT DHIS2 EVENTS TO DATAFRAME
# ============================================================

def convert_dhis2_events(events):

    records = []

    for event in events:

        tei = event.get("trackedEntityInstance")

        # Some Tracker API versions use different naming.
        if not tei:
            tei = event.get("trackedEntity")

        for data_value in event.get("dataValues", []):

            data_element = data_value.get("dataElement")
            value = data_value.get("value")

            records.append({
                "trackedEntityInstance": tei,
                "dataElement": data_element,
                "value": value,
            })

    df = pd.DataFrame(records)

    if df.empty:
        print("No DHIS2 data values found.")
        return df

    print(
        f"DHIS2 data values extracted: {len(df)}"
    )

    return df


# ============================================================
# 3. MAP DHIS2 DATA ELEMENTS TO REDCAP VARIABLES
# ============================================================

def map_to_redcap(df):

    if df.empty:
        return df

    df["redcap_variable"] = df["dataElement"].map(
        DHIS2_TO_REDCAP
    )

    # Remove fields that are not part of REDCap mapping
    df = df[
        df["redcap_variable"].notna()
    ].copy()

    print(
        f"Mapped DHIS2 values: {len(df)}"
    )

    return df


# ============================================================
# 4. PIVOT DATA
# ============================================================

def prepare_redcap_dataframe(df):

    if df.empty:
        return pd.DataFrame()

    # IMPORTANT:
    # If the same data element occurs more than once,
    # keep the first value for now.
    #
    # For repeated microbiology records, we will handle
    # repeat instances separately.

    df = df.drop_duplicates(
        subset=[
            "trackedEntityInstance",
            "redcap_variable"
        ],
        keep="last"
    )

    result = df.pivot(
        index="trackedEntityInstance",
        columns="redcap_variable",
        values="value"
    ).reset_index()

    result.columns.name = None

    # ========================================================
    # Rename TEI -> REDCap Record ID
    # ========================================================

    result = result.rename(
        columns={
            "trackedEntityInstance": "study_id_2"
        }
    )

    # ========================================================
    # REDCap event
    # ========================================================

    result["redcap_event_name"] = REDCAP_EVENT_NAME

    result["redcap_repeat_instrument"] = (
        REDCAP_REPEAT_INSTRUMENT
    )

    result["redcap_repeat_instance"] = (
        REDCAP_REPEAT_INSTANCE
    )

    # ========================================================
    # Recode values
    # ========================================================

    if "microbiology_done" in result.columns:
        result["microbiology_done"] = (
            result["microbiology_done"]
            .map(YES_NO_RECODE)
            .fillna(result["microbiology_done"])
        )

    if "antibiotic_treatment" in result.columns:
        result["antibiotic_treatment"] = (
            result["antibiotic_treatment"]
            .map(YES_NO_RECODE)
            .fillna(result["antibiotic_treatment"])
        )

    if "ast_done" in result.columns:
        result["ast_done"] = (
            result["ast_done"]
            .map(YES_NO_RECODE)
            .fillna(result["ast_done"])
        )

    if "sample_type" in result.columns:
        result["sample_type"] = (
            result["sample_type"]
            .map(SAMPLE_TYPE_RECODE)
            .fillna(result["sample_type"])
        )

    if "antibiotic" in result.columns:
        result["antibiotic"] = (
            result["antibiotic"]
            .map(ANTIBIOTIC_RECODE)
            .fillna(result["antibiotic"])
        )

    if "ast_result" in result.columns:
        result["ast_result"] = (
            result["ast_result"]
            .map(AST_RESULT_RECODE)
            .fillna(result["ast_result"])
        )

    # ========================================================
    # REDCap form completion
    # ========================================================

    result["microbiology_complete"] = "2"

    return result


# ============================================================
# 5. VALIDATE DATA
# ============================================================

def validate_data(df):

    print("\n==============================")
    print("VALIDATION")
    print("==============================")

    if df.empty:
        print("No data to import.")
        return False

    print(f"Records: {len(df)}")

    required_columns = [
        "study_id_2",
        "redcap_event_name",
        "redcap_repeat_instrument",
        "redcap_repeat_instance",
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        print(
            "Missing required columns:"
        )

        for col in missing_columns:
            print(f"  - {col}")

        return False

    # Check record ID
    empty_ids = df[
        df["study_id_2"].isna()
    ]

    if not empty_ids.empty:

        print(
            f"ERROR: {len(empty_ids)} records "
            "have no study_id_2"
        )

        return False

    # Check unknown sample types
    if "sample_type" in df.columns:

        allowed_sample_types = set(
            SAMPLE_TYPE_RECODE.values()
        )

        invalid = df[
            ~df["sample_type"]
            .astype(str)
            .isin(allowed_sample_types)
        ]

        if not invalid.empty:

            print(
                "WARNING: Unknown sample_type values:"
            )

            print(
                invalid["sample_type"]
                .drop_duplicates()
                .tolist()
            )

    print("\nValidation successful.")

    return True


# ============================================================
# 6. EXPORT PREVIEW CSV
# ============================================================

def save_preview(df):

    filename = "redcap_microbiology_preview.csv"

    df.to_csv(
        filename,
        index=False
    )

    print(
        f"\nPreview saved: {filename}"
    )


# ============================================================
# 7. IMPORT INTO REDCAP
# ============================================================

def import_to_redcap(df):

    if df.empty:
        print("Nothing to import.")
        return

    print("\n==============================")
    print("IMPORTING INTO REDCAP")
    print("==============================")

    csv_data = df.to_csv(
        index=False
    )

    payload = {
        "token": REDCAP_TOKEN,
        "content": "record",
        "action": "import",
        "format": "csv",
        "type": "flat",
        "overwriteBehavior": "normal",
        "forceAutoNumber": "false",
        "data": csv_data,
    }

    response = requests.post(
        REDCAP_URL,
        data=payload,
        timeout=120,
    )

    print(
        f"REDCap HTTP status: "
        f"{response.status_code}"
    )

    print(
        "REDCap response:"
    )

    print(response.text)

    if response.status_code != 200:

        print(
            "\nREDCap import FAILED."
        )

        response.raise_for_status()

    print(
        "\nREDCap import completed."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "========================================"
    )
    print(
        "DHIS2 -> REDCap Microbiology Integration"
    )
    print(
        "========================================"
    )

    # 1. Get DHIS2 events
    events = get_dhis2_events()

    if not events:
        print(
            "No events found in DHIS2."
        )
        return

    # 2. Convert to dataframe
    df = convert_dhis2_events(events)

    # 3. Map DHIS2 -> REDCap
    df = map_to_redcap(df)

    # 4. Prepare REDCap dataframe
    redcap_df = prepare_redcap_dataframe(df)

    # 5. Show preview
    print(
        "\n=============================="
    )
    print("REDCap DATA PREVIEW")
    print(
        "=============================="
    )

    print(
        redcap_df.to_string(index=False)
    )

    # 6. Validate
    valid = validate_data(
        redcap_df
    )

    if not valid:
        print(
            "\nImport stopped because "
            "validation failed."
        )
        return

    # 7. Save local CSV
    save_preview(
        redcap_df
    )

    # ========================================================
    # SAFETY SWITCH
    # ========================================================

    IMPORT_TO_REDCAP = False

    if not IMPORT_TO_REDCAP:

        print(
            "\nIMPORT_TO_REDCAP = False"
        )

        print(
            "No data was sent to REDCap."
        )

        print(
            "Review the CSV first."
        )

        return

    # 8. Import
    import_to_redcap(
        redcap_df
    )


if __name__ == "__main__":
    main()