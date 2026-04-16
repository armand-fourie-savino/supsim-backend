SELECT 
    m.customer_id,
    m.stock_code,
    m."date",
    m.stock_in,
    m.stock_out,
    m.stock_on_hand,
    m.burn_rate_90d,
    m.burn_rate_60d,
    m.burn_rate_30d,
    m.burn_rate_7d,
    m.stock_on_hand / m.burn_rate_30d AS coverage,
    CASE    
        WHEN m.stock_on_hand / m.burn_rate_30d <= 30 THEN 'CRITICAL_SHORTAGE'
        WHEN m.stock_on_hand / m.burn_rate_30d <= 60 THEN 'SHORTAGE_RISK'
        WHEN m.stock_on_hand / m.burn_rate_30d <= 120 THEN 'HEALTHY'
        WHEN m.stock_on_hand / m.burn_rate_30d > 120 THEN 'OVER_STOCKED'
        ELSE NULL
    END AS stock_status
    
FROM supsim.movement_metrics AS m

WHERE m.customer_id = '{customer_id}'
AND m.stock_code = '{stock_code}'