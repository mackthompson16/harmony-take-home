SELECT
    i.sku,
    i.description,
    i.available_qty,
    i.updated_at
FROM inventory_items i
ORDER BY i.sku;

SELECT
    u.po_number,
    u.sku,
    u.reserved_qty,
    u.updated_at
FROM purchase_order_stock_usage u
ORDER BY u.updated_at DESC, u.po_number, u.sku;
