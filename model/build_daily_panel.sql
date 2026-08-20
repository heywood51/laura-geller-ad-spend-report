WITH
parameters AS (
  SELECT DATE '2025-01-01' AS start_date, DATE '2026-07-27' AS end_date
),
geographies AS (
  SELECT geo
  FROM UNNEST(['United States', 'United Kingdom', 'Canada', 'Australia', 'Ireland', 'Germany']) AS geo
),
calendar AS (
  SELECT date, geo
  FROM parameters,
  UNNEST(GENERATE_DATE_ARRAY(start_date, end_date)) AS date
  CROSS JOIN geographies
),
business AS (
  SELECT
    date,
    country AS geo,
    MAX(SAFE_CAST(REGEXP_EXTRACT(promo_amount, r'(\d+)') AS FLOAT64) / 100.0) AS promo_depth,
    MAX(CAST(IFNULL(promo_is_gwp, FALSE) AS INT64)) AS promo_gwp,

    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) IN ('social - facebook', 'paid social - facebook'), IFNULL(ad_spend, 0), 0)) AS spend_Meta,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(search|shopping|pmax) - google$'), IFNULL(ad_spend, 0), 0)) AS spend_GoogleSearch,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) IN ('social - tiktok shop', 'paid social - tiktok shop'), IFNULL(ad_spend, 0), 0)) AS spend_TikTokShop,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(search|shopping|pmax|paid search) - bing$'), IFNULL(ad_spend, 0), 0)) AS spend_Bing,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) IN ('app - applovin', 'paid app - applovin'), IFNULL(ad_spend, 0), 0)) AS spend_AppLovin,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) IN ('social - pinterest', 'paid social - pinterest'), IFNULL(ad_spend, 0), 0)) AS spend_Pinterest,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) IN ('discovery - rokt', 'paid discovery - rokt'), IFNULL(ad_spend, 0), 0)) AS spend_Rokt,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) IN ('social - tiktok', 'paid social - tiktok'), IFNULL(ad_spend, 0), 0)) AS spend_TikTokSocial,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND LOWER(subchannel) = 'television', IFNULL(ad_spend, 0), 0)) AS spend_Television,
    SUM(IF(new_vs_repeat = 'Total (spend)' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(video|demand gen) - youtube$'), IFNULL(ad_spend, 0), 0)) AS spend_YouTube,

    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - facebook', 'paid social - facebook'), IFNULL(orders_new, 0), 0)) AS orders_Meta,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(search|shopping|pmax) - google$'), IFNULL(orders_new, 0), 0)) AS orders_GoogleSearch,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - tiktok shop', 'paid social - tiktok shop'), IFNULL(orders_new, 0), 0)) AS orders_TikTokShop,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(search|shopping|pmax|paid search) - bing$'), IFNULL(orders_new, 0), 0)) AS orders_Bing,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('app - applovin', 'paid app - applovin'), IFNULL(orders_new, 0), 0)) AS orders_AppLovin,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - pinterest', 'paid social - pinterest'), IFNULL(orders_new, 0), 0)) AS orders_Pinterest,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('discovery - rokt', 'paid discovery - rokt'), IFNULL(orders_new, 0), 0)) AS orders_Rokt,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - tiktok', 'paid social - tiktok'), IFNULL(orders_new, 0), 0)) AS orders_TikTokSocial,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) = 'television', IFNULL(orders_new, 0), 0)) AS orders_Television,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(video|demand gen) - youtube$'), IFNULL(orders_new, 0), 0)) AS orders_YouTube,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) = 'email', IFNULL(orders_new, 0), 0)) AS orders_CRMEmail,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('sms', 'mms'), IFNULL(orders_new, 0), 0)) AS orders_CRMSMS,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND STARTS_WITH(LOWER(subchannel), 'organic'), IFNULL(orders_new, 0), 0)) AS orders_Organic,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) = 'direct', IFNULL(orders_new, 0), 0)) AS orders_Direct,

    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - facebook', 'paid social - facebook'), IFNULL(gross_revenue, 0), 0)) AS revenue_Meta,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(search|shopping|pmax) - google$'), IFNULL(gross_revenue, 0), 0)) AS revenue_GoogleSearch,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - tiktok shop', 'paid social - tiktok shop'), IFNULL(gross_revenue, 0), 0)) AS revenue_TikTokShop,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(search|shopping|pmax|paid search) - bing$'), IFNULL(gross_revenue, 0), 0)) AS revenue_Bing,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('app - applovin', 'paid app - applovin'), IFNULL(gross_revenue, 0), 0)) AS revenue_AppLovin,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - pinterest', 'paid social - pinterest'), IFNULL(gross_revenue, 0), 0)) AS revenue_Pinterest,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('discovery - rokt', 'paid discovery - rokt'), IFNULL(gross_revenue, 0), 0)) AS revenue_Rokt,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('social - tiktok', 'paid social - tiktok'), IFNULL(gross_revenue, 0), 0)) AS revenue_TikTokSocial,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) = 'television', IFNULL(gross_revenue, 0), 0)) AS revenue_Television,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND REGEXP_CONTAINS(LOWER(subchannel), r'^(video|demand gen) - youtube$'), IFNULL(gross_revenue, 0), 0)) AS revenue_YouTube,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) = 'email', IFNULL(gross_revenue, 0), 0)) AS revenue_CRMEmail,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) IN ('sms', 'mms'), IFNULL(gross_revenue, 0), 0)) AS revenue_CRMSMS,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND STARTS_WITH(LOWER(subchannel), 'organic'), IFNULL(gross_revenue, 0), 0)) AS revenue_Organic,
    SUM(IF(source != 'Total' AND new_vs_repeat = 'New' AND LOWER(subchannel) = 'direct', IFNULL(gross_revenue, 0), 0)) AS revenue_Direct
  FROM `asbeauty-bi-dev.agg_master.custom_sessions_orders_spend`, parameters
  WHERE
    store = 'Laura Geller'
    AND date BETWEEN start_date AND end_date
    AND country IN ('United States', 'United Kingdom', 'Canada', 'Australia', 'Ireland', 'Germany')
  GROUP BY date, geo
),
email AS (
  SELECT aggregate_date AS date, SUM(event_count) AS exposure_CRMEmail
  FROM `asbeauty-bi-dev.klaviyo.fact_klaviyo_metric_daily`, parameters
  WHERE
    aggregate_date BETWEEN start_date AND end_date
    AND channel = 'email'
    AND klaviyo_metric_name = 'Received Email'
  GROUP BY date
),
klaviyo_sms AS (
  SELECT aggregate_date AS date, SUM(event_count) AS exposure_CRMSMS
  FROM `asbeauty-bi-dev.klaviyo.fact_klaviyo_metric_daily`, parameters
  WHERE
    aggregate_date BETWEEN start_date AND LEAST(end_date, DATE '2026-05-27')
    AND channel = 'sms'
    AND klaviyo_metric_name IN ('Received SMS', 'Received Text Message')
  GROUP BY date
),
vibes_sms AS (
  SELECT activity_date AS date, SUM(delivered_messages) AS exposure_CRMSMS
  FROM `asbeauty-bi-dev.vibes.fact_vibes_campaign_performance`, parameters
  WHERE
    activity_date BETWEEN GREATEST(start_date, DATE '2026-05-28') AND end_date
    AND brand = 'Laura Geller'
  GROUP BY date
),
sms AS (
  SELECT date, SUM(exposure_CRMSMS) AS exposure_CRMSMS
  FROM (
    SELECT * FROM klaviyo_sms
    UNION ALL
    SELECT * FROM vibes_sms
  )
  GROUP BY date
)
SELECT
  calendar.date,
  calendar.geo,
  IFNULL(business.promo_depth, 0) AS promo_depth,
  IFNULL(business.promo_gwp, 0) AS promo_gwp,
  IFNULL(business.spend_Meta, 0) AS spend_Meta,
  IFNULL(business.spend_GoogleSearch, 0) AS spend_GoogleSearch,
  IFNULL(business.spend_TikTokShop, 0) AS spend_TikTokShop,
  IFNULL(business.spend_Bing, 0) AS spend_Bing,
  IFNULL(business.spend_AppLovin, 0) AS spend_AppLovin,
  IFNULL(business.spend_Pinterest, 0) AS spend_Pinterest,
  IFNULL(business.spend_Rokt, 0) AS spend_Rokt,
  IFNULL(business.spend_TikTokSocial, 0) AS spend_TikTokSocial,
  IFNULL(business.spend_Television, 0) AS spend_Television,
  IFNULL(business.spend_YouTube, 0) AS spend_YouTube,
  IFNULL(email.exposure_CRMEmail, 0) AS exposure_CRMEmail,
  IFNULL(sms.exposure_CRMSMS, 0) AS exposure_CRMSMS,
  business.* EXCEPT(date, geo, promo_depth, promo_gwp, spend_Meta, spend_GoogleSearch, spend_TikTokShop, spend_Bing, spend_AppLovin, spend_Pinterest, spend_Rokt, spend_TikTokSocial, spend_Television, spend_YouTube)
FROM calendar
LEFT JOIN business USING(date, geo)
LEFT JOIN email USING(date)
LEFT JOIN sms USING(date)
ORDER BY date, geo
