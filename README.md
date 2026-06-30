<<<<<<< HEAD
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
>>>>>>> 3ea15c5 (Initial commit)
