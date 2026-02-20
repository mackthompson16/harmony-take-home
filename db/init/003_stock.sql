CREATE TABLE IF NOT EXISTS inventory_items (
    sku TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    available_qty INTEGER NOT NULL CHECK (available_qty >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_order_stock_usage (
    po_number TEXT NOT NULL,
    sku TEXT NOT NULL REFERENCES inventory_items(sku) ON DELETE CASCADE,
    reserved_qty INTEGER NOT NULL CHECK (reserved_qty >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (po_number, sku)
);

INSERT INTO inventory_items (sku, description, available_qty) VALUES
    ('label_roll', 'General label rolls', 5000),
    ('sleeve_pack', 'Shrink sleeve packs', 3000),
    ('neck_band', 'Tamper neck bands', 4000),
    ('generic_label', 'Fallback label stock', 2000)
ON CONFLICT (sku) DO NOTHING;
