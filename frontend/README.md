# Frontend

This folder contains a basic React + Vite frontend for the Django backend.

## Stack

- React
- Axios
- Tailwind CSS
- Vite

## API service

Centralized API calls live in [`src/services/api.js`](src/services/api.js):

- `fetchInventory()` for inventory reads
- `createOrder(orderPayload)` for order creation

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create a local environment file:
```bash
copy .env.example .env.local
```

3. Start the dev server:
```bash
npm run dev
```

## Backend URL

The frontend expects the Django API at `http://127.0.0.1:8000/api` by default. Override this with `VITE_API_BASE_URL` if needed.
