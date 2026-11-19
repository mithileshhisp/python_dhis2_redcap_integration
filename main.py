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
    get_option_code_attribute_value_dict,get_tei_details,get_tei_event_list,
    push_to_redcap,update_eventDataValue_in_dhis2
    
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
                '''
                all_isolate_events.append({
                    "study_id": study_id,
                    "event_date": event_date,
                    "event_uid": event["event"],
                    "program": program_name,
                    "data_values": data_values
                })
                '''

                all_isolate_events.append({
                    "study_id": study_id,
                    "event_date": event_date,
                    "event_uid": event["event"],
                    "tei_uid": tei_uid,
                    "program": program_name,
                    "data_values": data_values,
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
DHIS2_DE_SAMPLE_TYPE = "GqP6sLQ1Wt3"
DHIS2_DE_ANTIBIOTIC_TREATMENT = "nASTEmeapke"


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

def build_pathogen_redcap_fields(
    study_id,
    event_date,
    sample_type,
    all_isolate_events,
    data_element_by_uid,
    option_code_attr_value_dict,
):
    """
    Build pathogen fields for one study ID, date and sample type.

    Include one primary event regardless of isolate flag, then
    include additional events only when isolate flag is true.
    Maximum four events per sample type.
    """

    redcap_fields = {"pathogen_count": "0"}

    for index in range(1, 5):
        redcap_fields[f"pathogen_name_{index}"] = ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ""

    # Match the same study ID, date and sample type.
    matching_sample_events = [
        event
        for event in all_isolate_events
        if str(event.get("study_id") or "").strip()
        == str(study_id).strip()
        and str(event.get("event_date") or "").strip()
        == str(event_date).strip()
        and str(
            event.get("data_values", {}).get(
                DHIS2_DE_SAMPLE_TYPE
            ) or ""
        ).strip()
        == str(sample_type).strip()
    ]

    if not matching_sample_events:
        return redcap_fields, []

    # Prefer a primary event whose isolate flag is not true.
    primary_event = next(
        (
            event
            for event in matching_sample_events
            if not is_true_value(
                event.get("data_values", {}).get(DHIS2_DE_ISOLATE)
            )
        ),
        matching_sample_events[0],
    )

    selected_events = [primary_event]

    # Additional events must have isolate flag = true.
    for event in matching_sample_events:
        if event is primary_event:
            continue

        if is_true_value(
            event.get("data_values", {}).get(DHIS2_DE_ISOLATE)
        ):
            selected_events.append(event)

        if len(selected_events) >= 4:
            break

    redcap_fields["pathogen_count"] = str(len(selected_events))

    events_used_in_payload = []

    for index, isolate_event in enumerate(selected_events, start=1):
        data_values = isolate_event.get("data_values", {})

        pathogen_name_raw = data_values.get(
            DHIS2_DE_PATHOGEN_NAME, ""
        )
        ast_mic_raw = data_values.get(
            DHIS2_DE_AST_MIC, ""
        )

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

        redcap_fields[f"pathogen_name_{index}"] = pathogen_name or ""
        redcap_fields[f"pathogen_ast_mic_{index}"] = ast_mic_value or ""

        log_info("-" * 100)
        print("-" * 100)
        log_info(
            f"Pathogen mapping: study_id={study_id}, "
            f"event_date={event_date}, sample_type={sample_type}, "
            f"event_uid={isolate_event.get('event_uid')}, "
            f"isolate_flag="
            f"{data_values.get(DHIS2_DE_ISOLATE)!r}, "
            f"pathogen={pathogen_name!r}, ast_mic={ast_mic_value!r}"
        )

        print(
            f"Pathogen mapping: study_id={study_id}, "
            f"event_date={event_date}, sample_type={sample_type}, "
            f"event_uid={isolate_event.get('event_uid')}, "
            f"isolate_flag="
            f"{data_values.get(DHIS2_DE_ISOLATE)!r}, "
            f"pathogen={pathogen_name!r}, ast_mic={ast_mic_value!r}"
        )
        if (
            str(pathogen_name or "").strip()
            or str(ast_mic_value or "").strip()
        ):
            events_used_in_payload.append(isolate_event)

    log_info(
        f"Pathogen fields built: study_id={study_id}, "
        f"event_date={event_date}, sample_type={sample_type}, "
        f"pathogen_count={redcap_fields['pathogen_count']}"
    )
    print(
        f"Pathogen fields built: study_id={study_id}, "
        f"event_date={event_date}, sample_type={sample_type}, "
        f"pathogen_count={redcap_fields['pathogen_count']}"
    )
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

    # ============================================================
    # BUILD ONE REDCAP PAYLOAD PER STUDY ID + EVENT DATE
    # ============================================================

    program_configs = [
        (
            tei_list_gram_positive,
            DHIS2_PROGRAM_ID_GRAM_POSITIVE,
            DHIS2_PROGRAM_STAGE_ID_GP_SAMPLE_TESTING,
            "Gram Positive",
        ),
        (
            tei_list_gram_negative,
            DHIS2_PROGRAM_ID_GRAM_NEGATIVE,
            DHIS2_PROGRAM_STAGE_ID_GN_SAMPLE_TESTING,
            "Gram Negative",
        ),
    ]

    # Key: (study_id, event_date)
    # Value: one combined REDCap payload for that study/date.
    payloads_by_study_date = {}

    # Keep track of all source events represented in each payload.
    source_events_by_study_date = {}

    for (
        tei_list,
        program_uid,
        stage_uid,
        program_name,
    ) in program_configs:

        for tei in tei_list or []:

            tei_uid = tei["trackedEntity"]
            org_unit = tei["orgUnit"]

            attributes_dict = {
                attr["attribute"]: attr.get("value", "")
                for attr in tei.get("attributes", [])
            }

            study_id = str(
                attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID) or ""
            ).strip()

            if not study_id:
                log_info(
                    f"Skipping TEI {tei_uid} from {program_name}: "
                    "study ID is missing."
                )
                continue

            # Retrieve the eligible events for this program and TEI.
            event_list = get_tei_event_list(
                session_get,
                DHIS2_BASE_URL,
                tei_uid,
                program_uid,
                stage_uid,
                REDCAP_SYNC_STATUS_DATAELEMENT_UID,
            )

            log_info(
                f"TEI {tei_uid}, program={program_name}, "
                f"eligible events={len(event_list or [])}"
            )

            for event in event_list or []:

                event_uid = event["event"]

                event_date = format_date_yyyy_mm_dd(
                    event["occurredAt"]
                )

                # One payload for each unique study ID and date.
                #payload_key = (study_id, event_date)

                # Convert event values before creating the payload key.
                # Convert this event's data values to a dictionary.
                event_data_values = {
                    dv["dataElement"]: dv.get("value", "")
                    for dv in event.get("dataValues", [])
                }

                antibiotic_value = str(
                    event_data_values.get(DHIS2_DE_ANTIBIOTIC_TREATMENT) or ""
                ).strip().lower()

                if antibiotic_value == "true":
                    antibiotic_treatment = "1"
                else:
                    antibiotic_treatment = "0"

                sample_type = str(
                    event_data_values.get(DHIS2_DE_SAMPLE_TYPE) or ""
                ).strip()

                if not sample_type:
                    log_info(
                        f"Skipping event {event_uid}: missing sample type; "
                        f"study_id={study_id}, event_date={event_date}"
                    )
                    print(
                        f"Skipping event {event_uid}: missing sample type; "
                        f"study_id={study_id}, event_date={event_date}"
                    )
                    continue

                # Separate payload for each study ID + date + sample type.
                payload_key = (study_id, event_date, sample_type)
                
                if payload_key not in payloads_by_study_date:
                    payloads_by_study_date[payload_key] = {
                        "study_id": study_id,
                        "redcap_event_name": REDCAP_EVENT_NAME,
                        "redcap_repeat_instrument": REDCAP_REPEAT_INSTRUMENT,
                        #"redcap_repeat_instance": str(repeat_instance),
                        "sample_date": event_date,

                        "antibiotic_treatment": antibiotic_treatment,
                        "microscopy_done": "1",
                        "microbiology_done": "1",
                        "pathogen_id_done": "1",
                    }

                    source_events_by_study_date[payload_key] = []

                redcap_payload = payloads_by_study_date[payload_key]

                source_events_by_study_date[payload_key].append({
                    "event_uid": event_uid,
                    "tei_uid": tei_uid,
                    "program_uid": program_uid,
                    "program": program_name,
                })

                #redcap_payload = payloads_by_study_date[payload_key]

                # Map the event's DHIS2 values to REDCap fields.
                for data_element in data_element_list:

                    de_uid = data_element["id"]

                    redcap_variable_name = (
                        redcap_dataElement_attr_value_dict.get(de_uid)
                    )

                    if not redcap_variable_name:
                        continue

                    if de_uid not in event_data_values:
                        continue

                    
                    dhis2_value = event_data_values[de_uid]
                    normalized_value = (
                        str(dhis2_value).strip().lower()
                        if dhis2_value is not None
                        else ""
                    )

                    if normalized_value in {"", "false"}:
                        continue

                    if normalized_value == "true":
                        dhis2_value = 1

                    #dhis2_value = 1 if str(dhis2_value).strip().lower() == "true" else None

                    # Preserve valid values such as numeric/string zero.
                    if (
                        dhis2_value is None
                        or str(dhis2_value).strip() == ""
                    ):
                        continue

                    redcap_data_value = dhis2_value
                    option_set = data_element.get("optionSet")

                    # Map DHIS2 option codes to REDCap values.
                    if option_set:

                        option_set_uid = option_set["id"]
                        option_key = (option_set_uid, dhis2_value)

                        if option_key not in option_code_attr_value_dict:
                            log_info(
                                f"No option mapping for "
                                f"DE={de_uid}, "
                                f"option_set={option_set_uid}, "
                                f"value={dhis2_value}"
                            )
                            continue

                        mapped_value = option_code_attr_value_dict[
                            option_key
                        ]

                        if mapped_value is None:
                            log_info(
                                f"No mapped REDCap value for "
                                f"DE={de_uid}, value={dhis2_value}"
                            )
                            continue

                        redcap_data_value = mapped_value

                    # Merge this field into the combined payload.
                    if redcap_variable_name not in redcap_payload:

                        redcap_payload[redcap_variable_name] = (
                            redcap_data_value
                        )

                    elif (
                        str(redcap_payload[redcap_variable_name])
                        != str(redcap_data_value)
                    ):

                        # Avoid silently replacing a value supplied by
                        # another source event.
                        log_info(
                            f"Conflicting values for REDCap field "
                            f"'{redcap_variable_name}' in "
                            f"study_id={study_id}, date={event_date}. "
                            f"Keeping existing value="
                            f"{redcap_payload[redcap_variable_name]!r}; "
                            f"ignoring value={redcap_data_value!r} "
                            f"from event={event_uid}."
                        )

    # ============================================================
    # ADD PATHOGEN FIELDS ONCE PER COMBINED PAYLOAD
    # ============================================================


    for (
        study_id,
        event_date,
        sample_type,
    ), redcap_payload in payloads_by_study_date.items():

        pathogen_fields, pathogen_events_used = build_pathogen_redcap_fields(
            study_id=study_id,
            event_date=event_date,
            sample_type=sample_type,
            all_isolate_events=all_isolate_events,
            data_element_by_uid=data_element_by_uid,
            option_code_attr_value_dict=option_code_attr_value_dict,
        )

        redcap_payload.update(pathogen_fields)

        source_events = source_events_by_study_date.get(
            (study_id, event_date, sample_type), []
        )

        source_event_uids = [
            item["event_uid"]
            for item in source_events
            if item.get("event_uid")
        ]

        log_info(
            f"Submitting payload: study_id={study_id}, "
            f"event_date={event_date}, sample_type={sample_type}, "
            f"source_events={source_event_uids}, "
            f"payload={redcap_payload}"
        )

        print(
            f"Submitting payload: study_id={study_id}, "
            f"event_date={event_date}, sample_type={sample_type}, "
            f"source_events={source_event_uids}, "
            f"payload={redcap_payload}"
        )
        
        #if redcap_payload and study_id == "GA1103E":
        if redcap_payload:
            log_info(
                f"Submitting payload 2: study_id={study_id}, "
                f"event_date={event_date}, sample_type={sample_type}, "
                f"source_events={source_event_uids}, "
                f"payload={redcap_payload}"
            )

            print(
                f"Submitting payload 2: study_id={study_id}, "
                f"event_date={event_date}, sample_type={sample_type}, "
                f"source_events={source_event_uids}, "
                f"payload={redcap_payload}"
            )
            
            try:
                response = push_to_redcap(redcap_payload)
                response.raise_for_status()

                redcap_result = response.json()

                # Confirm successful REDCap import.
                try:
                    imported_count = int(
                        redcap_result.get("count", 0)
                    ) if isinstance(redcap_result, dict) else 0
                except (ValueError, TypeError):
                    imported_count = 0

                if imported_count > 0:
                    log_info(
                        f"REDCap import successful: "
                        f"study_id={study_id}, date={event_date}, "
                        f"sample_type={sample_type}, "
                        f"response={redcap_result}"
                    )

                    # Update sync status only after confirmed import.
                    log_info("-" * 100)
                    print("-" * 100)
                    for source_event in source_events:
                        event_uid = source_event.get("event_uid")
                        event_tei_uid = source_event.get("tei_uid")

                        if not event_uid or not event_tei_uid:
                            log_error(
                                f"Missing event/TEI UID; cannot update "
                                f"sync status. study_id={study_id}, "
                                f"sample_type={sample_type}"
                            )
                            continue

                        update_event_payload = {
                            "event": event_uid,
                            "dataValues": [
                                {
                                    "dataElement":
                                        REDCAP_SYNC_STATUS_DATAELEMENT_UID,
                                    "value": "true",
                                }
                            ],
                        }

                        try:
                            update_eventDataValue_in_dhis2(
                                DHIS2_BASE_URL,
                                session_get,
                                update_event_payload,
                                event_uid,
                                REDCAP_SYNC_STATUS_DATAELEMENT_UID,
                                event_tei_uid,
                                study_id,
                            )
                        except Exception as exc:
                            log_error(
                                f"REDCap import succeeded, but DHIS2 "
                                f"sync-status update failed for "
                                f"event={event_uid}: {exc}"
                            )

                else:
                    log_error(
                        f"REDCap import not confirmed: "
                        f"study_id={study_id}, date={event_date}, "
                        f"sample_type={sample_type}, "
                        f"response={redcap_result}. "
                        f"DHIS2 sync status was not updated."
                    )

            except (requests.RequestException, ValueError, TypeError) as exc:
                log_error(
                    f"REDCap submission failed: study_id={study_id}, "
                    f"date={event_date}, sample_type={sample_type}: "
                    f"{exc}. DHIS2 sync status was not updated."
                )
            
    # Do not mark the DHIS2 events as synced.


        # Submit redcap_payload ONCE using your existing REDCap
        # API submission function.
        #
        # Only update DHIS2 sync status after REDCap confirms
        # that this combined record was imported successfully.
        #     

    print("-" * 100)
    log_info("-" * 100)


if __name__ == "__main__":
    main()