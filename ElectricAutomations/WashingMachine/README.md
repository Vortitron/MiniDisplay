Helpers:
input_boolean.washing_machine_cycle_active
input_number.washing_machine_start_power
input_datetime.washing_machine_start_time
input_text.nordpool_price_raw_yesterday
input_boolean.cheap_leccy
Template sensors:
- Nordpool Average Price 1h-5h rolling price averages
Automations:
- Cheap Electricity Indicator (`CheapLeccy.yaml`)