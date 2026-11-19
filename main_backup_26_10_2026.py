import os
import sys
import requests

from datetime import datetime,date
from io import StringIO
from dotenv import load_dotenv

from dotenv import load_dotenv
import os

load_dotenv()

from utils import (
    configure_logging,log_info,log_error,format_date_yyyy_mm_dd,
    get_redcap_dataElement_attribute_value_dict,
    get_option_code_attribute_value_dict,get_tei_details,get_tei_event_list
    
)

# ============================================================
# LOAD CONFIGURATION
# ============================================================

load_dotenv()

DHIS2_BASE_URL = os.getenv("DHIS2_BASE_URL")
DHIS2_USERNAME = os.getenv("DHIS2_USERNAME")
DHIS2_PASSWORD = os.getenv("DHIS2_PASSWORD")


DHIS2_ORG_UNIT_ID = os.getenv("DHIS2_ORG_UNIT_ID")


DHIS2_PROGRAM_ID_GRAM_POSITIVE = os.getenv("DHIS2_PROGRAM_ID_GRAM_POSITIVE")
DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING = os.getenv("DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING")
DHIS2_PROGRAM_ID_GRAM_NEGATIVE = os.getenv("DHIS2_PROGRAM_ID_GRAM_NEGATIVE")
DHIS2_PROGRAM_STAGE_ID_GN_SAMPLE_TESTING = os.getenv("DHIS2_PROGRAM_STAGE_ID_GN_SAMPLE_TESTING")

SEARCH_TEI_ATTRIBUTE_UID = os.getenv("SEARCH_TEI_ATTRIBUTE_UID")
SEARCH_VALUE = os.getenv("SEARCH_VALUE")

META_ATTRIBUTE_REDCAP_HEADER = os.getenv("META_ATTRIBUTE_REDCAP_HEADER")
META_ATTRIBUTE_REDCAP_CODE = os.getenv("META_ATTRIBUTE_REDCAP_CODE")

REDCAP_SYNC_STATUS_DATAELEMENT_UID = os.getenv("REDCAP_SYNC_STATUS_DATAELEMENT_UID")


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
# Collect events from both programs
# ============================================================


def collect_all_isolate_events(
    session_get,
    tei_list_gram_positive,
    tei_list_gram_negative
):
    """
    Collect event data from both programs into one list.

    Each event is associated with its study ID and event date.
    """

    all_isolate_events = []

    program_configs = [
        (
            tei_list_gram_positive,
            DHIS2_PROGRAM_ID_GRAM_POSITIVE,
            DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING,
            "Gram Positive"
        ),
        (
            tei_list_gram_negative,
            DHIS2_PROGRAM_ID_GRAM_NEGATIVE,
            DHIS2_PROGRAM_STAGE_ID_GN_SAMPLE_TESTING,
            "Gram Negative"
        )
    ]

    for tei_list, program_uid, stage_uid, program_name in program_configs:

        for tei in tei_list or []:

            tei_uid = tei["trackedEntity"]

            attributes_dict = {
                attr["attribute"]: attr.get("value", "")
                for attr in tei.get("attributes", [])
            }

            study_id = attributes_dict.get(
                SEARCH_TEI_ATTRIBUTE_UID
            )

            if not study_id:
                log_info(
                    f"Skipping TEI {tei_uid} from {program_name}: "
                    f"study ID is missing"
                )
                continue

            event_list = get_tei_event_list(
                session_get,
                DHIS2_BASE_URL,
                tei_uid,
                program_uid,
                stage_uid,
                REDCAP_SYNC_STATUS_DATAELEMENT_UID
            )

            for event in event_list or []:

                event_date = format_date_yyyy_mm_dd(
                    event["occurredAt"]
                )

                data_values = {
                    dv["dataElement"]: dv.get("value", "")
                    for dv in event.get("dataValues", [])
                }

                all_isolate_events.append({
                    "study_id": study_id,
                    "event_date": event_date,
                    "event_uid": event["event"],
                    "program": program_name,
                    "data_values": data_values
                })

    log_info(
        f"Total events collected across both programs: "
        f"{len(all_isolate_events)}"
    )

    return all_isolate_events


def get_redcap_mapped_value(
    data_element_uid,
    dhis2_value,
    data_element_by_uid,
    option_code_attr_value_dict
):
    """
    Convert a DHIS2 Data Element value into its REDCap value
    using the Data Element's option set and option metadata.

    If the Data Element has no option set, return the original value.
    """

    if dhis2_value is None or str(dhis2_value).strip() == "":
        return ""

    data_element = data_element_by_uid.get(data_element_uid)

    if not data_element:
        log_info(
            f"Data Element {data_element_uid} not found in metadata."
        )
        return dhis2_value

    option_set = data_element.get("optionSet")

    # No option set: return the original DHIS2 value.
    if not option_set:
        return dhis2_value

    option_set_uid = option_set["id"]
    option_key = (option_set_uid, dhis2_value)

    if option_key in option_code_attr_value_dict:
        mapped_value = option_code_attr_value_dict[option_key]

        if mapped_value is not None:
            return mapped_value

    log_info(
        f"No REDCap option mapping found for "
        f"DE {data_element_uid}, "
        f"option set {option_set_uid}, "
        f"value {dhis2_value}"
    )

    return ""

def load_required_data_element_metadata(
    session_get,
    dhis2_base_url,
    data_element_by_uid
):
    """
    Ensure that the hardcoded pathogen Data Elements have metadata,
    including their optionSet IDs.
    """
    required_uids = [
        DHIS2_DE_PATHOGEN_NAME,
        DHIS2_DE_AST_MIC
    ]

    for de_uid in required_uids:
        response = session_get.get(
            f"{dhis2_base_url.rstrip('/')}/dataElements/{de_uid}",
            params={"fields": "id,name,optionSet[id]"}
        )
        response.raise_for_status()

        data_element = response.json()

        if data_element.get("id"):
            data_element_by_uid[de_uid] = data_element

            log_info(
                f"Loaded metadata for Data Element "
                f"{de_uid}: {data_element}"
            )

# ============================================================
# HARDCODED REDCAP PATHOGEN FIELD MAPPING
# ============================================================

DHIS2_DE_ISOLATE = "GCEJBEQ9TBk"
DHIS2_DE_PATHOGEN_NAME = "VsNSbOlwed9"
DHIS2_DE_AST_MIC = "tkUxDJN62fT"


def is_true_value(value):
    """
    Determine whether a DHIS2 data value represents true.
    """
    if value is None:
        return False

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes"
    }

## contains only events that contributed at least one non-empty mapped pathogen name or AST/MIC value to the REDCap payload

'''
def build_pathogen_redcap_fields(
    study_id,
    event_date,
    all_isolate_events,
    data_element_by_uid,
    option_code_attr_value_dict,
):
    """
    Build REDCap pathogen fields for events matching the same study ID and date.

    Returns:
        redcap_fields: Dict of REDCap pathogen fields.
        events_used_in_payload: Events that contributed at least one non-empty
                                pathogen name or AST/MIC value to the payload.
    """

    redcap_fields = {
        "pathogen_count": "0",
    }

    # Initialize four pathogen slots
    for index in range(1, 5):
        redcap_fields[f"pathogen_name_{index}"] = ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ""

    
    print(f"Target study_id: {study_id!r}")
    print(f"Target event_date: {event_date!r}")
    print(f"Total isolate events collected: {len(all_isolate_events)}")

    for event in all_isolate_events:
        data_values = event.get("data_values", {})

        print(
            f"event_uid={event.get('event_uid')!r}, "
            f"study_id={event.get('study_id')!r}, "
            f"event_date={event.get('event_date')!r}, "
            f"isolate_flag={data_values.get(DHIS2_DE_ISOLATE)!r}, "
            f"pathogen_name={data_values.get(DHIS2_DE_PATHOGEN_NAME)!r}, "
            f"ast_mic={data_values.get(DHIS2_DE_AST_MIC)!r}"
        )
    

    # Find isolate events matching the study ID, event date, and isolate flag
    matching_events = [
        event
        for event in all_isolate_events
        if event.get("study_id") == study_id
        and event.get("event_date") == event_date
        and is_true_value(
            event.get("data_values", {}).get(DHIS2_DE_ISOLATE)
        )
    ]

    
    matching_events = [
        event
        for event in all_isolate_events
        if str(event.get("study_id", "")).strip() == str(study_id).strip()
        and str(event.get("event_date", "")).strip() == str(event_date).strip()
        and (
            str(
                event.get("data_values", {}).get(
                    DHIS2_DE_PATHOGEN_NAME
                ) or ""
            ).strip()
            or str(
                event.get("data_values", {}).get(
                    DHIS2_DE_AST_MIC
                ) or ""
            ).strip()
        )
    ]
    
    print(f"Matching isolate events: {len(matching_events)}")

    
    for event in matching_events:
        print(f"Matched event UID: {event.get('event_uid')}")

    for event in matching_events:
        print(f"Matched event UID: {event.get('event_uid')}")
    

    # Preserve the existing count of all matching isolate events
    redcap_fields["pathogen_count"] = str(len(matching_events))

    events_used_in_payload = []

    # Only four pathogen slots are available in the REDCap payload
    for index, isolate_event in enumerate(matching_events[:4], start=1):
        data_values = isolate_event.get("data_values", {})

        pathogen_name_dhis2 = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )
        ast_mic_value_dhis2 = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

        # Map DHIS2 values to REDCap values
        pathogen_name = get_redcap_mapped_value(
            DHIS2_DE_PATHOGEN_NAME,
            pathogen_name_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        ast_mic_value = get_redcap_mapped_value(
            DHIS2_DE_AST_MIC,
            ast_mic_value_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        # Populate the REDCap payload fields
        redcap_fields[f"pathogen_name_{index}"] = pathogen_name
        redcap_fields[f"pathogen_ast_mic_{index}"] = ast_mic_value

        # Include the source event only if at least one mapped value
        # was actually added to its REDCap pathogen slot.
        if (
            pathogen_name is not None
            and str(pathogen_name).strip() != ""
        ) or (
            ast_mic_value is not None
            and str(ast_mic_value).strip() != ""
        ):
            events_used_in_payload.append(isolate_event)

    return redcap_fields, events_used_in_payload
'''

'''
def build_pathogen_redcap_fields(
    study_id,
    event_date,
    all_isolate_events,
    data_element_by_uid,
    option_code_attr_value_dict
):
    """
    Build hardcoded REDCap pathogen fields.

    Only events matching the same study_id and event_date
    with Another Isolate = true are included.

    all_isolate_events format:
    [
        {
            "study_id": "...",
            "event_date": "YYYY-MM-DD",
            "event_uid": "...",
            "data_values": {
                "GCEJBEQ9TBk": "true",
                "VsNSbOlwed9": "...",
                "tkUxDJN62fT": "..."
            }
        }
    ]
    """

    redcap_fields = {
        "pathogen_count": "0"
    }

    # Initialize all four pathogen slots.
    for i in range(1, 5):
        redcap_fields[f"pathogen_name_{i}"] = ""
        redcap_fields[f"pathogen_ast_mic_{i}"] = ""

    if not study_id or not event_date:
        return redcap_fields

    # Select isolate events matching study ID and event date.
    matching_events = []

    for isolate_event in all_isolate_events:

        if isolate_event.get("study_id") != study_id:
            continue

        if isolate_event.get("event_date") != event_date:
            continue

        data_values = isolate_event.get("data_values", {})

        if not is_true_value(
            data_values.get(DHIS2_DE_ISOLATE)
        ):
            continue

        matching_events.append(isolate_event)

    # Count all qualifying events, not just the first four.
    redcap_fields["pathogen_count"] = str(len(matching_events))

    # Populate up to four pathogen slots.
    for index, isolate_event in enumerate(matching_events[:4], start=1):

        data_values = isolate_event.get("data_values", {})


        # Get raw DHIS2 values.
        pathogen_name_dhis2 = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )

        ast_mic_value_dhis2 = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

        # Convert DHIS2 option codes into REDCap values.
        pathogen_name = get_redcap_mapped_value(
            DHIS2_DE_PATHOGEN_NAME,
            pathogen_name_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict
        )

        ast_mic_value = get_redcap_mapped_value(
            DHIS2_DE_AST_MIC,
            ast_mic_value_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict
        )

        # Assign mapped values to REDCap fields.
        redcap_fields[f"pathogen_name_{index}"] = pathogen_name
        redcap_fields[f"pathogen_ast_mic_{index}"] = ast_mic_value

        """
        pathogen_name = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )

        ast_mic_value = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

        redcap_fields[f"pathogen_name_{index}"] = (
            "" if pathogen_name is None else str(pathogen_name)
        )

        redcap_fields[f"pathogen_ast_mic_{index}"] = (
            "" if ast_mic_value is None else str(ast_mic_value)
        )
        """

    return redcap_fields

'''

def build_pathogen_redcap_fields(
    study_id,
    event_date,
    all_isolate_events,
    data_element_by_uid,
    option_code_attr_value_dict,
):
    """
    Build REDCap pathogen fields from qualifying isolate events.

    Returns:
        redcap_fields: Pathogen fields for the REDCap payload.
        events_used_in_payload: Qualifying events that contributed
                                a non-empty pathogen name or AST/MIC.
    """

    redcap_fields = {
        "pathogen_count": "0",
    }

    # Initialize pathogen slots 1-4
    for index in range(1, 5):
        redcap_fields[f"pathogen_name_{index}"] = ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ""

    # Find qualifying isolate events for the same study ID and date.
    matching_events = [
        event
        for event in all_isolate_events
        if str(event.get("study_id") or "").strip()
        == str(study_id).strip()
        and str(event.get("event_date") or "").strip()
        == str(event_date).strip()
        and is_true_value(
            event.get("data_values", {}).get(DHIS2_DE_ISOLATE)
        )
    ]

    # Maximum of four pathogen slots in REDCap.
    matching_events = matching_events[:4]

    # Count qualifying events, from 0 to 4.
    #redcap_fields["pathogen_count"] = str(len(matching_events))
    redcap_fields["pathogen_count"] = str(
        min(len(matching_events), 4)
    )
    
    log_info(
        f"Pathogen count for study_id={study_id}, event_date={event_date}, "
        f"event_count={len(matching_events)}, "
        f"event_uids={[event.get('event_uid') for event in matching_events]}"
    )

    print(
        f"Pathogen count for study_id={study_id}, event_date={event_date}, "
        f"event_count={len(matching_events)}, "
        f"event_uids={[event.get('event_uid') for event in matching_events]}"
    )

    events_used_in_payload = []

    # REDCap supports four pathogen slots.
    for index, isolate_event in enumerate(matching_events[:4], start=1):
        data_values = isolate_event.get("data_values", {})

        pathogen_name_dhis2 = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )

        ast_mic_value_dhis2 = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

        pathogen_name = get_redcap_mapped_value(
            DHIS2_DE_PATHOGEN_NAME,
            pathogen_name_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        ast_mic_value = get_redcap_mapped_value(
            DHIS2_DE_AST_MIC,
            ast_mic_value_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        # Populate the corresponding REDCap slot.
        redcap_fields[f"pathogen_name_{index}"] = pathogen_name or ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ast_mic_value or ""

        # Track only events that contributed an actual value.
        if (
            str(pathogen_name or "").strip()
            or str(ast_mic_value or "").strip()
        ):
            events_used_in_payload.append(isolate_event)

    return redcap_fields, events_used_in_payload




# ============================================================
# MAIN
# ============================================================

def main():

    configure_logging()

    print("========================================")
    print("DHIS2 -> REDCap Microbiology Integration")
    print("========================================")

    session_get = requests.Session()
    session_get.auth = (DHIS2_USERNAME, DHIS2_PASSWORD)

    print("-" * 100)
    log_info("-" * 100)

    current_time_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print( f"redcap to dhis2 integration process start . { current_time_start }" )
    log_info(f"redcap to dhis2 integration process start  . { current_time_start }")
    
    redcap_dataElement_attr_value_dict, data_element_list = get_redcap_dataElement_attribute_value_dict( session_get, DHIS2_BASE_URL, META_ATTRIBUTE_REDCAP_HEADER )
    log_info(f"redcap_dataElement_attr_value_dict {len(redcap_dataElement_attr_value_dict)}")
    print(f"redcap_dataElement_attr_value_dict {len(redcap_dataElement_attr_value_dict)}")


    
    option_code_attr_value_dict = get_option_code_attribute_value_dict( session_get, DHIS2_BASE_URL, META_ATTRIBUTE_REDCAP_CODE )
    log_info(f"option_code_attr_value_dict {len(option_code_attr_value_dict)}")
    print(f"option_code_attr_value_dict {len(option_code_attr_value_dict)}")

    # Create a lookup dictionary: Data Element UID -> Data Element metadata
    # Create a lookup dictionary: Data Element UID -> Data Element metadata
    data_element_by_uid = {
        data_element["id"]: data_element
        for data_element in data_element_list
    }

    # Ensure hardcoded pathogen Data Elements have option-set metadata.
    load_required_data_element_metadata(
        session_get,
        DHIS2_BASE_URL,
        data_element_by_uid
    )

    tei_list_gram_positive = get_tei_details( session_get, DHIS2_BASE_URL, DHIS2_ORG_UNIT_ID, DHIS2_PROGRAM_ID_GRAM_POSITIVE, SEARCH_TEI_ATTRIBUTE_UID, SEARCH_VALUE )
    
    print(f"trackedEntityInstances list Size for gram positive for redcap integration {len(tei_list_gram_positive) }")
    log_info(f"trackedEntityInstances list Size for gram positive for redcap integration {len(tei_list_gram_positive) } ")

    tei_list_gram_negative = get_tei_details( session_get, DHIS2_BASE_URL, DHIS2_ORG_UNIT_ID, DHIS2_PROGRAM_ID_GRAM_NEGATIVE, SEARCH_TEI_ATTRIBUTE_UID, SEARCH_VALUE )
    
    print(f"trackedEntityInstances list Size for gram negative for redcap integration {len(tei_list_gram_negative) }")
    log_info(f"trackedEntityInstances list Size for gram negative for redcap integration {len(tei_list_gram_negative) } ")

    all_isolate_events = collect_all_isolate_events(
        session_get,
        tei_list_gram_positive,
        tei_list_gram_negative
    )

## For Gram Positive

    if tei_list_gram_positive:
        for tei in tei_list_gram_positive:
            tei_uid = tei["trackedEntity"]
            org_unit = tei["orgUnit"]

            # Convert TEI attributes into a dictionary
            attributes_dict = {
                attr["attribute"]: attr.get("value", "")
                for attr in tei.get("attributes", [])
            }

            study_id = attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID)
            print("-" * 100)
            log_info("-" * 100)

            print(
                f"Source TEI UID Gram Positive: {tei_uid}, "
                f"Source Org Unit: {org_unit}, study_id: {study_id}"
            )

            tei_event_list_gram_positive = get_tei_event_list(
                session_get,
                DHIS2_BASE_URL,
                tei_uid,
                DHIS2_PROGRAM_ID_GRAM_POSITIVE,
                DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING,
                REDCAP_SYNC_STATUS_DATAELEMENT_UID
            )

            print(
                f"TEI {tei_uid} event list size for Gram Positive "
                f"REDCap integration: {len(tei_event_list_gram_positive)}"
            )

            log_info(
                f"TEI {tei_uid} event list size for Gram Positive "
                f"REDCap integration: {len(tei_event_list_gram_positive)}"
            )

            if not tei_event_list_gram_positive:
                continue

            for gram_positive_event in tei_event_list_gram_positive:

                gram_positive_event_uid = gram_positive_event["event"]

                gram_positive_event_date = format_date_yyyy_mm_dd(
                    gram_positive_event["occurredAt"]
                )
                print(
                    f"TEI {tei_uid} gram_positive_event_uid {gram_positive_event_uid} "
                    f"gram_positive_event_date: {gram_positive_event_date}"
                )

                log_info(
                    f"TEI {tei_uid} gram_positive_event_uid {gram_positive_event_uid} "
                    f"gram_positive_event_date: {gram_positive_event_date}"
                )
                event_datavalues_dict_gram_positive = {
                    data_value["dataElement"]: data_value.get("value", "")
                    for data_value in gram_positive_event.get("dataValues", [])
                }

                print("-" * 100)
                log_info("-" * 100)
                # Build REDCap record dynamically
                redcap_payload = {}

                # Add study ID if your REDCap field mapping requires it.
                if study_id:
                    redcap_payload["study_id"] = study_id
                    redcap_payload["microbiology_done"] = "1"
                    redcap_payload["redcap_event_name"] = "ipc_crfs_arm_1"
                    redcap_payload["redcap_repeat_instrument"] = "microbiology"
                    redcap_payload["sample_date"] = gram_positive_event_date
                    

                # Add event metadata if your REDCap project requires these fields.
                # Replace these names with the actual REDCap variable names.
                # redcap_payload["dhis2_event_uid"] = gram_positive_event_uid
                # redcap_payload["event_date"] = gram_positive_event_date

                for data_element in data_element_list:

                    de_uid = data_element["id"]

                    # Get the REDCap variable name mapped to this DHIS2 DE.
                    redcap_variable_name = (
                        redcap_dataElement_attr_value_dict.get(de_uid)
                    )

                    if not redcap_variable_name:
                        log_info(
                            f"No REDCap variable mapping for DHIS2 DE {de_uid}"
                        )
                        continue

                    # Check whether the event contains this DE.
                    if de_uid not in event_datavalues_dict_gram_positive:
                        continue

                    dhis2_value = event_datavalues_dict_gram_positive[de_uid]

                    # Preserve valid values such as 0; skip only empty values.
                    if dhis2_value is None or str(dhis2_value).strip() == "":
                        continue

                    option_set = data_element.get("optionSet")
                    redcap_data_value = dhis2_value

                    # Convert DHIS2 option code to the corresponding REDCap value.
                    if option_set:
                        option_set_uid = option_set["id"]

                        option_key = (option_set_uid, dhis2_value)

                        if option_key in option_code_attr_value_dict:
                            mapped_value = option_code_attr_value_dict[option_key]

                            if mapped_value is not None:
                                redcap_data_value = mapped_value
                            else:
                                log_info(
                                    f"No REDCap option value for "
                                    f"DE {de_uid}, option code {dhis2_value}"
                                )
                                continue
                        else:
                            log_info(
                                f"No option mapping for option set "
                                f"{option_set_uid}, option code {dhis2_value}, "
                                f"DE {de_uid}"
                            )
                            continue

                    # Add the mapped variable/value to the payload.
                    redcap_payload[redcap_variable_name] = redcap_data_value

                
                # Add pathogen fields from matching Gram Positive and Gram Negative events.
                pathogen_fields, pathogen_events_used = build_pathogen_redcap_fields(
                    study_id=study_id,
                    event_date=gram_positive_event_date,
                    all_isolate_events=all_isolate_events,
                    data_element_by_uid=data_element_by_uid,
                    option_code_attr_value_dict=option_code_attr_value_dict
                )

                redcap_payload.update(pathogen_fields)

                print(
                    f"DHIS2 event UID: {gram_positive_event_uid}, "
                    f"event date: {gram_positive_event_date}"
                )
                print(f"Dynamic REDCap payload: {redcap_payload}")

                log_info(
                    f"Dynamic REDCap payload for event "
                    f"{gram_positive_event_uid}: {redcap_payload}"
                )
                print("-" * 100)
                log_info("-" * 100)
                # Send redcap_payload to your existing REDCap integration
                # function here, once the payload has been validated.




    print("-" * 100)
    log_info("-" * 100)

## For Gram Negative
    print("========================================")
    print(f"For Gram Negative:")

    if tei_list_gram_negative:
        for tei in tei_list_gram_negative:
            tei_uid = tei["trackedEntity"]
            org_unit = tei["orgUnit"]

            # Convert TEI attributes into a dictionary
            attributes_dict = {
                attr["attribute"]: attr.get("value", "")
                for attr in tei.get("attributes", [])
            }

            study_id = attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID)
            print("-" * 100)
            log_info("-" * 100)

            print(
                f"Source TEI UID Gram Negative: {tei_uid}, "
                f"Source Org Unit: {org_unit}, study_id: {study_id}"
            )

            tei_event_list_gram_negative = get_tei_event_list(
                session_get,
                DHIS2_BASE_URL,
                tei_uid,
                DHIS2_PROGRAM_ID_GRAM_NEGATIVE,
                DHIS2_PROGRAM_STAGE_ID_GN_SAMPLE_TESTING,
                REDCAP_SYNC_STATUS_DATAELEMENT_UID
            )

            print(
                f"TEI {tei_uid} event list size for Gram Negative "
                f"REDCap integration: {len(tei_event_list_gram_negative)}"
            )

            log_info(
                f"TEI {tei_uid} event list size for Gram Negative "
                f"REDCap integration: {len(tei_event_list_gram_negative)}"
            )

            if not tei_event_list_gram_negative:
                continue

            for gram_negative_event in tei_event_list_gram_negative:

                gram_negative_event_uid = gram_negative_event["event"]

                gram_negative_event_date = format_date_yyyy_mm_dd(
                    gram_negative_event["occurredAt"]
                )

                event_datavalues_dict_gram_negative = {
                    data_value["dataElement"]: data_value.get("value", "")
                    for data_value in gram_negative_event.get("dataValues", [])
                }
                
                print(
                    f"TEI {tei_uid} gram_negative_event_uid {gram_negative_event_uid} "
                    f"gram_negative_event_date: {gram_negative_event_date}"
                )

                log_info(
                    f"TEI {tei_uid} gram_negative_event_uid {gram_negative_event_uid} "
                    f"gram_negative_event_date: {gram_negative_event_date}"
                )

                print("-" * 100)
                log_info("-" * 100)
                # Build REDCap record dynamically
                redcap_payload = {}

                # Add study ID if your REDCap field mapping requires it.
                if study_id:
                    redcap_payload["study_id"] = study_id
                    redcap_payload["microbiology_done"] = "1"
                    redcap_payload["redcap_event_name"] = "ipc_crfs_arm_1"
                    redcap_payload["redcap_repeat_instrument"] = "microbiology"
                    redcap_payload["sample_date"] = gram_negative_event_date                 

                # Add event metadata if your REDCap project requires these fields.
                # Replace these names with the actual REDCap variable names.
                # redcap_payload["dhis2_event_uid"] = gram_positive_event_uid
                # redcap_payload["event_date"] = gram_positive_event_date

                for data_element in data_element_list:

                    de_uid = data_element["id"]

                    # Get the REDCap variable name mapped to this DHIS2 DE.
                    redcap_variable_name = (
                        redcap_dataElement_attr_value_dict.get(de_uid)
                    )

                    if not redcap_variable_name:
                        log_info(
                            f"No REDCap variable mapping for DHIS2 DE {de_uid}"
                        )
                        continue

                    # Check whether the event contains this DE.
                    if de_uid not in event_datavalues_dict_gram_negative:
                        continue

                    dhis2_value = event_datavalues_dict_gram_negative[de_uid]

                    # Preserve valid values such as 0; skip only empty values.
                    if dhis2_value is None or str(dhis2_value).strip() == "":
                        continue

                    option_set = data_element.get("optionSet")
                    redcap_data_value = dhis2_value

                    # Convert DHIS2 option code to the corresponding REDCap value.
                    if option_set:
                        option_set_uid = option_set["id"]

                        option_key = (option_set_uid, dhis2_value)

                        if option_key in option_code_attr_value_dict:
                            mapped_value = option_code_attr_value_dict[option_key]

                            if mapped_value is not None:
                                redcap_data_value = mapped_value
                            else:
                                log_info(
                                    f"No REDCap option value for "
                                    f"DE {de_uid}, option code {dhis2_value}"
                                )
                                continue
                        else:
                            log_info(
                                f"No option mapping for option set "
                                f"{option_set_uid}, option code {dhis2_value}, "
                                f"DE {de_uid}"
                            )
                            continue

                    # Add the mapped variable/value to the payload.
                    redcap_payload[redcap_variable_name] = redcap_data_value

                # Add pathogen fields from matching Gram Positive and Gram Negative events.
                pathogen_fields, pathogen_events_used = build_pathogen_redcap_fields(
                    study_id=study_id,
                    event_date=gram_negative_event_date,
                    all_isolate_events=all_isolate_events,
                    data_element_by_uid=data_element_by_uid,
                    option_code_attr_value_dict=option_code_attr_value_dict
                )

                redcap_payload.update(pathogen_fields)                    

                print(
                    f"DHIS2 event UID: {gram_negative_event_uid}, "
                    f"event date: {gram_negative_event_date}"
                )
                print(f"Dynamic REDCap payload: {redcap_payload}")

                log_info(
                    f"Dynamic REDCap payload for event "
                    f"{gram_negative_event_uid}: {redcap_payload}"
                )
                print("-" * 100)
                log_info("-" * 100)
                # Send redcap_payload to your existing REDCap integration
                # function here, once the payload has been validated.






'''
    ## for Gram Positive
    if tei_list_gram_positive:
        for tei in tei_list_gram_positive:
            tei_uid = tei["trackedEntity"]
            org_unit = tei["orgUnit"]

            # Convert attributes list into dictionary
            attributes_dict = {
                #attr["displayName"]: attr.get("value", "")
                attr["attribute"]: attr.get("value", "")
                for attr in tei.get("attributes", [])
            }
            study_id = attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID)
            print(f"Source TEI UID Gram Positive: {tei_uid}, Source Org Unit: {org_unit}, study_id: {study_id}" )

            tei_event_list_gram_positive = get_tei_event_list(session_get, DHIS2_BASE_URL, tei_uid, DHIS2_PROGRAM_ID_GRAM_POSITIVE,DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING, REDCAP_SYNC_STATUS_DATAELEMENT_UID)
            print(f"tei {tei_uid} event list Size for gram positive for redcap integration {len(tei_event_list_gram_positive) }")
            log_info(f"tei {tei_uid} event list Size for gram positive for redcap integration {len(tei_event_list_gram_positive) }")

            if tei_event_list_gram_positive:
                for gram_positive_event in tei_event_list_gram_positive:


                    gram_positive_event_uid = gram_positive_event["event"]
                    gram_positive_event_date = format_date_yyyy_mm_dd(gram_positive_event["occurredAt"])

                    print(f"tei {tei_uid} gram_positive_event_uid {gram_positive_event_uid} gram_positive_event_date {gram_positive_event_date} ")
                    event_datavalues_dict_gram_positive = {
                        dataValue["dataElement"]: dataValue["value"]
                        for dataValue in gram_positive_event.get("dataValues", [])
                    }

                    if data_element_list:
                        log_info(f"data_element_list {len(redcap_dataElement_attr_value_dict)}")
                        print(f"data_element_list {len(redcap_dataElement_attr_value_dict)}")

                        for data_element in data_element_list:
                            option_set = data_element.get("optionSet")
                            redcap_variable_name = redcap_dataElement_attr_value_dict[data_element["id"]]

                            print(f"redcap_variable_name : {redcap_variable_name}")
                            print(data_element["id"], data_element["name"] , event_datavalues_dict_gram_positive.get(data_element["id"]) )
                            if event_datavalues_dict_gram_positive.get(data_element["id"]):
                                if option_set:
                                    de_optionset = option_set["id"]
                                    #print(f"de_optionset: {de_optionset}")
                                    
                                    if (event_datavalues_dict_gram_positive.get(data_element["id"]) in option_code_attr_value_dict
                                            and option_code_attr_value_dict[(de_optionset, event_datavalues_dict_gram_positive.get(data_element["id"]))] is not None):
                                    
                                            redcap_data_value = option_code_attr_value_dict[(de_optionset, event_datavalues_dict_gram_positive.get(data_element["id"]))]
                                    
                                            print(f"redcap_data_value {redcap_data_value}" )
                                else:
                                    de_optionset = None
    


if tei_list_gram_positive:
    for tei in tei_list_gram_positive:
        tei_uid = tei["trackedEntity"]
        org_unit = tei["orgUnit"]

        # Convert TEI attributes into a dictionary
        attributes_dict = {
            attr["attribute"]: attr.get("value", "")
            for attr in tei.get("attributes", [])
        }

        study_id = attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID)

        print(
            f"Source TEI UID Gram Positive: {tei_uid}, "
            f"Source Org Unit: {org_unit}, study_id: {study_id}"
        )

        tei_event_list_gram_positive = get_tei_event_list(
            session_get,
            DHIS2_BASE_URL,
            tei_uid,
            DHIS2_PROGRAM_ID_GRAM_POSITIVE,
            DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING,
            REDCAP_SYNC_STATUS_DATAELEMENT_UID
        )

        print(
            f"TEI {tei_uid} event list size for Gram Positive "
            f"REDCap integration: {len(tei_event_list_gram_positive)}"
        )

        log_info(
            f"TEI {tei_uid} event list size for Gram Positive "
            f"REDCap integration: {len(tei_event_list_gram_positive)}"
        )

        if not tei_event_list_gram_positive:
            continue

        for gram_positive_event in tei_event_list_gram_positive:

            gram_positive_event_uid = gram_positive_event["event"]

            gram_positive_event_date = format_date_yyyy_mm_dd(
                gram_positive_event["occurredAt"]
            )

            event_datavalues_dict_gram_positive = {
                data_value["dataElement"]: data_value.get("value", "")
                for data_value in gram_positive_event.get("dataValues", [])
            }

            # Build REDCap record dynamically
            redcap_payload = {}

            # Add study ID if your REDCap field mapping requires it.
            if study_id:
                redcap_payload["study_id"] = study_id

            # Add event metadata if your REDCap project requires these fields.
            # Replace these names with the actual REDCap variable names.
            # redcap_payload["dhis2_event_uid"] = gram_positive_event_uid
            # redcap_payload["event_date"] = gram_positive_event_date

            for data_element in data_element_list:

                de_uid = data_element["id"]

                # Get the REDCap variable name mapped to this DHIS2 DE.
                redcap_variable_name = (
                    redcap_dataElement_attr_value_dict.get(de_uid)
                )

                if not redcap_variable_name:
                    log_info(
                        f"No REDCap variable mapping for DHIS2 DE {de_uid}"
                    )
                    continue

                # Check whether the event contains this DE.
                if de_uid not in event_datavalues_dict_gram_positive:
                    continue

                dhis2_value = event_datavalues_dict_gram_positive[de_uid]

                # Preserve valid values such as 0; skip only empty values.
                if dhis2_value is None or str(dhis2_value).strip() == "":
                    continue

                option_set = data_element.get("optionSet")
                redcap_data_value = dhis2_value

                # Convert DHIS2 option code to the corresponding REDCap value.
                if option_set:
                    option_set_uid = option_set["id"]

                    option_key = (option_set_uid, dhis2_value)

                    if option_key in option_code_attr_value_dict:
                        mapped_value = option_code_attr_value_dict[option_key]

                        if mapped_value is not None:
                            redcap_data_value = mapped_value
                        else:
                            log_info(
                                f"No REDCap option value for "
                                f"DE {de_uid}, option code {dhis2_value}"
                            )
                            continue
                    else:
                        log_info(
                            f"No option mapping for option set "
                            f"{option_set_uid}, option code {dhis2_value}, "
                            f"DE {de_uid}"
                        )
                        continue

                # Add the mapped variable/value to the payload.
                redcap_payload[redcap_variable_name] = redcap_data_value

            print(
                f"DHIS2 event UID: {gram_positive_event_uid}, "
                f"event date: {gram_positive_event_date}"
            )
            print(f"Dynamic REDCap payload: {redcap_payload}")

            log_info(
                f"Dynamic REDCap payload for event "
                f"{gram_positive_event_uid}: {redcap_payload}"
            )

            # Send redcap_payload to your existing REDCap integration
            # function here, once the payload has been validated.




    ## for Gram Negative
    if tei_list_gram_negative:
        for tei in tei_list_gram_negative:
            tei_uid = tei["trackedEntity"]
            org_unit = tei["orgUnit"]

            # Convert attributes list into dictionary
            attributes_dict = {
                #attr["displayName"]: attr.get("value", "")
                attr["attribute"]: attr.get("value", "")
                for attr in tei.get("attributes", [])
            }
            study_id = attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID)
            print(f"Source TEI UID Gram Negative : {tei_uid}, Source Org Unit: {org_unit}, study_id: {study_id}" )
            tei_event_list_gram_negative = get_tei_event_list(session_get, DHIS2_BASE_URL, tei_uid, DHIS2_PROGRAM_ID_GRAM_NEGATIVE, DHIS2_PROGRAM_STAGE_ID_GN_SAMPLE_TESTING, REDCAP_SYNC_STATUS_DATAELEMENT_UID)
            print(f"tei {tei_uid} event list Size for gram Negative for redcap integration {len(tei_event_list_gram_negative) }")
            log_info(f"tei {tei_uid} event list Size for gram Negative for redcap integration {len(tei_event_list_gram_negative) }")
            

        if data_element_list:
            log_info(f"data_element_list {len(redcap_dataElement_attr_value_dict)}")
            print(f"data_element_list {len(redcap_dataElement_attr_value_dict)}")

            for data_element in data_element_list:
                option_set = data_element.get("optionSet")
                print(data_element["id"], data_element["name"])
                if option_set:
                    de_optionset = option_set["id"]
                    #print(f"de_optionset: {de_optionset}")
                else:
                    de_optionset = None

'''

if __name__ == "__main__":
    main()


'''
if redcap_import_success:
    event_uids_to_update = {
        current_event_uid,
        *(
            isolate_event["event_uid"]
            for isolate_event in pathogen_events_used
            if isolate_event.get("event_uid")
        ),
    }

    for event_uid in event_uids_to_update:
        try:
            update_dhis2_event_redcap_sync_status(
                session_get_post,
                DHIS2_BASE_URL,
                event_uid,
            )
        except Exception as e:
            logger.exception(
                "Failed to update REDCap sync status for event %s: %s",
                event_uid,
                e,
            )    
'''       

'''
DHIS2_REDCAP_SYNC_STATUS_DE_UID = "bDLtMWyjper"


def update_dhis2_event_redcap_sync_status(
    session,
    dhis2_base_url,
    event_uid
):
    """
    Mark a DHIS2 event as successfully synced to REDCap.

    This function should only be called after REDCap confirms
    that the record was saved successfully.
    """

    tracker_url = (
        f"{dhis2_base_url.rstrip('/')}/tracker"
        "?async=false&importStrategy=UPDATE"
    )

    # Retrieve the existing event so its current data values can
    # be preserved while updating the sync-status Data Element.
    get_url = (
        f"{dhis2_base_url.rstrip('/')}/tracker/events/{event_uid}"
    )

    response = session.get(
        get_url,
        params={"fields": "*"}
    )
    response.raise_for_status()

    event = response.json()

    # Preserve the existing event data values.
    data_values = event.get("dataValues", [])

    # Update the existing sync-status value, or add it if absent.
    status_found = False

    for data_value in data_values:
        if data_value.get("dataElement") == DHIS2_REDCAP_SYNC_STATUS_DE_UID:
            data_value["value"] = "true"
            status_found = True
            break

    if not status_found:
        data_values.append({
            "dataElement": DHIS2_REDCAP_SYNC_STATUS_DE_UID,
            "value": "true"
        })

    event["dataValues"] = data_values

    # Submit the updated event through the DHIS2 Tracker API.
    payload = {
        "events": [event]
    }

    update_response = session.post(
        tracker_url,
        json=payload,
        headers={"Accept": "application/json"}
    )

    update_response.raise_for_status()

    result = update_response.json()

    log_info(
        f"DHIS2 REDCap sync-status update response for "
        f"event {event_uid}: {result}"
    )

    return result



    
DHIS2_REDCAP_SYNC_STATUS_DE_UID = "bDLtMWyjper"


def update_all_isolate_events_sync_status(
    session,
    dhis2_base_url,
    all_isolate_events,
    successful_event_uids,
):
    """
    Update the REDCap sync-status Data Element to true for each
    isolate event included in a successfully imported REDCap record.

    Only events whose UIDs are in successful_event_uids are updated.
    """
    updated_event_uids = set()

    for isolate_event in all_isolate_events:
        event_uid = isolate_event.get("event_uid")

        if not event_uid or event_uid not in successful_event_uids:
            continue

        # Avoid updating the same event more than once.
        if event_uid in updated_event_uids:
            continue

        update_dhis2_event_redcap_sync_status(
            session=session,
            dhis2_base_url=dhis2_base_url,
            event_uid=event_uid,
        )

        updated_event_uids.add(event_uid)

    log_info(
        f"Updated REDCap sync status for "
        f"{len(updated_event_uids)} isolate events."
    )

    return updated_event_uids


if redcap_import_success:
    successful_event_uids = {
        isolate_event["event_uid"]
        for isolate_event in matching_isolate_events
        if isolate_event.get("event_uid")
    }

    update_all_isolate_events_sync_status(
        session=session_get,
        dhis2_base_url=DHIS2_BASE_URL,
        all_isolate_events=all_isolate_events,
        successful_event_uids=successful_event_uids,
    )



```python
response = push_to_redcap(redcap_payload)

if response.status_code == 200:
    try:
        redcap_result = response.json()

        if isinstance(redcap_result, dict) and redcap_result.get("count", 0) > 0:

            # Get all source events for this study ID and event date
            source_events = source_events_by_study_date.get(
                (study_id, event_date), []
            )

            source_event_uids = [
                source_event["event_uid"]
                for source_event in source_events
                if source_event.get("event_uid")
            ]

            # Update sync status for every source event
            for event_uid in source_event_uids:
                updateEventDataValue = {
                    "event": event_uid,
                    "dataValues": [
                        {
                            "dataElement": REDCAP_SYNC_STATUS_DATAELEMENT_UID,
                            "value": "true"
                        }
                    ]
                }

                update_eventDataValue_in_dhis2(
                    DHIS2_BASE_URL,
                    session_get,
                    updateEventDataValue,
                    event_uid,
                    REDCAP_SYNC_STATUS_DATAELEMENT_UID,
                    tei_uid,
                    study_id
                )

                print(
                    f"DHIS2 sync status updated: "
                    f"study_id={study_id}, "
                    f"event_date={event_date}, "
                    f"event_uid={event_uid}"
                )

        else:
            print(
                f"REDCap import failed or imported no records: "
                f"study_id={study_id}, response={redcap_result}"
            )

    except ValueError:
        print(
            f"Invalid REDCap JSON response for study_id={study_id}. "
            "DHIS2 sync status was not updated."
        )

else:
    print(
        f"REDCap HTTP error: {response.status_code}. "
        f"DHIS2 sync status was not updated."
    )
```



def build_pathogen_redcap_fields(
    study_id,
    event_date,
    all_isolate_events,
    data_element_by_uid,
    option_code_attr_value_dict,
):
    """
    Build REDCap pathogen fields from qualifying isolate events.

    Returns:
        redcap_fields: Pathogen fields for the REDCap payload.
        events_used_in_payload: Qualifying events that contributed
                                a non-empty pathogen name or AST/MIC.
    """

    #redcap_fields = {"pathogen_count": "0",}

    redcap_fields = {
        "pathogen_count": "1",
    }

    # Initialize pathogen slots 1-4
    for index in range(1, 5):
        redcap_fields[f"pathogen_name_{index}"] = ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ""

    # Find qualifying isolate events for the same study ID and date.

    matching_events = [
        event
        for event in all_isolate_events
        if str(event.get("study_id") or "").strip()
        == str(study_id).strip()
        and str(event.get("event_date") or "").strip()
        == str(event_date).strip()
        and is_true_value(
            event.get("data_values", {}).get(DHIS2_DE_ISOLATE)
        )
    ]

    # Maximum of four pathogen slots in REDCap.
    matching_events = matching_events[:4]

    # Count qualifying events, from 0 to 4.
    redcap_fields["pathogen_count"] = str(len(matching_events))

    #redcap_fields["pathogen_count"] = str( min(len(matching_events), 4))
    
    #redcap_fields["pathogen_count"] = str(len(matching_events))
    redcap_fields["pathogen_count"] = str(1 + len(matching_events))


    matching_events = [
        event
        for event in all_isolate_events
        if str(event.get("study_id") or "").strip()
        == str(study_id).strip()
        and str(event.get("event_date") or "").strip()
        == str(event_date).strip()
        and str(
            event.get("data_values", {}).get(DHIS2_DE_PATHOGEN_NAME) or ""
        ).strip()
    ]

    # Maximum of four pathogen slots in REDCap.
    matching_events = matching_events[:4]

    redcap_fields["pathogen_count"] = str(len(matching_events))


    print("-" * 100)
    log_info("-" * 100)

    log_info(
        f"Pathogen count for study_id={study_id}, event_date={event_date}, "
        f"event_count={len(matching_events)}, "
        f"event_uids={[event.get('event_uid') for event in matching_events]}"
    )

    print(
        f"Pathogen count for study_id={study_id}, event_date={event_date}, "
        f"event_count={len(matching_events)}, "
        f"event_uids={[event.get('event_uid') for event in matching_events]}"
    )

    events_used_in_payload = []

    # REDCap supports four pathogen slots.
    for index, isolate_event in enumerate(matching_events[:4], start=1):
        data_values = isolate_event.get("data_values", {})

        pathogen_name_dhis2 = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )

        ast_mic_value_dhis2 = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

        pathogen_name = get_redcap_mapped_value(
            DHIS2_DE_PATHOGEN_NAME,
            pathogen_name_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        ast_mic_value = get_redcap_mapped_value(
            DHIS2_DE_AST_MIC,
            ast_mic_value_dhis2,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        # Populate the corresponding REDCap slot.
        redcap_fields[f"pathogen_name_{index}"] = pathogen_name or ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ast_mic_value or ""

        # Track only events that contributed an actual value.
        if (
            str(pathogen_name or "").strip()
            or str(ast_mic_value or "").strip()
        ):
            events_used_in_payload.append(isolate_event)

    return redcap_fields, events_used_in_payload

    


    for (
        study_id,
        event_date,
        sample_type,
    ), redcap_payload in payloads_by_study_date.items():

        pathogen_fields, pathogen_events_used = build_pathogen_redcap_fields(
            study_id=study_id,
            event_date=event_date,
            all_isolate_events=all_isolate_events,
            data_element_by_uid=data_element_by_uid,
            option_code_attr_value_dict=option_code_attr_value_dict,
        )

        # Add pathogen fields to the combined payload.
        redcap_payload.update(pathogen_fields)

        log_info(
            f"Pathogen count for study_id={study_id}, "
            f"event_date={event_date}, "
            f"pathogen_events_used={len(pathogen_events_used)}"
        )

        source_events = source_events_by_study_date[
            (study_id, event_date)
        ]

        source_event_uids = [
            source_event["event_uid"]
            for source_event in source_events
        ]

        log_info("=" * 100)
        print("=" * 100)

        log_info(
            f"Combined REDCap payload: "
            f"study_id={study_id}, "
            f"event_date={event_date}, "
            f"source_events={source_event_uids}, "
            f"pathogen_events_used_uids={[event.get('event_uid') for event in pathogen_events_used]}"
        )

        log_info(
            f"Dynamic REDCap payload: {redcap_payload}"
        )

        print("=" * 100)

        print(
            f"Combined payload for study_id={study_id}, "
            f"event_date={event_date}"
        )

        print(f"Source event UIDs: {source_event_uids}")
        print(f"Dynamic REDCap payload: {redcap_payload}")

        if redcap_payload and study_id == 'GA1103E':
            print("=" * 100)
            print(f"for study_id {study_id} Dynamic REDCap payload: {redcap_payload}")

            try:
                log_info(
                    f"Combined REDCap payload for push in redcap: "
                    f"study_id={study_id}, "
                    f"event_date={event_date}, "
                    f"source_events={source_event_uids}, "
                    f"pathogen_events_used_uids={[event.get('event_uid') for event in pathogen_events_used]}"
                )
                print(
                    f"Combined REDCap payload for push in redcap: "
                    f"study_id={study_id}, "
                    f"event_date={event_date}, "
                    f"source_events={source_event_uids}, "
                    f"pathogen_events_used_uids={[event.get('event_uid') for event in pathogen_events_used]}"
                )                


                response = push_to_redcap(redcap_payload)

                # Update DHIS2 sync status only after successful REDCap import
                
                if response.status_code == 200:
                    try:
                        redcap_result = response.json()

                        if isinstance(redcap_result, dict) and redcap_result.get("count", 0) > 0:
                            print(
                                f"REDCap import successful for study_id={study_id}. "
                                f"Response from redcap: {redcap_result}"
                            )
                            log_info(
                                f"REDCap import successful for study_id={study_id}. "
                                f"Response from redcap: {redcap_result}"
                            )
                            for event_uid  in source_event_uids:
                                #event_uid = source_event.get("event_uid")

                                if not event_uid:
                                    continue

                                updateEventDataValue = {
                                    "event": event_uid,
                                    "dataValues": [
                                        {
                                            "dataElement": REDCAP_SYNC_STATUS_DATAELEMENT_UID,
                                            "value": "true"
                                        }
                                    ]
                                }
                                update_eventDataValue_in_dhis2(
                                    DHIS2_BASE_URL,
                                    session_get,
                                    updateEventDataValue,
                                    event_uid,
                                    REDCAP_SYNC_STATUS_DATAELEMENT_UID,
                                    tei_uid,
                                    study_id
                                )
                        else:
                            print(
                                f"REDCap import unsuccessful for study_id={study_id}. "
                                f"Response: {redcap_result}. "
                                "DHIS2 sync status was not updated."
                            )
                            log_info(
                                f"REDCap import unsuccessful for study_id={study_id}. "
                                f"Response: {redcap_result}. "
                                "DHIS2 sync status was not updated."
                            )
                    except ValueError:
                        print(
                            f"Invalid JSON response from REDCap for study_id={study_id}. "
                            "DHIS2 sync status was not updated."
                        )
                        
                        log_info(
                            f"Invalid JSON response from REDCap for study_id={study_id}. "
                            "DHIS2 sync status was not updated."
                        )                        

                else:
                    print(
                        f"REDCap HTTP request failed for study_id={study_id}. "
                        f"HTTP Status: {response.status_code}. "
                        "DHIS2 sync status was not updated."
                    )

                    log_info(
                        f"REDCap HTTP request failed for study_id={study_id}. "
                        f"HTTP Status: {response.status_code}. "
                        "DHIS2 sync status was not updated."
                    )

            except Exception as exc:
                log_error(
                    f"REDCap import failed for study_id="
                    f"{redcap_payload.get('study_id')}: {exc}"
                )
                print(
                    f"REDCap import failed for study_id="
                    f"{redcap_payload.get('study_id')}: {exc}"
                )                
                

def build_pathogen_redcap_fields_old(
    study_id,
    event_date,
    all_isolate_events,
    data_element_by_uid,
    option_code_attr_value_dict,
):
    """
    Build REDCap pathogen fields for a study ID and event date.

    Rules:
      - First matching event is included regardless of isolate flag.
      - Subsequent events are included only when isolate flag is true.
      - Maximum of four events are included.

    Returns:
        redcap_fields: REDCap pathogen fields.
        events_used_in_payload: Events contributing a mapped pathogen
                                name or AST/MIC value.
    """

    redcap_fields = {
        "pathogen_count": "0",
    }

    # Initialize REDCap pathogen slots 1-4.
    for index in range(1, 5):
        redcap_fields[f"pathogen_name_{index}"] = ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ""

    # Find all events matching the same study ID and event date.
    same_study_date_events = [
        event
        for event in all_isolate_events
        if str(event.get("study_id") or "").strip()
        == str(study_id).strip()
        and str(event.get("event_date") or "").strip()
        == str(event_date).strip()
    ]

    # Include the first event regardless of isolate flag.
    # Require isolate flag = true for subsequent events.
    matching_events = []

    for position, event in enumerate(same_study_date_events):
        data_values = event.get("data_values", {})
        isolate_flag = data_values.get(DHIS2_DE_ISOLATE)

        if position == 0 or is_true_value(isolate_flag):
            matching_events.append(event)

        if len(matching_events) >= 4:
            break

    # Count the events selected for pathogen mapping.
    redcap_fields["pathogen_count"] = str(len(matching_events))

    log_info(
        f"Pathogen selection: study_id={study_id}, "
        f"event_date={event_date}, "
        f"matching_event_count={len(matching_events)}, "
        f"event_uids=["
        f"{[event.get('event_uid') for event in matching_events]}]"
    )
    print(
        f"Pathogen selection: study_id={study_id}, "
        f"event_date={event_date}, "
        f"matching_event_count={len(matching_events)}, "
        f"event_uids=["
        f"{[event.get('event_uid') for event in matching_events]}]"
    )
    events_used_in_payload = []

    # Map pathogen name and AST/MIC into REDCap slots.
    for index, isolate_event in enumerate(matching_events, start=1):
        data_values = isolate_event.get("data_values", {})

        pathogen_name_raw = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )

        ast_mic_raw = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

        # Map DHIS2 values to REDCap values.
        pathogen_name = get_redcap_mapped_value(
            DHIS2_DE_PATHOGEN_NAME,
            pathogen_name_raw,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        ast_mic_value = get_redcap_mapped_value(
            DHIS2_DE_AST_MIC,
            ast_mic_raw,
            data_element_by_uid,
            option_code_attr_value_dict,
        )

        # Log raw and mapped values for troubleshooting.
        log_info(
            f"Pathogen mapping: study_id={study_id}, "
            f"event_date={event_date}, "
            f"event_uid={isolate_event.get('event_uid')}, "
            f"isolate_flag="
            f"{data_values.get(DHIS2_DE_ISOLATE)!r}, "
            f"pathogen_raw={pathogen_name_raw!r}, "
            f"ast_mic_raw={ast_mic_raw!r}, "
            f"pathogen_mapped={pathogen_name!r}, "
            f"ast_mic_mapped={ast_mic_value!r}"
        )
        print(
            f"Pathogen mapping: study_id={study_id}, "
            f"event_date={event_date}, "
            f"event_uid={isolate_event.get('event_uid')}, "
            f"isolate_flag="
            f"{data_values.get(DHIS2_DE_ISOLATE)!r}, "
            f"pathogen_raw={pathogen_name_raw!r}, "
            f"ast_mic_raw={ast_mic_raw!r}, "
            f"pathogen_mapped={pathogen_name!r}, "
            f"ast_mic_mapped={ast_mic_value!r}"
        )
        redcap_fields[f"pathogen_name_{index}"] = (
            pathogen_name or ""
        )

        redcap_fields[f"pathogen_ast_mic_{index}"] = (
            ast_mic_value or ""
        )

        # Track events that contributed at least one nonblank value.
        if (
            str(pathogen_name or "").strip()
            or str(ast_mic_value or "").strip()
        ):
            events_used_in_payload.append(isolate_event)

    log_info(
        f"Final pathogen fields: study_id={study_id}, "
        f"event_date={event_date}, fields={redcap_fields}"
    )

    return redcap_fields, events_used_in_payload




'''