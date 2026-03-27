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

## Tables to be watched.
 This would be contained in a json called as watch.json in root directory.
 
## History 
* History would be per environment .  
* Keep history only for specified days or when change data becomes over threshold.
* would also want handle to completely purge the history for a env name

## test harness 
 Will also need few inserts and updates happening periodically onto postgres database

## Deployment 
  Would also want to deploy this in azure kubernetes environment ( AKS ) to deploy and test the application.
  need a complete CI/CD pipeline for deploying into AKS .

