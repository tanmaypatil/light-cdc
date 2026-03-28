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

## Schema introspection
 * In dev and qa environments, tables already exist — the CDC agent must NOT create them.
 * Column names and data types must be read from the existing database schema at runtime.
 * The DAL must expose a schema introspection method (e.g. fetch_table_schema) that returns column names and types.
 * This is used by the diff engine, rollback engine, and UI diff viewer.
 
## History 
* History would be per environment .  
* Keep history only for specified days or when change data becomes over threshold.
* would also want handle to completely purge the history for a env name

## test harness
  * Use a small, curated seed dataset — not randomly generated data.
  * Tables to seed: accounts, customers, rules, memberships (and similar business tables).
  * Only a few records per table are needed — enough to observe CDC capturing inserts, updates, and deletes.
  * Periodic updates to these records simulate real change activity for testing.

## Deployment
  * Target deployment is Azure Kubernetes Service ( AKS ) with a full CI/CD pipeline.
  * Must also support local development and testing ( e.g. via docker-compose or running services directly ).
  * This tool is scoped to dev and qa environments only — not production application environments.

