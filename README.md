# Little Lemon API

The backend for the **Little Lemon** restaurant front end (web + mobile). Clients browse the
menu, manage a cart and place orders; staff manage the menu, assign delivery crew and update
delivery status. Roles are Django groups — `manager` and `delivery_crew` — and every endpoint
is scoped by role.

**Stack:** Django 6.0.3 · Django REST Framework 3.18.3 · djoser 2.3.5 (users + token
endpoints) · django-filter 26.2 · django-cors-headers 4.9.0 · SQLite · pipenv.

**Layout:** the whole feature lives in a single Django app, `LittleLemonAPI/`:

| Path | What is in it |
|---|---|
| `LittleLemonAPI/models.py` | `MenuItem`, `CartItem`, `Order`, `OrderItem` |
| `LittleLemonAPI/views.py` | the viewsets, the cart view and the token views |
| `LittleLemonAPI/serializers.py` | request/response shapes |
| `LittleLemonAPI/permissions.py` | `IsManager`, `IsDeliveryCrew`, `IsCustomer` + the two group names |
| `LittleLemonAPI/filters.py` | the query filters for menu items and orders |
| `LittleLemonAPI/pagination.py` | the shared pagination class |
| `LittleLemonAPI/routers.py` | the router that makes the trailing slash optional |
| `LittleLemonAPI/urls.py`, `token_urls.py` | the URL layout |
| `LittleLemonAPI/management/commands/seed_demo.py` | the idempotent demo seeder |

The project package `LittleLemon/` holds `settings.py` (REST framework, djoser, throttling,
CORS) and the root `urls.py` (`/admin/`, `/api/`, `/token/`).

---

## Setup and run

Requires Python 3.14 and [pipenv](https://pipenv.pypa.io/). The `curl` examples further down
pipe their output through [`jq`](https://stedolan.github.io/jq/) for readability — install it
with `apt install jq` or `brew install jq`. Without `jq` the same calls still work; they just
print the raw JSON.

```bash
pipenv install                                  # create the venv and install the locked deps
pipenv run python manage.py migrate             # create the tables and the manager/delivery_crew groups
pipenv run python manage.py seed_demo           # create the demo accounts and the demo menu
pipenv run python manage.py runserver           # http://127.0.0.1:8000
```

`runserver` takes a normal Django port argument, e.g. `pipenv run python manage.py runserver
8000`. The API is then served at `http://127.0.0.1:8000/api/…`.

**`seed_demo` is idempotent and safe to re-run.** It creates the seven accounts and six menu
items if they are missing and otherwise *reconciles* them: passwords, e-mail addresses, staff
flags, group memberships, prices, descriptions and categories are all reset to the seeded values.
Running it after a demo session therefore restores the seeded group memberships (a `manager` who
was demoted mid-demo is a manager again). It never touches the auto-generated ids of rows that
already exist.

Reconciliation is keyed on the **name**: accounts are matched by `username` and menu items by
`name`. A row whose name was changed during a demo is therefore *not* renamed back — the seeder
creates a fresh row under the seeded name instead, and the renamed row stays behind as an extra.

> Do **not** use `seed_demo --reset`. It deletes and recreates rows, which drifts SQLite's
> `AUTOINCREMENT` counters and destroys the deterministic seeded ids (users 1–7, menu items 1–6).

The seeded menu:

| id | Name | Price | Category |
|---|---|---|---|
| 1 | Greek Salad | 8.50 | salads |
| 2 | Lemon Chicken | 13.75 | mains |
| 3 | Veggie Wrap | 7.25 | mains |
| 4 | Lamb Burger | 11.00 | mains |
| 5 | Strawberry Cheesecake | 6.50 | desserts |
| 6 | Iced Tea | 3.00 | drinks |

---

## Seeded accounts

| Username | Password | Role | Notes |
|---|---|---|---|
| `admin` | `AdminPass123!` | superuser (acts as a manager) | also `is_staff`, so it can sign in to `/admin/` |
| `customer1` | `CustomerPass123!` | customer | no group membership |
| `customer2` | `CustomerPass123!` | customer | no group membership |
| `manager1` | `ManagerPass123!` | manager | in the `manager` group |
| `manager2` | `ManagerPass123!` | manager | in the `manager` group |
| `crew1` | `CrewPass123!` | delivery crew | in the `delivery_crew` group |
| `crew2` | `CrewPass123!` | delivery crew | in the `delivery_crew` group |

Managers are deliberately **not** `is_staff` — the `admin` account exists for the Django admin
panel, the `manager` accounts exist for the API. A superuser counts as a manager everywhere the
API checks for one.

---

## Authentication

Token authentication (`rest_framework.authtoken`). All protected endpoints expect the header
`Authorization: Token <key>`.

### Log in

```bash
curl -s -X POST http://127.0.0.1:8000/token/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"customer1","password":"CustomerPass123!"}'
```

```json
{"token": "7181baff61d6984e1f6ac399febaa40950183f7b",
 "auth_token": "7181baff61d6984e1f6ac399febaa40950183f7b"}
```

The response carries the key under **both** `token` and `auth_token` — they are the same
string. `token` is the name most clients expect, `auth_token` is what djoser documents; read
whichever your client code already uses.

`POST /token/login/` answers **200** (not 201) with a successful login, and **400** with wrong
credentials.

### Use the token

```bash
export BASE=http://127.0.0.1:8000
export TOKEN=$(curl -s -X POST "$BASE/token/login/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"manager1","password":"ManagerPass123!"}' | jq -r .token)

curl -s "$BASE/api/menu-items" -H "Authorization: Token $TOKEN"
```

### Who am I?

```bash
curl -s "$BASE/api/users/users/me/" -H "Authorization: Token $TOKEN"
```

```json
{"id": 4, "username": "manager1", "email": "manager1@littlelemon.example",
 "first_name": "", "last_name": "", "groups": ["manager"],
 "is_manager": true, "is_delivery_crew": false}
```

`groups`, `is_manager` and `is_delivery_crew` are additions on top of djoser's stock
`me` response — a client needs them to know which screen to render.

### Log out

```bash
# a token of its own, so the one used by the examples above stays valid
export LOGOUT_TOKEN=$(curl -s -X POST "$BASE/token/login/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"customer2","password":"CustomerPass123!"}' | jq -r .token)

curl -s -o /dev/null -w '%{http_code}\n' -X POST "$BASE/token/logout/" \
  -H "Authorization: Token $LOGOUT_TOKEN"
# 204
```

The token is deleted server-side; the next request with it answers **401**.

---

## Endpoint reference

Status code per role. **Every endpoint answers with and without the trailing slash** — there is
no redirect and no error for either form.

| Request | Customer | Delivery crew | Manager | Anonymous |
|---|---|---|---|---|
| `POST /api/users` | 201 | 201 | 201 | 201 |
| `GET /api/users/users/me/` | 200 | 200 | 200 | 401 |
| `POST /token/login/` | 200 | 200 | 200 | 200 |
| `POST /token/logout/` | 204 | 204 | 204 | 401 |
| `GET /api/categories` | 200 | 200 | 200 | 401 |
| `GET /api/menu-items` | 200 | 200 | 200 | 401 |
| `POST /api/menu-items` | 403 | 403 | **201** | 401 |
| `PUT /api/menu-items` | 403 | 403 | 405 | 401 |
| `PATCH /api/menu-items` | 403 | 403 | 405 | 401 |
| `DELETE /api/menu-items` | 403 | 403 | 405 | 401 |
| `GET /api/menu-items/{id}` | 200 | 200 | 200 | 401 |
| `POST /api/menu-items/{id}` | 403 | 403 | 405 | 401 |
| `PUT /api/menu-items/{id}` | 403 | 403 | **200** | 401 |
| `PATCH /api/menu-items/{id}` | 403 | 403 | **200** | 401 |
| `DELETE /api/menu-items/{id}` | 403 | 403 | **200** | 401 |
| `GET /api/groups/manager/users` | 403 | 403 | **200** | 401 |
| `POST /api/groups/manager/users` | 403 | 403 | **201** | 401 |
| `DELETE /api/groups/manager/users/{userId}` | 403 | 403 | 200 (member) / 404 (not a member) | 401 |
| `GET /api/groups/delivery-crew/users` | 403 | 403 | **200** | 401 |
| `POST /api/groups/delivery-crew/users` | 403 | 403 | **201** | 401 |
| `DELETE /api/groups/delivery-crew/users/{userId}` | 403 | 403 | 200 (member) / 404 (not a member) | 401 |
| `GET /api/cart/menu-items` | 200 | 403 | 403 | 401 |
| `POST /api/cart/menu-items` | 201 | 403 | 403 | 401 |
| `DELETE /api/cart/menu-items` | 200 | 403 | 403 | 401 |
| `GET /api/orders` | 200 (own) | 200 (assigned) | 200 (all) | 401 |
| `POST /api/orders` | **201** | 403 | 403 | 401 |
| `GET /api/orders/{id}` | 200 (own) / 403 (someone else's) | 200 (assigned) / 403 (not assigned) | 200 | 401 |
| `PUT /api/orders/{id}` | 403 | 400 (assigned to them; 403 if assigned to another crew member) | **200** | 401 |
| `PATCH /api/orders/{id}` | 403 | **200** (assigned to them; 403 if not; status only) | **200** | 401 |
| `DELETE /api/orders/{id}` | 403 | 403 | **200** | 401 |

Notes on the table:

* A **customer** is any authenticated user who is in neither the `manager` nor the
  `delivery_crew` group. `admin` is a superuser and therefore counts as a manager.
* `PUT`/`PATCH`/`DELETE` on the **collection** `/api/menu-items` answer **405** for a manager:
  the brief scopes manager writes to the detail route, and there is no bulk-delete semantics to
  invent. A customer or a crew member gets **403** for the same call — the permission check runs
  before the method is resolved, so the refusal wins over the 405.
* `POST /api/menu-items/{id}` answers **405** for a manager: the detail route has no `create`.
* `DELETE /api/groups/.../users/{userId}` answers **404** when the user is unknown or is not in
  that group; it removes the user *from the group only* — the account itself survives.
* A successful `DELETE` answers **200** with a small JSON body (`{"detail": "…"}`), not 204.
* `GET /api/orders/{id}` distinguishes *not found* (**404**) from *not yours* (**403**).
* For the delivery-crew rows of `/api/orders/{id}` the **access check runs first**: a crew member
  who is not the assigned crew member gets **403** for `GET`, `PUT` and `PATCH` alike, before any
  payload rule is applied. Only on an order assigned to them does `PUT` become the **400**
  (`"Delivery crew may only PATCH the 'status' field."`) and `PATCH` the **200**.

### Request and response bodies

`POST /api/users` — `username`, `email` and `password` are required; `name` is an optional alias
stored in `first_name`.

```json
{"username": "alice", "email": "alice@example.com", "password": "S3cret-Pass!", "name": "Alice"}
```

`POST /api/menu-items` — manager only.

```json
{"name": "Greek Salad", "price": "8.50", "description": "…", "category": "salads"}
```

`POST /api/cart/menu-items` — the customer owns the cart, so `user` comes from the token and is
never read from the payload. `quantity` defaults to 1.

```json
{"menu_item_id": 1, "quantity": 2}
```

`POST /api/orders` — empty body; the order is built from the caller's cart. An empty cart is a
**400**.

`PATCH /api/orders/{id}` — manager; `delivery_crew` accepts a username or a numeric user id and
is rejected with **400** if that user is not in the `delivery_crew` group.

```json
{"delivery_crew": "crew1", "status": 0}
```

`PATCH /api/orders/{id}` — delivery crew; `status` only. Any other field is **400**.

```json
{"status": 1}
```

`POST /api/groups/manager/users` — the brief says "assigns the user in the payload", i.e. an
**existing** user is added to the group. `{"user_id": 3}` is accepted as well.

```json
{"username": "alice"}
```

An unknown user is **400**, and so is a user who is already in the group.

---

## Query parameters

### Filtering

`/api/menu-items`

| Param | Effect |
|---|---|
| `category` | exact match (`?category=mains`) |
| `name` | case-insensitive *contains* (`?name=salad`) |
| `search` | alias for `name` (`?search=chicken`) |
| `price_min` | price greater than or equal to (`?price_min=7`) |
| `price_max` | price less than or equal to (`?price_max=9`) |
| `price` | exact price (`?price=8.50`) |

`/api/orders`

| Param | Effect |
|---|---|
| `status` | exact (`0` = pending, `1` = delivered) |
| `delivery_crew` | crew username, case-insensitive (`?delivery_crew=crew1`) |
| `created_after` | ISO-8601 datetime lower bound (`?created_after=2026-10-01T00:00:00Z`) |
| `created_before` | ISO-8601 datetime upper bound |

Order filters are applied to the caller's visible orders, so a customer filtering by `status`
only ever sees their own.

### Ordering

| Endpoint | `ordering` values |
|---|---|
| `/api/menu-items` | `id`, `name`, `price`, `category` |
| `/api/orders` | `id`, `status`, `total`, `created_at` |

Prefix with `-` for descending: `?ordering=price`, `?ordering=-price`,
`?ordering=-created_at`.

### Pagination

Every list endpoint is paginated with `PageNumberPagination`.

| Param | Default | Notes |
|---|---|---|
| `page` | 1 | the page number |
| `page_size` | 10 | the number of rows per page, capped at 100 |

```bash
curl -s "$BASE/api/menu-items?page=1&page_size=3" -H "Authorization: Token $TOKEN"
```

### The list envelope

Every list endpoint answers with the same envelope, so a client writes one list-parsing routine:

```json
{
  "count": 6,
  "next": "http://127.0.0.1:8000/api/menu-items?page=2&page_size=3",
  "previous": null,
  "results": [
    {"id": 1, "name": "Greek Salad", "price": "8.50", "description": "…", "category": "salads"}
  ]
}
```

`count` is the number of matching rows in total, `next`/`previous` are page URLs (`null` at the
ends) and `results` holds the page itself.

---

## Throttling

| Scope | Rate | Applies to |
|---|---|---|
| `anon` | 60 / minute | unauthenticated callers |
| `user` | 300 / minute | authenticated callers, per user |
| `login` | 30 / minute | `POST /token/login/` and `POST /token/logout/` |

A request over the limit is answered with **429 Too Many Requests** and a `Retry-After`
header. The `login` scope is there to slow credential stuffing; it is keyed by IP address, so
a burst of login attempts from one client is the thing that trips it.

---

## Status codes

| Code | Meaning here |
|---|---|
| 200 | the request succeeded (`GET`, `PUT`, `PATCH`, and a successful `DELETE` all answer 200) |
| 201 | a resource was created (`POST /api/users`, `POST /api/menu-items`, `POST /api/cart/menu-items`, `POST /api/orders`, `POST /api/groups/.../users`) |
| 204 | the token was deleted (`POST /token/logout/`) — no body |
| 400 | validation failed: bad body, unknown `menu_item_id`, empty cart at checkout, a crew member sending a field other than `status`, a user that is already in the group, an unknown user in the payload |
| 401 | **not authenticated** — no token, a bad token, or a logged-out token |
| 403 | **authenticated but not allowed** — e.g. a customer trying to create a menu item, a crew member reading the cart, a customer reading somebody else's order |
| 404 | no such resource — an unknown id, or a group member that is not in the group |
| 405 | the verb is not defined for that route (e.g. `DELETE /api/menu-items` on the collection) |
| 429 | the rate limit was hit — wait for the window to pass and retry |

---

## Walkthrough with curl

The main flows, end to end. Set `BASE` once:

```bash
export BASE=http://127.0.0.1:8000
```

### 1. Log in

```bash
export CUSTOMER_TOKEN=$(curl -s -X POST "$BASE/token/login/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"customer1","password":"CustomerPass123!"}' | jq -r .token)

export MANAGER_TOKEN=$(curl -s -X POST "$BASE/token/login/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"manager1","password":"ManagerPass123!"}' | jq -r .token)

export CREW_TOKEN=$(curl -s -X POST "$BASE/token/login/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"crew1","password":"CrewPass123!"}' | jq -r .token)
```

### 2. Browse the menu and the categories

```bash
curl -s "$BASE/api/menu-items" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
curl -s "$BASE/api/categories"  -H "Authorization: Token $CUSTOMER_TOKEN" | jq
curl -s "$BASE/api/menu-items/1" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
```

The second call answers with the distinct categories currently in use:

```json
{"count": 4, "next": null, "previous": null,
 "results": [{"category": "desserts"}, {"category": "drinks"},
             {"category": "mains"}, {"category": "salads"}]}
```

The third call answers with a single menu item:

```json
{"id": 1, "name": "Greek Salad", "price": "8.50",
 "description": "Fresh tomatoes, cucumber, olives and feta cheese.", "category": "salads"}
```

### 3. Filter, sort and paginate

```bash
curl -s "$BASE/api/menu-items?category=mains" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
curl -s "$BASE/api/menu-items?name=salad" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
curl -s "$BASE/api/menu-items?price_min=7&price_max=9" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
curl -s "$BASE/api/menu-items?ordering=price" -H "Authorization: Token $CUSTOMER_TOKEN" | jq '.results[] | {id, price}'
curl -s "$BASE/api/menu-items?ordering=-price" -H "Authorization: Token $CUSTOMER_TOKEN" | jq '.results[] | {id, price}'
curl -s "$BASE/api/menu-items?page=1&page_size=3" -H "Authorization: Token $CUSTOMER_TOKEN" | jq '{count, next, previous}'
```

### 4. Add to the cart

```bash
curl -s -X POST "$BASE/api/cart/menu-items" \
  -H "Authorization: Token $CUSTOMER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"menu_item_id": 1, "quantity": 2}' | jq
```

```json
{"id": 1,
 "menu_item": {"id": 1, "name": "Greek Salad", "price": "8.50", "description": "…", "category": "salads"},
 "quantity": 2, "unit_price": "8.50", "total": "17.00"}
```

```bash
curl -s "$BASE/api/cart/menu-items" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
```

### 5. Place the order

```bash
curl -s -X POST "$BASE/api/orders" \
  -H "Authorization: Token $CUSTOMER_TOKEN" \
  -H 'Content-Type: application/json' -d '{}' | jq
```

```json
{"id": 1, "user": 2, "status": 0, "delivery_crew": null, "delivery_crew_id": null,
 "total": "17.00",
 "order_items": [
   {"id": 1, "menu_item": {"id": 1, "name": "Greek Salad", "price": "8.50", "description": "…", "category": "salads"},
    "quantity": 2, "price": "8.50", "total": "17.00"}],
 "created_at": "2026-10-21T10:00:00Z"}
```

The cart is emptied in the same transaction that creates the order.

```bash
curl -s "$BASE/api/orders" -H "Authorization: Token $CUSTOMER_TOKEN" | jq
```

### 6. Assign the delivery crew and deliver the order

```bash
curl -s -X PATCH "$BASE/api/orders/1" \
  -H "Authorization: Token $MANAGER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"delivery_crew": "crew1", "status": 0}' | jq
```

```bash
curl -s "$BASE/api/orders" -H "Authorization: Token $CREW_TOKEN" | jq
curl -s -X PATCH "$BASE/api/orders/1" \
  -H "Authorization: Token $CREW_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status": 1}' | jq
```

The crew member may send `status` and nothing else; the same call with `"delivery_crew"` in the
payload is a 400. These calls only work on an order **assigned to that crew member** — a crew
member who touches an order assigned to somebody else gets a 403.

### 7. Manage the menu as a manager

```bash
curl -s -X POST "$BASE/api/menu-items" \
  -H "Authorization: Token $MANAGER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name": "Greek Salad Special", "price": "9.99", "description": "With extra feta.", "category": "salads"}' | jq

curl -s -X PATCH "$BASE/api/menu-items/7" \
  -H "Authorization: Token $MANAGER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"description": "The item of the day."}' | jq
```

### 8. Manage the groups as a manager

```bash
curl -s "$BASE/api/groups/manager/users" -H "Authorization: Token $MANAGER_TOKEN" | jq
curl -s -X POST "$BASE/api/groups/manager/users" \
  -H "Authorization: Token $MANAGER_TOKEN" \
  -H 'Content-Type: application/json' -d '{"username": "customer2"}' | jq
curl -s -X DELETE "$BASE/api/groups/manager/users/3" \
  -H "Authorization: Token $MANAGER_TOKEN" | jq
```

---

## Peer-review checklist

The course's 21 grading criteria, each with the call that satisfies it. All of them were
exercised by hand against the running server; the status code in the last column is the
observed one.

| # | Criterion | Satisfied by | Role | Observed |
|---|---|---|---|---|
| 1 | The admin can assign users to the manager group | `POST /api/groups/manager/users` `{"username": "customer2"}` | admin / manager | 201 |
| 2 | You can access the manager group with an admin token | `GET /api/groups/manager/users` | admin / manager | 200 |
| 3 | The admin can add menu items | `POST /api/menu-items` | admin / manager | 201 |
| 4 | The admin can add categories | `POST /api/menu-items` with a new `category` value; the category then shows up in `GET /api/categories` | admin / manager | 201 → 200 |
| 5 | Managers can log in | `POST /token/login/` with `manager1` / `ManagerPass123!` | — | 200 |
| 6 | Managers can update the item of the day | `PUT` / `PATCH /api/menu-items/{id}` | manager | 200 |
| 7 | Managers can assign users to the delivery crew | `POST /api/groups/delivery-crew/users` `{"username": "customer2"}` | manager | 201 |
| 8 | Managers can assign orders to the delivery crew | `PATCH /api/orders/{id}` `{"delivery_crew": "crew1"}` | manager | 200 |
| 9 | The delivery crew can access orders assigned to them | `GET /api/orders` (and `GET /api/orders/{id}`) | delivery crew | 200 |
| 10 | The delivery crew can update an order as delivered | `PATCH /api/orders/{id}` `{"status": 1}` | delivery crew | 200 |
| 11 | Customers can register | `POST /api/users` | anonymous | 201 |
| 12 | Customers can log in using their username and password and get access tokens | `POST /token/login/` → `Authorization: Token <key>` | — | 200 |
| 13 | Customers can browse all categories | `GET /api/categories` | customer | 200 |
| 14 | Customers can browse all the menu items at once | `GET /api/menu-items` | customer | 200 |
| 15 | Customers can browse menu items by category | `GET /api/menu-items?category=mains` | customer | 200 |
| 16 | Customers can paginate menu items | `GET /api/menu-items?page=1&page_size=3` | customer | 200 |
| 17 | Customers can sort menu items by price | `GET /api/menu-items?ordering=price` | customer | 200 |
| 18 | Customers can add menu items to the cart | `POST /api/cart/menu-items` `{"menu_item_id": 1, "quantity": 2}` | customer | 201 |
| 19 | Customers can access previously added items in the cart | `GET /api/cart/menu-items` | customer | 200 |
| 20 | Customers can place orders | `POST /api/orders` (empty body, built from the cart) | customer | 201 |
| 21 | Customers can browse their own orders | `GET /api/orders` | customer | 200 |

Two of these need a word of explanation, because the data model has no separate resource for
them.

**A category is a value on a menu item — there is no `Category` table.** `MenuItem.category` is
a free-text field. A category comes into existence the moment a menu item carries it, and
`GET /api/categories` answers with the distinct, non-empty category values currently in use
(`{"count": 4, "results": [{"category": "desserts"}, …]}`). So "adding a category" (criterion 4)
means creating a menu item with that category; there is no separate category-create endpoint to
call.

**There is no "featured" flag — "the item of the day" is an ordinary menu item.** The model has
no boolean column and no special endpoint for it. "Updating the item of the day" (criterion 6)
means a manager edits the menu item that happens to be the one on offer today, e.g.
`PATCH /api/menu-items/1` with `{"description": "The item of the day."}` — the same call that
updates any other menu item.

---

## Design notes

This project carries **no explanatory comments in the code** on purpose, so the reasoning lives
here.

**`TokenAuthentication` is first in `DEFAULT_AUTHENTICATION_CLASSES`.** DRF answers 401 only when
the first authenticator that fails supplies a `WWW-Authenticate` header, and
`TokenAuthentication` does. If `SessionAuthentication` came first, DRF would treat an anonymous
request as "not permitted" and answer **403** instead of **401** — every anonymous row in the
matrix would be wrong, and a client could not tell "you forgot your token" from "you are not
allowed". Ordering the authenticators is the whole mechanism.

**A successful `DELETE` answers 200, not 204.** Every delete endpoint returns a small JSON body
(`{"detail": "Order 2 was deleted."}`) so the client learns *what* was removed. 204 means "no
content"; here there is content worth having. `POST /token/logout/` is the exception — it is
djoser's endpoint and it answers 204 with an empty body.

**The current user is at `/api/users/users/me/` and registration is at `/api/users`.** The brief
names both paths explicitly, and they are genuinely different resources: `POST /api/users` is
the public registration endpoint (no token needed), while `/api/users/users/me/` is djoser's
`me` action on the user collection. The doubled `users` is not a typo — djoser mounts its user
viewset under a `users` prefix, and the brief's path is that prefix plus the `me` action.
The user viewset is registered on the project's own router rather than through
`include("djoser.urls")`, which is what puts `me` at that path while keeping the collection
rooted at `/api/users`.

**The delivery crew may only `PATCH` the `status` field of an order assigned to them.** Two
restrictions, both enforced: the order must be one this crew member is assigned to (otherwise
403), and the payload must contain nothing but `status` (otherwise 400, with a message naming
the offending fields). `PUT` is refused with 400 as well, because a `PUT` replaces the
resource, and a crew member is not allowed to replace an order. The crew cannot change the
delivery assignment, the total or the line items — that is the manager's job.

**A customer may not write an order at all.** `POST /api/orders` is the customer's only order
write, and it is a *checkout*: the body is empty and the order is built from the customer's
cart. There is no way to post a hand-written order, and no way to edit or delete one — only a
manager can delete an order, and only a manager or the assigned crew can change one.

**The two group names live in `LittleLemonAPI/permissions.py`.** `MANAGER_GROUP = "manager"` and
`DELIVERY_CREW_GROUP = "delivery_crew"` are defined there, next to the `is_manager` /
`is_delivery_crew` / `is_customer` helpers that read them. The seeder, the group viewsets and
the permission classes all import the constants, so the group name is written in exactly one
place. The URL segment is `delivery-crew` (hyphen) while the Django group name is
`delivery_crew` (underscore) — Django's convention for group names.

**`seed_demo` is declarative, so re-running it restores the seeded group memberships.** The
command does not "create the demo users if they are missing and hope for the best"; for every
seeded account it re-asserts the e-mail, the staff/superuser flags, the password and the exact
group set (`user.groups.set([...])`). A demo session that added `customer2` to the `manager`
group is undone by re-running the seeder, and a manager who was demoted is a manager again. It
is safe to run at any time and it never touches the ids of rows that already exist — which is
why `--reset` (which deletes and recreates rows) is off-limits.

**Everything answers with and without the trailing slash.** The brief mixes both forms. Django
raises a 500 for a slash-less `POST` when `DEBUG=True` and `CommonMiddleware` is installed, so
`APPEND_SLASH = False` and a router whose route regexes make the slash optional. One route
serves both forms, so nothing is registered twice and no request is ever redirected.

**There is no automated test suite.** Verification for this project was done by hand, with
`curl`, over every cell of the matrix above. The evidence ships with this README: the
**Endpoint reference** table lists the status code observed for every request × role cell, the
**Peer-review checklist** lists the observed code for each of the 21 grading criteria, and every
example in this document was executed against the running server before it was written down. The
code is deliberately comment-free, so this README and the design document are the documentation.
