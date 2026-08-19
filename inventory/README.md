# C.A.S.E Inventory Collator (CIC)
[Inventory Debug View](https://caselabbet.se/components?debug)

Collates IZettle and extra google sheet into a single .json file for caselabbet.se/inventory page.
When ran on the GUDs docker this program will build a new .json file and that happens every day at 7 in the morning.

This container published inventory status on [caselabbet.se/components](https://caselabbet.se/components) by collating the [Inventory Sheet](https://docs.google.com/spreadsheets/d/147HL4QCIvZX2amx6_Im6BiK4NwPTtFHxHf3mKN7k_S4/edit?gid=0#gid=0) and Zettle. 

If a component exists in both Zettle and the sheet, they are merged to one entry with full information. Components are matched by (case-insensitive) name. The name of a Zettle component with variants will be `[name] [variant name]`. Components expected to be found in Zettle should be marked as such in the sheet, so that a warning can be shown on the debug page for unmatched components.

- The sheet contains data like a detailed description, drawer location, MPN etc.
- Zettle contains price, stock and images.

Most free or lab components will only be in the sheet, as these are a) not sold and b) too numerous to manage in Zettle.

## Zettle API rate limits and pagination
Both the Products and Inventory endpoints return paginated responses. The inventory endpoint (`/v3/stock`) returns max 100 entries per page by default. Pagination is cursor-based via the `Link` response header — the code follows the `rel="next"` URL until no more pages are returned. A 0.5s delay is added between requests to stay well within the rate limit (4 req/s for inventory).

Source: https://developer.zettle.com/docs/api/inventory/overview

## isolated local dev notes and instructions
Sometimes one will want to check/ improve or solve bugs in inventory collator
program for this one needs to run a local non scheduled version!

### Create a local .env file
Script needs the `ZETTLE_APIKEY=` set. so copy over .env.example to .env
Then provide the key in .env.

OBS! DO NOT INCLUDE APIKEYS IN GIT.

### Using UV
Running python localy:
- Install: uv . It is a fast python package manager written in Rust.

#### Running the program
```bash
uv run main.py
```

This will create what it needs


### Using Docker
Another alternative is to use docker

#### Pre-requisites
- insall docker

#### Building
```bash
docker build -t inventory:latest
```

#### Running
```bash
docker run --env-file .env inventory:latest
```
####
To inspect files you need to build an image then copy over .json to inspect it.

