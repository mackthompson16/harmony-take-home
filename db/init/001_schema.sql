CREATE TABLE IF NOT EXISTS purchase_orders (
    id BIGSERIAL PRIMARY KEY,
    po_number TEXT NOT NULL UNIQUE,
    vendor TEXT,
    ship_to_name TEXT,
    ship_to_address TEXT,
    order_date DATE,
    due_date DATE,
    payment_terms TEXT,
    subtotal NUMERIC(12, 2),
    tax_rate TEXT,
    tax_amount NUMERIC(12, 2),
    shipping_amount NUMERIC(12, 2),
    total_amount NUMERIC(12, 2),
    subject TEXT,
    sender_email TEXT,
    recipient_email TEXT,
    email_date TEXT,
    is_urgent BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT[] NOT NULL DEFAULT '{}',
    contact_name TEXT,
    contact_title TEXT,
    contact_company TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_order_line_items (
    id BIGSERIAL PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    item_no INTEGER NOT NULL,
    description TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_price NUMERIC(12, 2) NOT NULL,
    line_total NUMERIC(12, 2) NOT NULL,
    UNIQUE (purchase_order_id, item_no)
);

CREATE TABLE IF NOT EXISTS po_alerts (
    id BIGSERIAL PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    po_number TEXT NOT NULL,
    reasons TEXT[] NOT NULL,
    fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_purchase_orders_updated_at ON purchase_orders;
CREATE TRIGGER trg_purchase_orders_updated_at
BEFORE UPDATE ON purchase_orders
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION upsert_purchase_order(payload JSONB)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    po_id BIGINT;
BEGIN
    INSERT INTO purchase_orders (
        po_number,
        vendor,
        ship_to_name,
        ship_to_address,
        order_date,
        due_date,
        payment_terms,
        subtotal,
        tax_rate,
        tax_amount,
        shipping_amount,
        total_amount,
        subject,
        sender_email,
        recipient_email,
        email_date,
        is_urgent,
        notes,
        contact_name,
        contact_title,
        contact_company,
        contact_phone,
        contact_email,
        raw_payload
    )
    VALUES (
        payload #>> '{purchase_order,po_number}',
        payload #>> '{purchase_order,vendor}',
        payload #>> '{purchase_order,ship_to,name}',
        payload #>> '{purchase_order,ship_to,full}',
        NULLIF(payload #>> '{purchase_order,order_date}', '')::date,
        NULLIF(payload #>> '{purchase_order,due_date}', '')::date,
        payload #>> '{purchase_order,payment_terms}',
        NULLIF(payload #>> '{purchase_order,totals,subtotal}', '')::numeric,
        payload #>> '{purchase_order,totals,tax,rate}',
        NULLIF(payload #>> '{purchase_order,totals,tax,amount}', '')::numeric,
        NULLIF(payload #>> '{purchase_order,totals,shipping}', '')::numeric,
        NULLIF(payload #>> '{purchase_order,totals,total}', '')::numeric,
        payload #>> '{email,subject}',
        payload #>> '{email,from}',
        payload #>> '{email,to}',
        payload #>> '{email,date}',
        POSITION('urgent' IN LOWER(COALESCE(payload #>> '{email,subject}', ''))) > 0,
        COALESCE(ARRAY(SELECT jsonb_array_elements_text(payload #> '{purchase_order,notes}')), '{}'),
        payload #>> '{purchase_order,contact,name}',
        payload #>> '{purchase_order,contact,title}',
        payload #>> '{purchase_order,contact,company}',
        payload #>> '{purchase_order,contact,phone}',
        payload #>> '{purchase_order,contact,email}',
        payload
    )
    ON CONFLICT (po_number) DO UPDATE
    SET
        vendor = EXCLUDED.vendor,
        ship_to_name = EXCLUDED.ship_to_name,
        ship_to_address = EXCLUDED.ship_to_address,
        order_date = EXCLUDED.order_date,
        due_date = EXCLUDED.due_date,
        payment_terms = EXCLUDED.payment_terms,
        subtotal = EXCLUDED.subtotal,
        tax_rate = EXCLUDED.tax_rate,
        tax_amount = EXCLUDED.tax_amount,
        shipping_amount = EXCLUDED.shipping_amount,
        total_amount = EXCLUDED.total_amount,
        subject = EXCLUDED.subject,
        sender_email = EXCLUDED.sender_email,
        recipient_email = EXCLUDED.recipient_email,
        email_date = EXCLUDED.email_date,
        is_urgent = EXCLUDED.is_urgent,
        notes = EXCLUDED.notes,
        contact_name = EXCLUDED.contact_name,
        contact_title = EXCLUDED.contact_title,
        contact_company = EXCLUDED.contact_company,
        contact_phone = EXCLUDED.contact_phone,
        contact_email = EXCLUDED.contact_email,
        raw_payload = EXCLUDED.raw_payload
    RETURNING id INTO po_id;

    DELETE FROM purchase_order_line_items WHERE purchase_order_id = po_id;

    INSERT INTO purchase_order_line_items (
        purchase_order_id,
        item_no,
        description,
        qty,
        unit_price,
        line_total
    )
    SELECT
        po_id,
        (item->>'item_no')::int,
        item->>'description',
        (item->>'qty')::int,
        (item->>'unit_price')::numeric,
        (item->>'total')::numeric
    FROM jsonb_array_elements(COALESCE(payload #> '{purchase_order,line_items}', '[]'::jsonb)) item;

    RETURN po_id;
END;
$$;
