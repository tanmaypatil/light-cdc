# Change data capture agent

## Objective 
Objective is to capture change data into business tables into dev or qa environments.
These are low volume tables but slight change results into side effects into application. 
* capture change data at periodic interval ( e.g 30 mins )
* Allow user to rollback a specific change .


## Tech stack 
*  target database - postgres for proof of concept ( oracle - final )
*  language - python 
*  User interface - React 
*  Snapshot store - sqlite

## History 
* Keep history only for specified days or when change data becomes over threshold.

