# SoBi (Social Bicycles) API Reference — Hamilton Bike Share

Compiled from the official (public, unauthenticated) Swagger docs at
`https://app.socialbicycles.com/developer` and `https://app.socialbicycles.com` (API root),
plus live probes against the production API on 2026-08-04.

## Base URL
```
https://app.socialbicycles.com/api
```
All requests over HTTPS. JSON responses only. CORS enabled.

## Authentication

### HTTP Basic (confirmed live)
`Authorization: Basic base64(email:password)`

Verified against production: a bogus-credential request returned
`{"error":"Not Authenticated","code":401}` — a real, correctly-formed JSON
error (not a dead/404 route), confirming this auth path is still active
despite the docs' 2014 deprecation notice.

### OAuth 2 (documented as "preferred", but partially dead)
- App registration: `/applications/register` (requires login)
- Authorized apps management: `/oauth/authorized_applications`
- `/oauth/authorize` returns 200 (route exists)
- `/oauth/token` returns **404** — the classic Doorkeeper token path is gone/renamed.
  If you want OAuth instead of Basic, the real token path would need to be pulled from
  the decompiled app's Retrofit/OkHttp interceptor code (this is exactly the kind of
  thing to paste from JADX output — the app must call *some* token endpoint).

### Required headers (per docs, not currently enforced)
- `Application-Name`
- `Application-Version`

### Rate limit
100 calls/day per app (UTC), by default. Contact `api@socialbicycles.com` to raise it.

### Error format
```json
{"error": "error text", "code": 401}
```

---

## Full Endpoint Map

### areas
| Method | Path | Notes |
|---|---|---|
| GET | `/areas.json` | `network_ids` (query, array) |
| GET | `/areas/{id}.json` | |

### bikes
| Method | Path | Notes |
|---|---|---|
| GET | `/bikes.json` | `latitude`, `longitude`, `coordinates`, `network_id`, `page`, `per_page`, `sort`, `outside_hub`, `hub_id`, `collapsed`, `exclude_attributes` |
| POST | `/bikes/{bike_id}/book_bike.json` | `ble_uuid`, `unlock_bike` (bool), `user_position` |
| POST | `/bikes/rent.json` | `bike_identifier_type` [id\|qr_code\|qr_id\|license_plate], `bike_identifier`, `ble_uuid`, `unlock_bike`, `user_position` |
| POST | `/bikes/{bike_id}/report_issue.json` | `problems`, `description` |
| GET | `/bikes/{bike_id}.json` | |

### bike (singular — current/active bike)
| Method | Path | Notes |
|---|---|---|
| GET | `/bike.json` | `bike_identifier_type`, `bike_identifier` |

### friends
| Method | Path | Notes |
|---|---|---|
| GET | `/friends.json` | `page`, `per_page` |

### hubs
| Method | Path | Notes |
|---|---|---|
| GET | `/hubs.json` | `network_id`, `filter` (hungry\|priority\|full), `latitude`, `longitude`, `coordinates`, `sort`, `page`, `per_page`, `exclude_attributes` |
| POST | `/hubs/{hub_id}/book_bike.json` | `ble_uuid`, `unlock_bike`, `user_position` |
| POST | `/hubs/{hub_id}/book_vehicle.json` | `ble_uuid`, `unlock_vehicle`, `user_position` |
| GET | `/hubs/{hub_id}.json` | `exclude_attributes` |

### networks
| Method | Path | Notes |
|---|---|---|
| GET | `/networks.json` | `subscribed` (bool) |
| GET | `/networks/{network_id}/areas.json` | |
| GET | `/networks/{network_id}/special_areas.json` | |
| GET | `/networks/{network_id}/hubs.json` | same params as `/hubs.json` |
| GET | `/networks/{network_id}/vehicle_types.json` | |
| GET | `/networks/{network_id}/bikes.json` | |
| GET | `/networks/{network_id}/vehicles.json` | |
| DELETE | `/networks/{network_id}/unsubscribe.json` | `reason` |
| POST | `/networks/{network_id}/accept_terms_of_service.json` | |
| GET | `/networks/{network_id}/subscription.json` | |
| GET | `/networks/{network_id}/system_hours.json` | |
| GET | `/networks/{network_id}.json` | |
| PATCH | `/networks/{network_id}/enable_auto_renewal.json` | |
| PATCH | `/networks/{network_id}/disable_auto_renewal.json` | |

### rentals
| Method | Path | Notes |
|---|---|---|
| GET | `/rentals.json` | `network_id`, `bike_id`, `page`, `per_page` |
| GET | `/rentals/current.json` | `network_id`, `latitude`, `longitude` |
| DELETE | `/rentals/cancel.json` | cancels active rental |
| GET | `/rentals/{rental_id}.json` | |
| PATCH | `/rentals/{rental_id}/unlock.json` | **remote unlock** — `bike_identifier_type`, `vehicle_identifier_type`, `bike_identifier`, `vehicle_identifier`, `user_position` |

### rfids
| Method | Path | Notes |
|---|---|---|
| GET | `/rfids.json` | `page`, `per_page` |
| POST | `/rfids.json` | `uid`, `name` |
| PATCH | `/rfids/{rfid_id}.json` | `name` |
| DELETE | `/rfids/{rfid_id}.json` | |

### routes
| Method | Path | Notes |
|---|---|---|
| GET | `/routes.json` | trip history |
| GET | `/routes/{route_id}.json` | |
| PATCH | `/routes/{route_id}.json` | |

### search
| Method | Path | Notes |
|---|---|---|
| GET | `/search.json` | `query`, `all_networks` (bool) — searches friends/bikes/etc |

### subscriptions
| Method | Path | Notes |
|---|---|---|
| GET | `/subscriptions.json` | user's plan/membership state per network |

### users
| Method | Path | Notes |
|---|---|---|
| PATCH | `/users/update_info.json` | `first_name`, `last_name`, `email`, `pin_code`, `locale`, `timezone_name`, `zip_code`, `phone_number`, `privacy_default_sobi`, `privacy_non_friends_view`, `privacy_hide_from_search_results`, `units_of_measurement`, `skip_pin_on_rfid_booking` |
| PATCH | `/users/update_email.json` | `email`, `password` |
| PATCH | `/users/update_password.json` | `password`, `old_password` |
| GET | `/users/me.json` | current user profile |

### invoices
| Method | Path | Notes |
|---|---|---|
| GET | `/invoices.json` | |
| GET | `/invoices/{invoice_id}.json` | |
| POST | `/invoices/{invoice_id}/pay.json` | |

### vehicles / vehicle
| Method | Path | Notes |
|---|---|---|
| GET | `/vehicles.json` | same filters as `/bikes.json` |
| POST | `/vehicles/rent.json` | same shape as `/bikes/rent.json` |
| POST | `/vehicles/{vehicle_id}/report_issue.json` | |
| GET | `/vehicles/{vehicle_id}.json` | |
| GET | `/vehicle.json` | current/active vehicle |

---

## Notes for building a companion app

- `bikes.json` and `hubs.json` support lat/long + bounding-box (`coordinates`) queries — good for a live map.
- The unlock flow is: rent (`POST /bikes/rent.json` or `/hubs/{id}/book_bike.json`) → then `PATCH /rentals/{rental_id}/unlock.json` if `unlock_bike` wasn't already true on booking.
- `GET /rentals/current.json` is the poll-able "do I have an active rental" check for a widget/watch app.
- **Hamilton's `network_id` is `24`** (confirmed via `GET /networks.json?subscribed=true`), now defaulted in `sobi_client.py`'s `hubs`/`bikes` commands.
  - City: `Hamilton, ON`, timezone `America/New_York`, currency `CAD`
  - Center point: `43.2554, -79.8698`
  - Payment gateway: `BraintreeMobilityCloudGateway`
  - `supports_scan_to_unlock: true` — the app likely does QR/barcode scan-to-unlock in addition to BLE
  - `has_ebikes: false`
- If you want true OAuth2 (for something like a public-facing web app where you can't ask users for raw passwords), the real token endpoint needs to come from the decompiled APK — paste the Retrofit/OkHttp auth interceptor and I'll map it in.
- `sobi_client.py` now also covers `rent-from-hub` (books whatever bike is at a station via `book_bike`), `report-issue`, `rfids`/`rfid-add`/`rfid-rename`/`rfid-delete`, `routes`/`route` (trip history, read-only — the API doc doesn't specify what `PATCH /routes/{id}.json` actually accepts, so that's left unimplemented), `search`, `subscriptions`, and `invoices`/`invoice`/`invoice-pay`. Still unimplemented: `areas`, `book_vehicle`/vehicle endpoints (moot — Hamilton's `has_ebikes: false`), and the `users` update endpoints.
