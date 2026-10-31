DOMAIN = "cepik_historia_pojazdu"

CONF_REGISTRATION = "registration_number"
CONF_VIN = "vin"
CONF_FIRST_REGISTRATION = "first_registration_date"
CONF_VEHICLE_ID = "vehicle_id"

API_BASE = "https://moj.gov.pl/nforms/api/HistoriaPojazdu/1.1.0"
ENGINE_URL = "https://moj.gov.pl/nforms/engine/ng/index?xFormsAppName=HistoriaPojazdu"
VEHICLE_URL = f"{API_BASE}/data/vehicle-data"
TIMELINE_URL = f"{API_BASE}/data/timeline-data"

UPDATE_INTERVAL_HOURS = 24

PLATFORMS = ["sensor", "binary_sensor"]