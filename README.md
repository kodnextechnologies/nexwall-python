# Python Client & CLI for a Free Wallpaper API (NexWall)

`nexwall` is a tiny Python client and command-line tool for the [NexWall **free wallpaper API**](https://nexwall.kodnextech.com/wallpaper-api/free-wallpaper-api). List categories, search and page through wallpapers, grab a random wallpaper, download it, and change your desktop wallpaper every day on Windows, macOS or Linux. One dependency (`requests`) and two short modules you can read in a few minutes.

> Step-by-step tutorial: [Python wallpaper automation guide](https://nexwall.kodnextech.com/wallpaper-api/guides/python-wallpaper-automation-guide)

## Features

- Small client class covering every v1 endpoint: categories, wallpapers (paging, category, tag search, sort, type), category wallpapers, wallpaper by id
- `random()` helper: one request with `sort=random`
- `download()` streams the full-size image to a file or folder (the API key is never sent to the image host)
- Typed exceptions: `AuthError` (401), `NotFoundError` (404), `ValidationError` (422), `RateLimitError` (429, with `retry_after`)
- Tracks `plan`, `remaining_requests_today` and the `X-RateLimit-*` headers after each call
- CLI: `nexwall categories | list | random | get`, with `--json` output and `--download`
- Example script: **daily desktop wallpaper changer** for Windows, macOS, GNOME, KDE Plasma, XFCE, Cinnamon and feh
- Offline unit tests (mocked HTTP, no key needed)

## What it does

```console
$ nexwall categories
    5  Nature                      412 wallpapers
   ...

$ nexwall random --category 5 --download ./wall.jpg
   10234  3840x2160    Nature                https://...
Saved wall.jpg
[97 API requests left today, plan: free]
```

(The output above shows the format only; your categories, IDs and counts will differ.)

## Quick start

### 1. Get a free API key

Sign up at **https://nexwall.kodnextech.com/developers/register**. The free plan needs no credit card.

### 2. Install and configure

Requires Python 3.9+.

```bash
git clone https://github.com/kodnextechnologies/nexwall-python.git
cd nexwall-python
pip install .            # or: pip install -e .  for development
```

Set your key as an environment variable (see `.env.example`; never commit it):

```bash
export NEXWALL_API_KEY=your_key_here          # macOS / Linux
setx NEXWALL_API_KEY your_key_here            # Windows (new terminals)
$env:NEXWALL_API_KEY = "your_key_here"        # Windows PowerShell (current session)
```

The package is not on PyPI yet. The `pyproject.toml` is ready for publishing as `nexwall` later; until then, install from source as shown above.

### 3. Run

```bash
nexwall categories
nexwall list --category 5 --sort popular --per-page 10
nexwall list --search mountains
nexwall random --category 5 --download ./wall.jpg
nexwall get 10234 --download ~/Pictures/
nexwall categories --json                  # raw JSON for scripting
python -m nexwall --help                   # works without installing the script
```

Exit codes: `0` success, `1` error, `2` rate limit reached.

### Use it as a library

```python
from nexwall import NexWallClient, RateLimitError

client = NexWallClient()                        # reads NEXWALL_API_KEY

for category in client.categories():
    print(category["id"], category["name"], category["wallpaper_count"])

page = client.wallpapers(category_id=5, sort="popular", per_page=20)
print(page["current_page"], "/", page["last_page"])

try:
    wallpaper = client.random(search="sunset")
    client.download(wallpaper, "downloads/")    # -> downloads/nexwall-<id>.jpg
except RateLimitError as e:
    print("Quota exceeded, retry in", e.retry_after, "seconds")

print(client.remaining_today, "requests left today")
```

### Daily wallpaper changer

`examples/daily_wallpaper.py` downloads one random wallpaper to `~/Pictures/NexWall`, sets it as your desktop background, and keeps the last 7 files. Each run uses **one** API request.

```bash
python examples/daily_wallpaper.py --category 5
```

Schedule it once a day:

- **Windows (Task Scheduler)**
  ```powershell
  schtasks /create /tn "NexWall daily wallpaper" /sc daily /st 09:00 /tr "pythonw C:\path\to\nexwall-python\examples\daily_wallpaper.py"
  ```
  The task runs as you, so the `NEXWALL_API_KEY` you saved with `setx` is available.
- **Linux (cron)**: `crontab -e`
  ```cron
  0 9 * * * NEXWALL_API_KEY=your_key DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus /usr/bin/python3 /path/to/examples/daily_wallpaper.py
  ```
  `DBUS_SESSION_BUS_ADDRESS` is needed for `gsettings` from cron (replace `1000` with your user id from `id -u`).
- **macOS (cron or launchd)**: same cron line without `DISPLAY`/`DBUS_*`. macOS asks once for permission to control "System Events".

## Project structure

```
src/nexwall/
├── __init__.py          # public exports
├── client.py            # NexWallClient + exceptions
├── cli.py               # `nexwall` command
└── __main__.py          # python -m nexwall
examples/daily_wallpaper.py
tests/test_client.py     # after `pip install -e .`: python -m unittest discover -s tests
pyproject.toml
.env.example
```

## API endpoints used

Base URL: `https://nexwall.kodnextech.com/api/developer/v1`

Every request sends `Authorization: Bearer <API_KEY>` and `Accept: application/json`.

| Endpoint | Client method | CLI |
| --- | --- | --- |
| `GET /categories` | `categories()` | `nexwall categories` |
| `GET /wallpapers?page=&per_page=&category_id=&type=&search=&sort=` | `wallpapers()`, `random()` | `nexwall list`, `nexwall random` |
| `GET /categories/{categoryId}/wallpapers` | `category_wallpapers()` | |
| `GET /wallpapers/{id}` | `wallpaper()` | `nexwall get` |

Parameters: `per_page` 1-100 (default 50); `type` is `image` or `live` (live requires Ultra); `search` is 2-100 characters and matches tags; `sort` is `newest`, `oldest`, `popular` or `random`.

Full reference: [API docs](https://nexwall.kodnextech.com/wallpaper-api/docs) · [OpenAPI spec](https://nexwall.kodnextech.com/openapi.json) · [Sandbox](https://nexwall.kodnextech.com/wallpaper-api/sandbox)

## Rate limits & plans

| Plan | Price | Requests per day | Content |
| --- | --- | --- | --- |
| Free | Free, no credit card | 100 | Non-premium categories |
| Pro | ₹399 / $4.99 per month | 10,000 | |
| Ultra | ₹899 / $10.99 per month | 50,000 | Includes live (video) wallpapers |

- The free plan also allows up to 60 requests per minute.
- Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` and `X-Developer-Api-Plan` (available as `client.rate_limit`), and the JSON body includes `plan` and `remaining_requests_today` (`client.plan`, `client.remaining_today`).
- On **HTTP 429** the client raises `RateLimitError` with `retry_after` from the `Retry-After` header. The CLI prints the wait time and exits with code 2; the daily script keeps your current wallpaper.

## Production note

On your own computer, an environment variable is fine. If you build a web app or service on top of this client, keep the key on the server only. Do not ship it in browser JavaScript or a mobile app; have your frontend call your backend, which uses `NexWallClient`, acting as a **backend proxy**. You can pass `base_url=` to point the client at a proxy of your own.

## Related starters

- [Flutter wallpaper app](https://github.com/kodnextechnologies/nexwall-flutter-wallpaper-app)
- [Android Kotlin wallpaper app (Jetpack Compose)](https://github.com/kodnextechnologies/nexwall-android-kotlin-wallpaper-app)
- [React Native / Expo wallpaper app](https://github.com/kodnextechnologies/nexwall-react-native-expo-wallpaper-app)
- [Web starter: Next.js / React, Laravel and plain JavaScript (API key kept server-side)](https://github.com/kodnextechnologies/nexwall-web-starter)

## License

The source code is released under the [MIT License](LICENSE).

Wallpaper images and videos returned by the API are **not** covered by the MIT license. Their use, including use as desktop backgrounds, is governed by the [NexWall Developer API License](https://nexwall.kodnextech.com/wallpaper-api/license).
