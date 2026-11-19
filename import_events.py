#!/usr/bin/env python

from config import config
import requests, json

'''
record = {
    'study_id': 'EB1109W',
    'redcap_event_name': 'ipc_crfs_arm_1',
    'redcap_repeat_instrument': 'microbiology',
    'redcap_repeat_instance': 1,
    #'microbiology_done': 1,
    'sample_date': '2026-08-25',
    #'adm_date_hois': '2026-08-25',
    'sample_type': 2,
    'antibiotic_treatment' : 1,
    #'antibiotic_recode': 9,
    #'sample_type_recode': 5,
    'pathogen_comm_time' : '01:00:00',
    'pathogen_name': 'Enterococcus faecalis',
    'ast_done': 1,
    'ast_date' : '2026-08-31',
    'ast_comm_date': '2026-08-31',
    'ast_comm_time' : '01:00:00',
    'antibiotic_substance_0': 1,
    'antibiotic_substance_name_1': 24,
    'antibiotic_substance_1': 1,
    'microbiology_complete': 2,
}
'''


record =  {
    "study_id": "EB1109W",
    "redcap_event_name": "ipc_crfs_arm_1",
    "redcap_repeat_instrument": "microbiology",
    "redcap_repeat_instance": "2",
    "data_collector_2": "",
    "microbiology_done": "1",
    "sample_date": "2026-08-26",
    "sample_type": "2",
    "sample_type_other": "",
    "receipt_date": "2026-08-26",
    "receipt_time": "02:30",
    "antibiotic_treatment": "0",
    "antibiotic_treatment_0": "1",
    "antibiotic_treatment_1": "8",
    "antibiotic_treatment_2": "",
    "antibiotic_treatment_3": "",
    "antibiotic_treatment_4": "",
    "microscopy_done": "1",
    "microscopy_date": "2026-08-26",
    "microscopy_comm_date": "2026-08-26",
    "microscopy_comm_time": "02:40",
    "microscopy_outcome": "3",
    "microscopy_outcome_other": "",
    "pathogen_id_done": "2",
    "pathogen_id_date": "2026-08-26",
    "pathogen_comm_date": "2026-08-26",
    "pathogen_comm_time": "16:30",
    "pathogen_name": "Enterococcus faecalis",
    "ast_done": "1",
    "ast_date": "2026-08-04",
    "ast_comm_date": "2026-08-26",
    "ast_comm_time": "01:00",
    "antibiotic_substance_0": "1",
    "antibiotic_substance_name_1": "25",
    "antibiotic_substance_name_2": "",
    "antibiotic_substance_name_3": "",
    "antibiotic_substance_name_4": "",
    "antibiotic_substance_1": "1",
    "antibiotic_substance_2": "",
    "antibiotic_substance_3": "",
    "antibiotic_substance_4": "",
    "antibiotic_substance_mic_0": "",
    "antibiotic_substance_mic_name_1": "",
    "antibiotic_substance_mic_name_2": "",
    "antibiotic_substance_mic_name_3": "",
    "antibiotic_substance_mic_name_4": "",
    "antibiotic_substance_mic_1": "",
    "antibiotic_substance_mic_2": "",
    "antibiotic_substance_mic_3": "",
    "antibiotic_substance_mic_4": "",
    "microbiology_complete": "1"
  }
 
data = json.dumps([record])

fields = {
    'token': config['api_token'],
    'content': 'record',
    'action': 'import',
    'format': 'json',
    'returnFormat': 'json',
    'data': data,
    'type': 'flat',
    'overwriteBehavior': "normal",
    'forceAutoNumber':  "false",
}

print(f"red_cap_record {record} ")
print("-" * 75)
print(f"red_cap_fields {fields} ")

#redCapResponse = requests.post(config['api_base_url'],data=fields)
#print('HTTP Status: ' + str(redCapResponse.status_code))
#print(redCapResponse.text)


'''

HTTP Status: 400
{"error":"The following fields were not found in the project as real data fields: microbiology_done, antibiotic_recode, sample_type_recode"}


record = {
    'event_name': 'Event 1',
    'arm_num': 1,
    'day_offset': 0,
    'offset_min': 0,
    'offset_max': 0,
    'unique_event_name': 'event_1_arm_1'
}

data = json.dumps([record])

fields = {
    'token': config['api_token'],
    'content': 'event',
    'action': 'import',
    'format': 'json',
    'override': 0,
    'data': data,
}

r = requests.post(config['api_url'],data=fields)
print('HTTP Status: ' + str(r.status_code))
print(r.text)


## https://chatgpt.com/c/6adb24c3-2494-83ee-8954-f12a4ea080e2
## https://links.hispindia.org/amr_ghana_replica/api/dataElements?fields=id,name,optionSet[id],attributeValues&filter=attributeValues.attribute.id:eq:hM5FycN9l5J&paging=false
## https://links.hispindia.org/amr_ghana_replica/api/options?fields=id,name,code,attributeValues&filter=attributeValues.attribute.id:eq:PLnYjpToQwF&paging=false
## https://links.hispindia.org/amr_ghana_replica/api/options?fields=id,name,code,optionSet[id,name],attributeValues&filter=attributeValues.attribute.id:eq:PLnYjpToQwF&paging=false
## https://links.hispindia.org/amr_ghana_replica/api/tracker/trackedEntities?orgUnit=b3aCK1PTn5S&ouMode=DESCENDANTS&trackedEntityType=osuAV8VCTWd&filter=oLBln17zzdJ:neq:%20&fields=trackedEntity,trackedEntityType,orgUnit,attributes&skipPaging=true
## https://links.hispindia.org/amr_ghana_replica/api/tracker/events?program=ICxr5ByOXkV&programStage=LEaC0JtgaRF&orgUnit=b3aCK1PTn5S&ouMode=DESCENDANTS&filter=bDLtMWyjper:neq:true&fields=event,occurredAt,trackedEntity,orgUnit,program,programStage,dataValues&skipPaging=true

## https://links.hispindia.org/amr_ghana_replica/api/tracker/trackedEntities?program=qlHnTeSDOfP&orgUnit=b3aCK1PTn5S&ouMode=DESCENDANTS&filter=oLBln17zzdJ:neq:%20&fields=trackedEntity,trackedEntityType,orgUnit,attributes&skipPaging=true
## https://links.hispindia.org/amr_ghana_replica/api/tracker/events?trackedEntity=apIaF10rn0k&program=qlHnTeSDOfP&programStage=ZH528YQyn18&fields=event,occurredAt,trackedEntity,orgUnit,program,programStage,dataValues&skipPaging=true

## https://links.hispindia.org/amr_ghana_replica/api/tracker/events.json?trackedEntity=O2LfMA2fzaq&program=ICxr5ByOXkV&programStage=LEaC0JtgaRF&order=updatedAt%3Adesc&fields=trackedEntity%2Cevent%2CorgUnit%2Cprogram%2CprogramStage%2CoccurredAt%2CcreatedAt%2CupdatedAt%2CdataValues%5BdataElement%2Cvalue%5D&skipPaging=true
## https://links.hispindia.org/amr_ghana_replica/api/tracker/events.json?trackedEntity=apIaF10rn0k&program=qlHnTeSDOfP&programStage=ZH528YQyn18&fields=event,occurredAt,trackedEntity,orgUnit,program,programStage,dataValues&skipPaging=true

## https://links.hispindia.org/amr_ghana_replica/api/tracker/events/uG3wg72YlTb.json
## https://your-dhis2-server/api/tracker/events
    ?program=PROGRAM_UID
    &occurredAfter=2026-10-20
    &occurredBefore=2026-10-20
    &filter=AbCdEf12345:eq:123456
    &fields=event,occurredAt,program,programStage,orgUnit,trackedEntity,dataValues
    &pageSize=100

## https://chatgpt.com/c/6ad85417-c248-83ee-b99e-8a67084b1c20    

SELECT
    tei.uid AS tei_uid,teav.value AS study_id,
    psi.uid AS event_uid,psi.executiondate::date AS event_date,
	psi.eventdatavalues
FROM trackedentityinstance tei
INNER JOIN programinstance pi
    ON pi.trackedentityinstanceid = tei.trackedentityinstanceid
INNER JOIN organisationunit org
    ON org.organisationunitid = pi.organisationunitid
INNER JOIN program prg
    ON prg.programid = pi.programid
INNER JOIN programstageinstance psi
    ON psi.programinstanceid = pi.programinstanceid
INNER JOIN programstage ps
    ON ps.programstageid = psi.programstageid
INNER JOIN trackedentityattributevalue teav
    ON teav.trackedentityinstanceid = tei.trackedentityinstanceid
INNER JOIN trackedentityattribute tea
    ON tea.trackedentityattributeid = teav.trackedentityattributeid
WHERE org.path LIKE '%b3aCK1PTn5S%'
    AND prg.uid = 'ICxr5ByOXkV'
    AND ps.uid = 'LEaC0JtgaRF'
    AND tea.uid = 'oLBln17zzdJ'
    AND tei.deleted = FALSE
    AND psi.deleted = FALSE
    AND teav.value IS NOT NULL
    AND (
        psi.eventdatavalues::jsonb -> 'bDLtMWyjper' IS NULL
        OR psi.eventdatavalues::jsonb -> 'bDLtMWyjper' ->> 'value' IS NULL
        OR psi.eventdatavalues::jsonb -> 'bDLtMWyjper' ->> 'value' = ''
    );

'''