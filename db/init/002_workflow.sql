CREATE TABLE IF NOT EXISTS workflow_runs (
    id BIGSERIAL PRIMARY KEY,
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS purchase_order_runs (
    id BIGSERIAL PRIMARY KEY,
    workflow_run_id BIGINT NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    test_name TEXT NOT NULL,
    po_number TEXT,
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')),
    req JSONB NOT NULL,
    output JSONB,
    attempts INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_order_run_state_history (
    id BIGSERIAL PRIMARY KEY,
    purchase_order_run_id BIGINT NOT NULL REFERENCES purchase_order_runs(id) ON DELETE CASCADE,
    from_state TEXT,
    to_state TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    error_message TEXT
);

CREATE OR REPLACE FUNCTION create_purchase_order_run(
    p_workflow_run_id BIGINT,
    p_test_name TEXT,
    p_po_number TEXT,
    p_req JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    run_id BIGINT;
BEGIN
    INSERT INTO purchase_order_runs (workflow_run_id, test_name, po_number, state, req)
    VALUES (p_workflow_run_id, p_test_name, p_po_number, 'PENDING', p_req)
    RETURNING id INTO run_id;

    INSERT INTO purchase_order_run_state_history (
        purchase_order_run_id,
        from_state,
        to_state
    ) VALUES (run_id, NULL, 'PENDING');

    RETURN run_id;
END;
$$;

CREATE OR REPLACE FUNCTION transition_purchase_order_run(
    p_run_id BIGINT,
    p_new_state TEXT,
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_state TEXT;
BEGIN
    SELECT state INTO current_state
    FROM purchase_order_runs
    WHERE id = p_run_id
    FOR UPDATE;

    IF current_state IS NULL THEN
        RAISE EXCEPTION 'purchase_order_run % not found', p_run_id;
    END IF;

    IF NOT (
        (current_state = 'PENDING' AND p_new_state = 'RUNNING') OR
        (current_state = 'RUNNING' AND p_new_state IN ('SUCCESS', 'FAILED'))
    ) THEN
        RAISE EXCEPTION 'invalid state transition % -> %', current_state, p_new_state;
    END IF;

    UPDATE purchase_order_runs
    SET state = p_new_state,
        error_message = COALESCE(p_error_message, error_message),
        updated_at = NOW()
    WHERE id = p_run_id;

    INSERT INTO purchase_order_run_state_history (
        purchase_order_run_id,
        from_state,
        to_state,
        error_message
    ) VALUES (p_run_id, current_state, p_new_state, p_error_message);
END;
$$;

CREATE OR REPLACE FUNCTION transition_workflow_run(
    p_run_id BIGINT,
    p_new_state TEXT,
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_state TEXT;
BEGIN
    SELECT state INTO current_state
    FROM workflow_runs
    WHERE id = p_run_id
    FOR UPDATE;

    IF current_state IS NULL THEN
        RAISE EXCEPTION 'workflow_run % not found', p_run_id;
    END IF;

    IF NOT (
        (current_state = 'PENDING' AND p_new_state = 'RUNNING') OR
        (current_state = 'RUNNING' AND p_new_state IN ('SUCCESS', 'FAILED'))
    ) THEN
        RAISE EXCEPTION 'invalid workflow transition % -> %', current_state, p_new_state;
    END IF;

    UPDATE workflow_runs
    SET state = p_new_state,
        error_message = COALESCE(p_error_message, error_message),
        finished_at = CASE WHEN p_new_state IN ('SUCCESS', 'FAILED') THEN NOW() ELSE finished_at END
    WHERE id = p_run_id;
END;
$$;
