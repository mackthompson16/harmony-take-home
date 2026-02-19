Implement the purchase order class:
    state: str // PENDING → RUNNING → SUCCESS | FAILED
    req: parsed_json

Implement the DAG execution:
    process all purchase orders in dependency order.
    workflow must stop on first failed purchase order.

Database must support:  create, upsert, query
    must manage the state transitions of the purchase orders. 

Produce alerts if failed or success
    test<n>/alerts.json

Read PO email → Extract PO fields → Upsert PO row → Check if needs attention → Write po_alert.json