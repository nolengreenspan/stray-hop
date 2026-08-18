#!/usr/bin/env python3
"""
Hamilton Bike Share (SoBi) companion CLI.

Authenticates with HTTP Basic Auth using credentials you type directly into
this terminal (via getpass) -- nothing is sent anywhere except
https://app.socialbicycles.com/api over HTTPS, and no credentials are ever
written to disk or logged.

Usage:
    python sobi_client.py me
    python sobi_client.py nearby --lat 43.2557 --lng -79.8711
    python sobi_client.py find-bike --lat 43.2557 --lng -79.8711 --open
    python sobi_client.py hubs --lat 43.2557 --lng -79.8711
    python sobi_client.py bikes --hub-id 123
    python sobi_client.py rent --bike-id 12345678 --unlock
    python sobi_client.py rent-from-hub --hub-id 123 --unlock
    python sobi_client.py unlock --rental-id 234567
    python sobi_client.py cancel
    python sobi_client.py current
    python sobi_client.py networks
    python sobi_client.py report-issue --bike-id 12345678 --description "flat tire"
    python sobi_client.py rfids
    python sobi_client.py friends
    python sobi_client.py routes
    python sobi_client.py search --query "some friend"
    python sobi_client.py subscriptions
    python sobi_client.py invoices
"""
import argparse
import base64
import getpass
import json
import math
import sys
import webbrowser
import urllib.request
import urllib.parse
import urllib.error

BASE_URL = "https://app.socialbicycles.com/api"
HAMILTON_NETWORK_ID = 24


def get_credentials():
    email = input("SoBi account email: ").strip()
    password = getpass.getpass("SoBi account password (hidden): ")
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return token


def api_request(auth_header, method, path, params=None, data=None):
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})

    body = None
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Application-Name": "sobi-companion-cli",
        "Application-Version": "1.0",
        "Accept": "application/json",
    }
    if data:
        body = urllib.parse.urlencode(data, doseq=True).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"error": str(e), "code": e.code}
        print(json.dumps(err, indent=2), file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: could not reach {BASE_URL} ({e.reason})", file=sys.stderr)
        sys.exit(1)


def cmd_me(args, auth):
    print(json.dumps(api_request(auth, "GET", "/users/me.json"), indent=2))


def cmd_networks(args, auth):
    print(json.dumps(api_request(auth, "GET", "/networks.json", {"subscribed": "true"}), indent=2))


def cmd_hubs(args, auth):
    params = {"network_id": args.network_id, "latitude": args.lat, "longitude": args.lng}
    print(json.dumps(api_request(auth, "GET", "/hubs.json", params), indent=2))


def cmd_bikes(args, auth):
    params = {"network_id": args.network_id, "hub_id": args.hub_id}
    print(json.dumps(api_request(auth, "GET", "/bikes.json", params), indent=2))


def cmd_current(args, auth):
    print(json.dumps(api_request(auth, "GET", "/rentals/current.json"), indent=2))


def cmd_rentals(args, auth):
    print(json.dumps(api_request(auth, "GET", "/rentals.json"), indent=2))


def cmd_nearby(args, auth):
    params = {"network_id": args.network_id, "latitude": args.lat, "longitude": args.lng}
    hubs = api_request(auth, "GET", "/hubs.json", params)
    items = hubs.get("items", hubs) if isinstance(hubs, dict) else hubs
    if not items:
        print("No hubs found.")
        return
    for h in items:
        name = h.get("name", "?")
        bikes = h.get("bikes_count", h.get("available_bikes", "?"))
        free_racks = h.get("free_racks", "?")
        racks = h.get("racks_amount", "?")
        print(f"{name}: {bikes} bikes available, {free_racks}/{racks} docks free")


def confirm(prompt):
    return input(f"{prompt} [y/N]: ").strip().lower() == "y"


def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def maps_directions_url(origin_lat, origin_lng, dest_lat, dest_lng, mode="walking"):
    params = {
        "api": "1",
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "travelmode": mode,
    }
    return "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(params)


def cmd_find_bike(args, auth):
    params = {"network_id": args.network_id, "latitude": args.lat, "longitude": args.lng}
    bikes = api_request(auth, "GET", "/bikes.json", params)
    items = bikes.get("items", bikes) if isinstance(bikes, dict) else bikes
    if not items:
        print("No bikes found.")
        return

    located = []
    for b in items:
        pos = b.get("current_position")
        coords = pos.get("coordinates") if isinstance(pos, dict) else None
        if not coords or len(coords) != 2:
            continue
        bike_lng, bike_lat = coords  # GeoJSON order is [lng, lat]
        dist = haversine_km(args.lat, args.lng, bike_lat, bike_lng)
        located.append((dist, bike_lat, bike_lng, b))

    if not located:
        print("No bikes with known positions found nearby.")
        return

    located.sort(key=lambda t: t[0])
    for dist, bike_lat, bike_lng, b in located[: args.limit]:
        name = b.get("name", b.get("id", "?"))
        state = b.get("state", "unknown")
        url = maps_directions_url(args.lat, args.lng, bike_lat, bike_lng, args.mode)
        print(f"{name} (id={b.get('id')}, state={state}) - {dist * 1000:.0f}m away")
        print(f"  Directions: {url}")

    if args.open:
        _, top_lat, top_lng, _ = located[0]
        webbrowser.open(maps_directions_url(args.lat, args.lng, top_lat, top_lng, args.mode))


def cmd_rent(args, auth):
    if not confirm(f"Rent bike {args.bike_id}? This may start billing per your plan"):
        print("Cancelled.")
        return
    data = {
        "bike_identifier_type": "id",
        "bike_identifier": str(args.bike_id),
        "unlock_bike": "true" if args.unlock else "false",
    }
    if args.lat is not None and args.lng is not None:
        data["user_position"] = f"{args.lat},{args.lng}"
    print(json.dumps(api_request(auth, "POST", "/bikes/rent.json", data=data), indent=2))


def cmd_unlock(args, auth):
    data = {}
    if args.lat is not None and args.lng is not None:
        data["user_position"] = f"{args.lat},{args.lng}"
    path = f"/rentals/{args.rental_id}/unlock.json"
    print(json.dumps(api_request(auth, "PATCH", path, data=data), indent=2))


def cmd_cancel(args, auth):
    if not confirm("Cancel your active rental?"):
        print("Cancelled.")
        return
    print(json.dumps(api_request(auth, "DELETE", "/rentals/cancel.json"), indent=2))


def cmd_rent_from_hub(args, auth):
    data = {"unlock_bike": "true" if args.unlock else "false"}
    if args.lat is not None and args.lng is not None:
        data["user_position"] = f"{args.lat},{args.lng}"
    path = f"/hubs/{args.hub_id}/book_bike.json"
    print(json.dumps(api_request(auth, "POST", path, data=data), indent=2))


def cmd_report_issue(args, auth):
    data = {"description": args.description}
    if args.problems:
        data["problems"] = args.problems
    path = f"/bikes/{args.bike_id}/report_issue.json"
    print(json.dumps(api_request(auth, "POST", path, data=data), indent=2))


def cmd_rfids(args, auth):
    print(json.dumps(api_request(auth, "GET", "/rfids.json"), indent=2))


def cmd_rfid_add(args, auth):
    data = {"uid": args.uid}
    if args.name:
        data["name"] = args.name
    print(json.dumps(api_request(auth, "POST", "/rfids.json", data=data), indent=2))


def cmd_rfid_rename(args, auth):
    path = f"/rfids/{args.rfid_id}.json"
    print(json.dumps(api_request(auth, "PATCH", path, data={"name": args.name}), indent=2))


def cmd_rfid_delete(args, auth):
    if not confirm(f"Delete RFID {args.rfid_id}?"):
        print("Cancelled.")
        return
    path = f"/rfids/{args.rfid_id}.json"
    print(json.dumps(api_request(auth, "DELETE", path), indent=2))


def cmd_friends(args, auth):
    params = {"page": args.page, "per_page": args.per_page}
    print(json.dumps(api_request(auth, "GET", "/friends.json", params), indent=2))


def cmd_routes(args, auth):
    print(json.dumps(api_request(auth, "GET", "/routes.json"), indent=2))


def cmd_route(args, auth):
    path = f"/routes/{args.route_id}.json"
    print(json.dumps(api_request(auth, "GET", path), indent=2))


def cmd_search(args, auth):
    params = {"query": args.query, "all_networks": "true" if args.all_networks else None}
    print(json.dumps(api_request(auth, "GET", "/search.json", params), indent=2))


def cmd_subscriptions(args, auth):
    print(json.dumps(api_request(auth, "GET", "/subscriptions.json"), indent=2))


def cmd_invoices(args, auth):
    print(json.dumps(api_request(auth, "GET", "/invoices.json"), indent=2))


def cmd_invoice(args, auth):
    path = f"/invoices/{args.invoice_id}.json"
    print(json.dumps(api_request(auth, "GET", path), indent=2))


def cmd_invoice_pay(args, auth):
    if not confirm(f"Pay invoice {args.invoice_id}? This will charge the payment method on file"):
        print("Cancelled.")
        return
    path = f"/invoices/{args.invoice_id}/pay.json"
    print(json.dumps(api_request(auth, "POST", path), indent=2))


def main():
    parser = argparse.ArgumentParser(description="Hamilton Bike Share (SoBi) companion CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("me", help="Show your account profile").set_defaults(func=cmd_me)
    sub.add_parser("networks", help="List networks you're subscribed to").set_defaults(func=cmd_networks)
    sub.add_parser("current", help="Show your current active rental").set_defaults(func=cmd_current)
    sub.add_parser("rentals", help="List your rental history").set_defaults(func=cmd_rentals)

    p_hubs = sub.add_parser("hubs", help="List hubs/stations")
    p_hubs.add_argument("--network-id", type=int, default=HAMILTON_NETWORK_ID)
    p_hubs.add_argument("--lat", type=float, default=43.2554)
    p_hubs.add_argument("--lng", type=float, default=-79.8698)
    p_hubs.set_defaults(func=cmd_hubs)

    p_bikes = sub.add_parser("bikes", help="List available bikes")
    p_bikes.add_argument("--network-id", type=int, default=HAMILTON_NETWORK_ID)
    p_bikes.add_argument("--hub-id", type=int)
    p_bikes.set_defaults(func=cmd_bikes)

    p_nearby = sub.add_parser("nearby", help="Human-readable hub availability near a point")
    p_nearby.add_argument("--network-id", type=int, default=HAMILTON_NETWORK_ID)
    p_nearby.add_argument("--lat", type=float, default=43.2554)
    p_nearby.add_argument("--lng", type=float, default=-79.8698)
    p_nearby.set_defaults(func=cmd_nearby)

    p_rent = sub.add_parser("rent", help="Rent a bike by ID")
    p_rent.add_argument("--bike-id", type=int, required=True)
    p_rent.add_argument("--unlock", action="store_true", help="Unlock immediately on booking")
    p_rent.add_argument("--lat", type=float)
    p_rent.add_argument("--lng", type=float)
    p_rent.set_defaults(func=cmd_rent)

    p_unlock = sub.add_parser("unlock", help="Remotely unlock your active rental's bike")
    p_unlock.add_argument("--rental-id", type=int, required=True)
    p_unlock.add_argument("--lat", type=float)
    p_unlock.add_argument("--lng", type=float)
    p_unlock.set_defaults(func=cmd_unlock)

    sub.add_parser("cancel", help="Cancel your active rental").set_defaults(func=cmd_cancel)

    p_rent_hub = sub.add_parser("rent-from-hub", help="Rent whatever bike is available at a hub/station")
    p_rent_hub.add_argument("--hub-id", type=int, required=True)
    p_rent_hub.add_argument("--unlock", action="store_true", help="Unlock immediately on booking")
    p_rent_hub.add_argument("--lat", type=float)
    p_rent_hub.add_argument("--lng", type=float)
    p_rent_hub.set_defaults(func=cmd_rent_from_hub)

    p_report = sub.add_parser("report-issue", help="Report a problem with a bike")
    p_report.add_argument("--bike-id", type=int, required=True)
    p_report.add_argument("--problems", nargs="+", help="One or more problem codes")
    p_report.add_argument("--description", default="")
    p_report.set_defaults(func=cmd_report_issue)

    sub.add_parser("rfids", help="List your registered RFID cards").set_defaults(func=cmd_rfids)

    p_rfid_add = sub.add_parser("rfid-add", help="Register a new RFID card")
    p_rfid_add.add_argument("--uid", required=True)
    p_rfid_add.add_argument("--name")
    p_rfid_add.set_defaults(func=cmd_rfid_add)

    p_rfid_rename = sub.add_parser("rfid-rename", help="Rename a registered RFID card")
    p_rfid_rename.add_argument("--rfid-id", type=int, required=True)
    p_rfid_rename.add_argument("--name", required=True)
    p_rfid_rename.set_defaults(func=cmd_rfid_rename)

    p_rfid_delete = sub.add_parser("rfid-delete", help="Delete a registered RFID card")
    p_rfid_delete.add_argument("--rfid-id", type=int, required=True)
    p_rfid_delete.set_defaults(func=cmd_rfid_delete)

    p_friends = sub.add_parser("friends", help="List your friends on the network")
    p_friends.add_argument("--page", type=int, default=1)
    p_friends.add_argument("--per-page", type=int, default=25)
    p_friends.set_defaults(func=cmd_friends)

    sub.add_parser("routes", help="Show your trip history").set_defaults(func=cmd_routes)

    p_route = sub.add_parser("route", help="Show a single trip's details")
    p_route.add_argument("--route-id", type=int, required=True)
    p_route.set_defaults(func=cmd_route)

    p_search = sub.add_parser("search", help="Search friends/bikes/etc across the network")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--all-networks", action="store_true")
    p_search.set_defaults(func=cmd_search)

    sub.add_parser("subscriptions", help="Show your plan/membership state per network").set_defaults(func=cmd_subscriptions)

    sub.add_parser("invoices", help="List your invoices").set_defaults(func=cmd_invoices)

    p_invoice = sub.add_parser("invoice", help="Show a single invoice")
    p_invoice.add_argument("--invoice-id", type=int, required=True)
    p_invoice.set_defaults(func=cmd_invoice)

    p_invoice_pay = sub.add_parser("invoice-pay", help="Pay an invoice (charges the payment method on file)")
    p_invoice_pay.add_argument("--invoice-id", type=int, required=True)
    p_invoice_pay.set_defaults(func=cmd_invoice_pay)

    p_find = sub.add_parser("find-bike", help="Find nearest available bikes + Google Maps directions")
    p_find.add_argument("--network-id", type=int, default=HAMILTON_NETWORK_ID)
    p_find.add_argument("--lat", type=float, required=True, help="Your current latitude")
    p_find.add_argument("--lng", type=float, required=True, help="Your current longitude")
    p_find.add_argument("--limit", type=int, default=3, help="How many nearest bikes to show")
    p_find.add_argument("--mode", default="walking", choices=["walking", "bicycling", "driving", "transit"])
    p_find.add_argument("--open", action="store_true", help="Open directions to the nearest bike in your browser")
    p_find.set_defaults(func=cmd_find_bike)

    args = parser.parse_args()
    auth = get_credentials()
    args.func(args, auth)


if __name__ == "__main__":
    main()
