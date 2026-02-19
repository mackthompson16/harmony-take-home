SELECT
    wr.id,
    wr.state,
    wr.started_at,
    wr.finished_at,
    wr.error_message
FROM workflow_runs wr
ORDER BY wr.id DESC
LIMIT 10;

SELECT
    por.id,
    por.workflow_run_id,
    por.test_name,
    por.po_number,
    por.state,
    por.attempts,
    por.error_message,
    por.updated_at
FROM purchase_order_runs por
ORDER BY por.id DESC
LIMIT 50;

SELECT
    h.purchase_order_run_id,
    h.from_state,
    h.to_state,
    h.changed_at,
    h.error_message
FROM purchase_order_run_state_history h
ORDER BY h.id DESC
LIMIT 100;
