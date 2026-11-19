# utils.py

import requests
import logging

import requests, json

from datetime import datetime,date
from dotenv import load_dotenv
import os

load_dotenv()

REDCAP_API_BASE_URL = os.getenv("REDCAP_API_BASE_URL")
REDCAP_API_TOKEN = os.getenv("REDCAP_API_TOKEN")

from constants import LOG_FILE


DHIS2_API_URL = os.getenv("DHIS2_API_URL")

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


#Add a global log queue
import queue
log_queue = queue.Queue()

import logging
import queue

log_queue = queue.Queue()

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_queue.put(self.format(record))



def configure_logging():

    #Optional (Advanced, but useful)
    '''
    import sys
    sys.stdout.write = lambda msg: logging.info(msg)
    logging.info(f"[job:{job_id}] step 1")
    '''

    LOG_DIR = "logs"
    #os.makedirs(LOG_DIR, exist_ok=True)

    os.makedirs(LOG_DIR, exist_ok=True)
    assert LOG_DIR != "/" and LOG_DIR != "" #### Never delete outside log folder.

    # Create unique log filename

    log_filename = LOG_FILE

    log_path = os.path.join(LOG_DIR, log_filename)

    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def log_info(message):
    logging.info(message)

def log_error(message):
    logging.error(message)

#################################
## for redcap integration ######

def format_date(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%y-%m-%d")
        formatted_date = date_obj.strftime("%Y-%m-%d")
        return formatted_date
    except ValueError:
        return None

def format_date_yyyy_mm_dd(date_str):
    try:
        #date_str = "14-01-26"
        #dt = datetime.strptime(date_str, "%d-%m-%y")
        #iso_date = dt.strftime("%Y-%m-%d")
        
        date_obj = datetime.fromisoformat(date_str)
        formatted_date = date_obj.strftime("%Y-%m-%d")
        return formatted_date
    except ValueError:
        return None


def get_redcap_dataElement_attribute_value_dict(
    session, dhis2_base_url, attribute_uid
):
    """
    Return:
        data_element_dict: {attribute_value: data_element_uid}
        data_element_list: List of matching data element objects
    """
    response = session.get(
        f"{dhis2_base_url}dataElements",
        params={
            "fields": "id,name,optionSet[id],attributeValues[attribute[id],value]",
            "filter": f"attributeValues.attribute.id:eq:{attribute_uid}",
            "paging": "false"
        }
    )
    
    
    response.raise_for_status()

    data = response.json()
    data_element_dict = {}
    data_element_list = []

    for data_element in data.get("dataElements", []):
        data_element_id = data_element.get("id")
        matched = False

        for attribute in data_element.get("attributeValues", []):
            if attribute.get("attribute", {}).get("id") == attribute_uid:
                
                #key = attribute.get("value")
                key = data_element_id

                if key is not None and attribute.get("value"):
                    #data_element_dict[key] = data_element_id
                    data_element_dict[key] = attribute.get("value")

                    matched = True

        if matched:
            # Option set may be absent for date, text, numeric, etc.
            option_set = data_element.get("optionSet")
            if option_set:
                print(
                    f"{data_element['id']} {data_element['name']} "
                    f"optionSet={option_set['id']}"
                )
            else:
                print(
                    f"{data_element['id']} {data_element['name']} "
                    "has no option set"
                )

            data_element_list.append(data_element)

    return data_element_dict, data_element_list

def get_option_code_attribute_value_dict(session, dhis2_api_url, attribute_uid):
    """
    Return a dictionary mapping (optionSet UID, option code)
    to the attribute value.
    """
    response = session.get(
        f"{dhis2_api_url}options",
        params={
            "fields": "id,name,code,optionSet[id,name],attributeValues",
            "filter": f"attributeValues.attribute.id:eq:{attribute_uid}",
            "paging": "false"
        }
    )

    response.raise_for_status()

    data = response.json()
    option_dict = {}

    for option in data.get("options", []):
        option_code = option.get("code")
        option_set_id = option.get("optionSet", {}).get("id")

        for attribute_value in option.get("attributeValues", []):
            if attribute_value.get("attribute", {}).get("id") == attribute_uid:
                value = attribute_value.get("value")

                if option_code and option_set_id and value is not None:
                    option_dict[(option_set_id, option_code)] = value

    return option_dict

def get_tei_details(session_get, DHIS2_BASE_URL, DHIS2_ORG_UNIT_ID, DHIS2_PROGRAM_ID, SEARCH_TEI_ATTRIBUTE_UID, SEARCH_VALUE):
    

    final_tei_list = []
    tei_search_url = (
        f"{DHIS2_BASE_URL}tracker/trackedEntities.json"
        f"?orgUnit={DHIS2_ORG_UNIT_ID}&ouMode=DESCENDANTS"
        f"&program={DHIS2_PROGRAM_ID}"
        f"&filter={SEARCH_TEI_ATTRIBUTE_UID}:neq:{SEARCH_VALUE}&skipPaging=true"
    )

    #print(tei_search_url)
    print(f"tei_search_url : {tei_search_url}" )
    log_info(f"tei_search_url : {tei_search_url}")
    #response = requests.get(event_search_url, auth=HTTPBasicAuth(dhis2_username, dhis2_password))
    response = session_get.get(tei_search_url)
    
    if response.status_code != 200:
        return []
    
    if response.status_code == 200:
        tei_response_data = response.json()
   
        teis = tei_response_data.get('instances', [])

        print(f"trackedEntityInstances list Size {len(teis) }")
        log_info(f"trackedEntityInstances list Size {len(teis) } ")

        if teis:
            for tei in teis:

                # Convert attributes list into dictionary
                attributes_dict = {
                    #attr["displayName"]: attr.get("value", "")
                    attr["attribute"]: attr.get("value", "")
                    for attr in tei.get("attributes", [])
                }

                
                if (attributes_dict.get(SEARCH_TEI_ATTRIBUTE_UID) ):
                    
                    final_tei_list.append(tei)
                    
                
        return final_tei_list 
    else:
        return []


def get_tei_event_list(
    session_get,
    DHIS2_BASE_URL,
    tei_uid,
    DHIS2_PROGRAM_ID,
    PROGRAM_STAGE_UID,
    REDCAP_SYNC_STATUS_DATAELEMENT_UID
):
    event_new_get_url = (
        f"{DHIS2_BASE_URL.rstrip('/')}/tracker/events.json"
    )

    params = {
        "trackedEntity": tei_uid,
        "program": DHIS2_PROGRAM_ID,
        "programStage": PROGRAM_STAGE_UID,
        "order": "updatedAt:desc",
        "fields": (
            "trackedEntity,event,orgUnit,program,programStage,"
            "occurredAt,createdAt,updatedAt,"
            "dataValues[dataElement,value]"
        ),
        "skipPaging": "true"
    }

    tei_events_list = []

    event_response = session_get.get(
        event_new_get_url,
        params=params
    )
   
    if event_response.status_code != 200:
        print(
            f"Failed to get events for TEI {tei_uid}. "
            f"Status: {event_response.status_code}, "
            f"Response: {event_response.text}"
        )
        return tei_events_list

    all_events_data = event_response.json()
   
    events = all_events_data.get("instances", [])

    for event in events:
        data_values = event.get("dataValues", [])

        sync_status_dv = next(
            (
                dv for dv in data_values
                if dv.get("dataElement")
                == REDCAP_SYNC_STATUS_DATAELEMENT_UID
            ),
            None
        )

        # Missing data element, null value, or blank value
        value = sync_status_dv.get("value") if sync_status_dv else None

        if value is None or str(value).strip() == "" or str(value).strip() == "false":
            tei_events_list.append(event)
            
    return tei_events_list

def get_next_redcap_repeat_instance(study_id):

    params = {
        "token": REDCAP_API_TOKEN,
        "content": "record",
        "format": "json",
        "type": "eav",
        "records[0]": study_id,
        "forms[0]": REDCAP_REPEAT_INSTRUMENT,
        "events[0]": REDCAP_EVENT_NAME,
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
    }

    try:
        response = requests.post(
            REDCAP_API_BASE_URL,
            data=params,
            timeout=60
        )

        print(
            f"REDCap get response rows for study_id {study_id}: {response.text}"
        )
        response.raise_for_status()

        rows = response.json()

        print(
            f"REDCap get record rows for study_id {study_id}: {rows}"
        )
        log_info(
            f"REDCap get record rows for study_id {study_id}: {rows}"
        )

        if not isinstance(rows, list):
            raise ValueError(
                f"Unexpected REDCap export response for "
                f"study_id={study_id}: {rows}"
            )

        used_instances = []

        for row in rows:

            row_id = str(
                row.get("study_id", row.get("record", ""))
            ).strip()

            if row_id != str(study_id).strip():
                continue

            if (
                row.get("redcap_event_name")
                and row.get("redcap_event_name") != REDCAP_EVENT_NAME
            ):
                continue

            if (
                row.get("redcap_repeat_instrument")
                != REDCAP_REPEAT_INSTRUMENT
            ):
                continue

            instance_value = row.get("redcap_repeat_instance")

            if instance_value in (None, ""):
                continue

            try:
                instance_number = int(instance_value)

            except (ValueError, TypeError):
                log_info(
                    f"Ignoring invalid repeat instance "
                    f"{instance_value!r} for study_id={study_id}"
                )
                continue

            if instance_number > 0:
                used_instances.append(instance_number)

        next_instance = max(used_instances, default=0) + 1

        msg = (
            f"REDCap instance lookup: study_id={study_id}, "
            f"existing_instances={sorted(set(used_instances))}, "
            f"next_instance={next_instance}"
        )

        print(msg)
        log_info(msg)

        return next_instance

    except requests.RequestException as exc:
        error_msg = (
            f"REDCap instance lookup failed for "
            f"study_id={study_id}: {exc}"
        )
        print(error_msg)
        log_info(error_msg)
        raise

    except ValueError as exc:
        error_msg = (
            f"Invalid REDCap instance lookup response "
            f"for study_id={study_id}: {exc}"
        )
        print(error_msg)
        log_info(error_msg)
        raise

def push_to_redcap(redcap_payload):
    
    log_info("-" * 100)
    print("-" * 100)

    study_id = redcap_payload["study_id"]

    redcap_repeat_instance = get_next_redcap_repeat_instance(study_id)

    redcap_payload["redcap_repeat_instance"] = redcap_repeat_instance

    data = json.dumps([redcap_payload])

    fields = {
        "token": REDCAP_API_TOKEN,
        "content": "record",
        "action": "import",
        "format": "json",
        "returnFormat": "json",
        "returnContent": "count",
        "data": data,
        "type": "flat",
        "overwriteBehavior": "normal",
        "forceAutoNumber": "false",
    }

    print(f"REDCap record redcap_payload for post : {redcap_payload}")
    log_info(f"REDCap record redcap_payload for post : {redcap_payload}")
    print("-" * 75)

    try:
        response = requests.post(
            REDCAP_API_BASE_URL,
            data=fields
        )

        print(f"HTTP Status: {response.status_code} REDCap response: {response.text} ")
        log_info(f"HTTP Status: {response.status_code} REDCap response: {response.text} ")

        # Raise an exception for HTTP errors.
        response.raise_for_status()

        # Validate the REDCap API response.
        try:
            result = response.json()
            
        except ValueError:
            raise RuntimeError(
                f"REDCap returned invalid JSON: {response.text}"
            )

        # Successful record imports normally return a count or
        # another response according to the requested return format.
        if isinstance(result, dict) and result.get("error"):
            raise RuntimeError(
                f"REDCap import failed: {result['error']}"
            )

        return response

    except requests.RequestException as exc:
        print(f"REDCap request failed: {exc}")
        raise
      
      
def update_eventDataValue_in_dhis2(DHIS2_BASE_URL, session_get, updateEventDataValue, eventUID, dataElementUid,tei_uid, study_id):

    
    event_update_url = f"{DHIS2_BASE_URL}events/{eventUID}/{dataElementUid}"
    
    response = session_get.put(event_update_url, json=updateEventDataValue, headers={"Content-Type": "application/json"})
    
    if response.status_code == 200:
        conflictsDetails   = response.json().get("response", {}).get("conflicts")
        
        impCount = response.json().get("response", {}).get("importCount").get("imported")
        updateCount = response.json().get("response", {}).get("importCount").get("updated")
        ignoreCount = response.json().get("response", {}).get("importCount").get("ignored")
        
        print(f"Events updated successfully. for tei_uid : {tei_uid}, Study_id : {study_id}, updated event : {eventUID}. impCount : {impCount} .updateCount : {updateCount} .ignoreCount : {ignoreCount}")
        logging.info(f"Events updated successfully. for tei_uid : {tei_uid}, Study_id : {study_id}, updated event : {eventUID}. impCount : {impCount} .updateCount : {updateCount} .ignoreCount : {ignoreCount}")
       
    else:
        print(f"Failed to update events. Error: {response.text}")
        logging.error(f"Failed to update events. for tei_uid : {tei_uid}, Study_id : {study_id}, conflictsDetails : {conflictsDetails} .Status code: {response.status_code} .error details: {response.json()} .Error: {response.text}")
