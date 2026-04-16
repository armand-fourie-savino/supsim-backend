WITH stock_summary AS (

    SELECT 
        m.customer_id,
        m.stock_code,
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
        END AS stock_status,
        RANK() OVER (PARTITION BY m.customer_id ORDER BY m.burn_rate_30d DESC) AS movement_rank,
        COUNT(m.stock_code) OVER (PARTITION BY m.customer_id) AS total_stock_codes,
        SUM(m.burn_rate_30d) OVER (PARTITION BY m.customer_id) AS total_burn_rate_30d

    FROM supsim.movement_metrics AS m

    WHERE m.customer_id = '{customer_id}'
    AND m.current_data = 1
    AND (
        m.stock_on_hand > 0
        OR
        m.burn_rate_90d > 0
    )

)

SELECT 
    ss.customer_id,
    ss.stock_code,
    ss.stock_on_hand,
    ss.burn_rate_90d,
    ss.burn_rate_60d,
    ss.burn_rate_30d,
    ss.burn_rate_7d,
    ss.coverage,
    ss.stock_status,
    ss.movement_rank,
    ss.total_stock_codes,
    ss.total_burn_rate_30d,
    ss.burn_rate_30d / ss.total_burn_rate_30d AS burn_percentage,
    CASE 
        WHEN ss.burn_rate_30d > 10 THEN 'FAST'
        WHEN ss.burn_rate_30d > 3 THEN 'NORMAL'
        WHEN ss.burn_rate_30d > 0 THEN 'SLOW'
        ELSE 'NOT_MOVING'
    END AS movement_status


FROM stock_summary AS ss

ORDER BY ss.burn_rate_30d DESC

