# chudfish

Naive betting market arbitrage strategy

## Endpoints (localhost:5001)

```
/matched_market?market=market_name [GET, DELETE]
```

```
/matched_market [PUT, POST]

BODY:
{
    "name": "market_name", 
    "markets": 
    {
        "kalshi": "[uri]", 
        "polymarket":"[uri]"
    }
}
```

```
/list_matched_markets [GET]
```

```
/ticker [GET]
```
