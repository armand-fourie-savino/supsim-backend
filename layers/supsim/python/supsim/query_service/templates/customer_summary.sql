SELECT 
    m.customer_id,
    COUNT(m.stock_code) AS total_stock_codes,
    SUM(m.stock_on_hand) AS total_stock_on_hand,
    AVG(m.burn_rate_30d) AS burn_rate,
    AVG(m.stock_on_hand / m.burn_rate_30d) AS coverage,
    COUNT(
        CASE    
            WHEN m.stock_on_hand / m.burn_rate_30d <= 30 THEN m.stock_code
            ELSE NULL
        END 
    ) AS total_critical_stock,
    COUNT(
        CASE    
            WHEN m.stock_on_hand / m.burn_rate_30d > 30 AND m.stock_on_hand / m.burn_rate_30d <= 60 THEN m.stock_code
            ELSE NULL
        END 
    ) AS total_risk_stock,
    COUNT(
        CASE    
            WHEN m.stock_on_hand / m.burn_rate_30d > 60 AND m.stock_on_hand / m.burn_rate_30d <= 120 THEN m.stock_code
            ELSE NULL
        END 
    ) AS total_healthy_stock,
    COUNT(
        CASE    
            WHEN m.stock_on_hand / m.burn_rate_30d > 120 THEN m.stock_code
            ELSE NULL
        END 
    ) AS total_over_stock

FROM supsim.movement_metrics AS m

WHERE m.customer_id = '{customer_id}'
AND m.current_data = 1
AND (
    m.stock_on_hand > 0
    OR
    m.burn_rate_90d > 0
)