
# cpyking
food business tracking system
=======
# Fast-Food Tracking Schema

This repository contains a Django ORM schema for a fast-food tracking system optimized for high-write, high-read workloads.

## Included models

- Ingredients and recipe mapping
- Inventory balance plus immutable inventory transactions
- Orders and order lines
- Staff members and shifts

## Notes

- The schema uses indexed foreign keys, status fields, and timestamp columns for efficient filtering.
- Inventory is modeled with both a current balance table and an append-only transaction ledger.
- Order totals are denormalized to keep checkout and reporting queries fast.

## Frontend

A basic React + Vite frontend lives in [`frontend/`](frontend). It includes Axios, Tailwind CSS, and a centralized API service at [`frontend/src/services/api.js`](frontend/src/services/api.js) for inventory and order requests.

To point the frontend at your Django backend, set `VITE_API_BASE_URL` in `frontend/.env` or `frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

Typical commands:

```bash
cd frontend
npm install
npm run dev
```

