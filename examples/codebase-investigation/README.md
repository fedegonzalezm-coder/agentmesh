# Example: e-commerce codebase investigation

Four experts covering the main domains of a typical e-commerce app.
Copy `agentmesh.yml` to your project root and adjust the descriptions to match your codebase.

## What each expert covers

| Expert | Ask about |
|--------|-----------|
| `orders` | Order lifecycle, cancellations, refunds, status transitions |
| `payments` | Payment providers, webhooks, retries, charge disputes |
| `auth` | Sessions, guest users, roles, access control |
| `frontend` | Components, state management, routing |

## Example queries

```bash
agentmesh ask orders "What happens to inventory when an order is cancelled?"
agentmesh ask payments "How are failed payment retries handled?"
agentmesh ask auth "Can guest users save items to a wishlist?"
agentmesh ask frontend "Where is the cart state managed?"
```

## Adding a seed

If you have existing documentation, point each expert at it:

```yaml
experts:
  orders:
    description: "Expert in order lifecycle..."
    seed: ./docs/orders.md   # expert reads this on first call
```
