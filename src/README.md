# TrustRoom

Our code for the ti&m challenge: a page that the mock e-banking loads in an iframe, and the backend behind it.

- `backend/`: FastAPI. It reads the customer's bank data from the e-banking's API with the customer's own token, asks Apertus, and stores conversations in Postgres.
- `frontend/`: the page, React with plain CSS in the e-banking's look.
- `docker-compose.yml`: Postgres, and with `--profile app` the backend and the page.
- `gates.sh`: every check a change has to pass.

## Run it

1. Put `LLM_NAME`, `LLM_BASE_URL` and `LLM_API_KEY` into `.env` in the repo root.
2. Start our services, from this folder:
   ```
   docker compose --profile app up --build -d
   ```
3. Start the e-banking and point it at our page, from `../starter`:
   ```
   TRUSTROOM_URL=http://localhost:3000 docker compose up -d
   ```
4. Open http://localhost:8090, log in as one of the demo customers (`lukas` / `lukas2026`) and open the TrustRoom from the header or the sidebar.

For development without Docker, see the commands in `../CLAUDE.md`.
